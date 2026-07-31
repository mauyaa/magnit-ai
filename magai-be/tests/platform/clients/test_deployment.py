"""The Vercel client — the last hop, where a build becomes a public URL.

Everything here is a failure the customer sees directly: a deploy that reports
success without a URL, a project left behind SSO so the embed 401s in an
iframe, a domain removal that half-happened. None of it can be covered by a live
call in CI, so the seam under test is the HTTP boundary itself.
"""

from __future__ import annotations

import httpx
import pytest

from app.platform.clients import deployment
from app.platform.config.settings import settings


def _response(status: int, payload: dict | None = None, *, method: str = "POST") -> httpx.Response:
    return httpx.Response(
        status,
        json=payload if payload is not None else {},
        request=httpx.Request(method, "https://api.vercel.com/"),
    )


class TestReadDistFiles:
    def test_walks_nested_directories_into_vercel_payload(self, tmp_path):
        (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
        assets = tmp_path / "assets"
        assets.mkdir()
        (assets / "app.js").write_text("console.log(1)", encoding="utf-8")

        files = deployment._read_dist_files(str(tmp_path))

        by_path = {entry["file"]: entry["data"] for entry in files}
        assert by_path["index.html"] == "<html></html>"
        assert by_path["assets/app.js"] == "console.log(1)"

    def test_paths_are_posix_even_on_windows(self, tmp_path):
        """Vercel keys files by URL path; a backslash would create a literal name."""
        nested = tmp_path / "assets" / "img"
        nested.mkdir(parents=True)
        (nested / "logo.svg").write_text("<svg/>", encoding="utf-8")

        files = deployment._read_dist_files(str(tmp_path))

        assert files[0]["file"] == "assets/img/logo.svg"
        assert "\\" not in files[0]["file"]

    def test_missing_directory_is_an_error(self, tmp_path):
        with pytest.raises(RuntimeError, match="Dist directory not found"):
            deployment._read_dist_files(str(tmp_path / "nope"))

    def test_empty_directory_is_an_error(self, tmp_path):
        """An empty dist means the build produced nothing; deploying it hides that."""
        with pytest.raises(RuntimeError, match="Dist directory is empty"):
            deployment._read_dist_files(str(tmp_path))


class TestHeaders:
    def test_missing_token_is_refused_before_any_request(self, monkeypatch):
        monkeypatch.setattr(settings, "vercel_api_token", "")

        with pytest.raises(RuntimeError, match="MAGAI_VERCEL_API_TOKEN not set"):
            deployment._vercel_headers()

    def test_token_is_sent_as_a_bearer(self, monkeypatch):
        monkeypatch.setattr(settings, "vercel_api_token", "tok_abc")

        headers = deployment._vercel_headers()

        assert headers["Authorization"] == "Bearer tok_abc"
        assert headers["Content-Type"] == "application/json"


class TestDeployDirectory:
    async def test_missing_token_is_refused_before_reading_the_build(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings, "vercel_api_token", "")

        with pytest.raises(RuntimeError, match="MAGAI_VERCEL_API_TOKEN not set"):
            await deployment.deploy_directory(str(tmp_path), "abcdef1234")

    async def test_successful_deploy_returns_an_https_url(self, monkeypatch, tmp_path):
        (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
        seen: dict = {}

        async def fake_post(self, url, **kwargs):
            seen["url"] = url
            seen["json"] = kwargs.get("json")
            return _response(200, {"url": "magai-widget-abcdef12.vercel.app"})

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

        result = await deployment.deploy_directory(str(tmp_path), "abcdef1234567890")

        # Vercel returns a bare host; an embed needs a scheme or the iframe
        # resolves it relative to the customer's own page.
        assert result.url == "https://magai-widget-abcdef12.vercel.app"
        assert result.widget_id == "abcdef1234567890"
        assert seen["json"]["name"] == "magai-widget-abcdef1234567890"
        assert seen["json"]["target"] == "production"

    async def test_the_embed_address_is_the_project_alias_not_this_build(
        self, monkeypatch, tmp_path
    ):
        """The one property the snippet on a customer's website depends on.

        Vercel mints a fresh hostname for every deployment. Handing that to a
        customer means their page keeps serving one frozen build, and silently
        breaks on any provider-side cleanup. The project alias always resolves
        to whatever is currently live, which is what "paste this once" means.
        """
        (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
        seen: dict = {}

        async def fake_post(self, url, **kwargs):
            seen["json"] = kwargs.get("json")
            return _response(200, {"url": "magai-widget-w-9f8e7d6.vercel.app", "id": "dpl_99"})

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

        result = await deployment.deploy_directory(str(tmp_path), "abcdef1234567890")

        assert result.url == "https://magai-widget-w-9f8e7d6.vercel.app"
        assert result.embed_url == "https://magai-widget-abcdef1234567890.vercel.app"
        assert result.provider_deployment_id == "dpl_99"
        # Requested explicitly, so a failure to assign it is a failed deploy
        # rather than a tool nobody can embed.
        assert seen["json"]["alias"] == ["magai-widget-abcdef1234567890.vercel.app"]

    async def test_project_is_taken_out_of_sso_after_deploy(self, monkeypatch, tmp_path):
        """A protected project renders a login page inside the customer's iframe."""
        (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
        patched: list[tuple[str, dict]] = []

        async def fake_post(self, url, **kwargs):
            return _response(201, {"url": "w.vercel.app", "projectId": "prj_123"})

        async def fake_patch(self, url, **kwargs):
            patched.append((url, kwargs.get("json")))
            return _response(200, {}, method="PATCH")

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
        monkeypatch.setattr(httpx.AsyncClient, "patch", fake_patch)

        await deployment.deploy_directory(str(tmp_path), "abcdef1234")

        assert patched == [("https://api.vercel.com/v9/projects/prj_123", {"ssoProtection": None})]

    async def test_sso_failure_does_not_fail_the_deploy(self, monkeypatch, tmp_path):
        """The build is live and reachable; a failed unprotect is worth a log, not a rollback."""
        (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")

        async def fake_post(self, url, **kwargs):
            return _response(200, {"url": "w.vercel.app", "projectId": "prj_123"})

        async def fake_patch(self, url, **kwargs):
            return _response(403, {"error": "forbidden"}, method="PATCH")

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
        monkeypatch.setattr(httpx.AsyncClient, "patch", fake_patch)

        result = await deployment.deploy_directory(str(tmp_path), "abcdef1234")

        assert result.url == "https://w.vercel.app"

    async def test_no_project_id_skips_the_sso_call(self, monkeypatch, tmp_path):
        (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
        patched: list[str] = []

        async def fake_post(self, url, **kwargs):
            return _response(200, {"url": "w.vercel.app"})

        async def fake_patch(self, url, **kwargs):
            patched.append(url)
            return _response(200, {}, method="PATCH")

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
        monkeypatch.setattr(httpx.AsyncClient, "patch", fake_patch)

        await deployment.deploy_directory(str(tmp_path), "abcdef1234")

        assert patched == []

    async def test_rejected_deploy_raises(self, monkeypatch, tmp_path):
        (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")

        async def fake_post(self, url, **kwargs):
            return _response(402, {"error": "payment required"})

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

        with pytest.raises(RuntimeError, match="Vercel deploy failed: 402"):
            await deployment.deploy_directory(str(tmp_path), "abcdef1234")

    async def test_success_without_a_url_raises(self, monkeypatch, tmp_path):
        """A 200 with no URL is a failed deploy wearing a success code."""
        (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")

        async def fake_post(self, url, **kwargs):
            return _response(200, {"projectId": "prj_123"})

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

        with pytest.raises(RuntimeError, match="Vercel returned no URL"):
            await deployment.deploy_directory(str(tmp_path), "abcdef1234")


class TestProjectDomains:
    def test_project_name_is_derived_from_the_widget_id(self):
        """Deploys and domain calls must agree on the project, or they target different ones."""
        assert deployment._project_name("abcdef1234567890") == "magai-widget-abcdef1234567890"

    def test_the_whole_id_is_used_so_two_tools_cannot_share_a_project(self):
        """A truncated id is a shared hostname between unrelated customers.

        One project per tool is what makes the alias a safe permanent address.
        If two ids collapsed to the same project name, one customer's publish
        would replace what the other customer's website is serving.
        """
        first = "3f6b1a52-9c1e-4a1f-9f0b-2c0f5d7a1b34"
        second = "3f6b1a52-0000-0000-0000-000000000000"

        assert deployment._project_name(first) != deployment._project_name(second)

    def test_the_alias_follows_the_project_name(self):
        widget_id = "3F6B1A52-9C1E-4A1F-9F0B-2C0F5D7A1B34"
        assert deployment._stable_alias(widget_id) == (
            f"{deployment._project_name(widget_id)}.vercel.app"
        )
        # Vercel hostnames are lowercase; an id with capitals must not produce a
        # hostname the browser will normalise into a different one.
        assert deployment._stable_alias(widget_id).islower()

    async def test_add_domain_returns_vercels_payload(self, monkeypatch):
        async def fake_post(self, url, **kwargs):
            assert url.endswith("/v10/projects/magai-widget-abcdef1234/domains")
            assert kwargs["json"] == {"name": "tools.example.com"}
            return _response(200, {"name": "tools.example.com", "verified": False})

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

        payload = await deployment.add_project_domain("abcdef1234", "tools.example.com")

        assert payload["verified"] is False

    async def test_add_domain_failure_raises(self, monkeypatch):
        async def fake_post(self, url, **kwargs):
            return _response(409, {"error": "domain already in use"})

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

        with pytest.raises(RuntimeError, match="Vercel domain assignment failed: 409"):
            await deployment.add_project_domain("abcdef1234", "tools.example.com")

    async def test_verify_domain_returns_the_challenge_state(self, monkeypatch):
        async def fake_post(self, url, **kwargs):
            assert url.endswith("/domains/tools.example.com/verify")
            return _response(200, {"verified": True})

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

        payload = await deployment.verify_project_domain("abcdef1234", "tools.example.com")

        assert payload["verified"] is True

    async def test_verify_domain_failure_raises(self, monkeypatch):
        async def fake_post(self, url, **kwargs):
            return _response(403, {"error": "not verified"})

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

        with pytest.raises(RuntimeError, match="Vercel domain verification failed: 403"):
            await deployment.verify_project_domain("abcdef1234", "tools.example.com")

    @pytest.mark.parametrize("status", [200, 204, 404])
    async def test_remove_domain_treats_already_gone_as_done(self, monkeypatch, status):
        """404 means the hostname is not attached, which is the state being asked for."""

        async def fake_delete(self, url, **kwargs):
            return _response(status, {}, method="DELETE")

        monkeypatch.setattr(httpx.AsyncClient, "delete", fake_delete)

        assert await deployment.remove_project_domain("abcdef1234", "tools.example.com") is None

    async def test_remove_domain_failure_raises(self, monkeypatch):
        async def fake_delete(self, url, **kwargs):
            return _response(500, {"error": "boom"}, method="DELETE")

        monkeypatch.setattr(httpx.AsyncClient, "delete", fake_delete)

        with pytest.raises(RuntimeError, match="Vercel domain removal failed: 500"):
            await deployment.remove_project_domain("abcdef1234", "tools.example.com")
