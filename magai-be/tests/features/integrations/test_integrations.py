"""Connecting outside systems, and getting a captured lead to them."""

import json
from unittest.mock import patch

import httpx
import pytest

from app.features.integrations.models import Integration, IntegrationDelivery
from app.features.integrations.providers import (
    CATALOG_BY_ID,
    DeliveryResult,
    LeadPayload,
    ProviderError,
    deliver,
    get_provider,
)
from app.features.integrations.service import (
    integration_covers,
    upsert_integration,
)
from app.features.leads.delivery import enqueue_lead_deliveries, run_deliveries
from app.features.leads.models import Lead, LeadDelivery
from app.features.widgets.models import Widget
from app.platform.security.secrets import (
    SecretDecryptionError,
    decrypt_secret,
    encrypt_secret,
    mask_secret,
)


@pytest.fixture(autouse=True)
def public_dns():
    """Resolve every hostname to a public address.

    The SSRF guard does real DNS lookups, so without this the suite would depend
    on the network and on hooks.slack.com continuing to exist. Tests that assert
    a destination is *refused* use literal private IPs, which skip resolution
    entirely and so are unaffected by this stub.
    """
    with patch(
        "app.platform.security.url_guard.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 443))],
    ):
        yield


def _payload(**overrides) -> LeadPayload:
    defaults = dict(
        email="jo@example.com",
        name="Jo Rivera",
        score=82,
        answers={"team": "11-50"},
        widget_title="Growth quiz",
        widget_id="w-1",
        lead_id="l-1",
        created_at="2026-07-28T10:00:00Z",
    )
    defaults.update(overrides)
    return LeadPayload(**defaults)


class TestSecretStorage:
    def test_round_trips(self):
        assert decrypt_secret(encrypt_secret("pat-eu1-topsecret")) == "pat-eu1-topsecret"

    def test_ciphertext_does_not_contain_the_plaintext(self):
        assert "topsecret" not in encrypt_secret("pat-eu1-topsecret")

    def test_a_tampered_ciphertext_is_rejected_rather_than_partially_read(self):
        token = encrypt_secret("pat-eu1-topsecret")
        with pytest.raises(SecretDecryptionError):
            decrypt_secret(token[:-4] + "AAAA")

    def test_a_different_key_cannot_read_it(self, monkeypatch):
        token = encrypt_secret("pat-eu1-topsecret")
        monkeypatch.setattr(
            "app.platform.config.settings.settings.secret_key", "a-completely-different-secret"
        )
        with pytest.raises(SecretDecryptionError):
            decrypt_secret(token)

    def test_mask_reveals_only_the_tail(self):
        assert mask_secret("pat-eu1-abcd1234") == "••••1234"
        assert mask_secret("ab") == "••••"


class TestProviderCatalog:
    def test_every_provider_declares_renderable_fields(self):
        for provider in CATALOG_BY_ID.values():
            assert provider.fields, f"{provider.id} has no fields to render"
            assert provider.setup_hint, f"{provider.id} has no setup guidance"
            for spec in provider.fields:
                assert spec.label and spec.help_text

    def test_endpoint_providers_take_a_url_field(self):
        for provider in CATALOG_BY_ID.values():
            if provider.auth == "endpoint":
                assert any(spec.name == "endpoint_url" for spec in provider.fields)

    def test_unknown_provider_raises(self):
        with pytest.raises(ProviderError):
            get_provider("mycrm")


class TestDelivery:
    async def test_hubspot_posts_a_contact_with_the_bearer_token(self, monkeypatch):
        seen = {}

        async def fake_post(self, url, **kwargs):
            seen["url"] = url
            seen["headers"] = kwargs.get("headers") or {}
            seen["json"] = kwargs.get("json")
            return httpx.Response(201, request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
        result = await deliver(
            get_provider("hubspot"),
            _payload(),
            credential="pat-eu1-x",
            config=None,
            endpoint_url=None,
        )

        assert result.ok
        assert seen["url"] == "https://api.hubapi.com/crm/v3/objects/contacts"
        assert seen["headers"]["Authorization"] == "Bearer pat-eu1-x"
        assert seen["json"]["properties"]["email"] == "jo@example.com"
        assert seen["json"]["properties"]["firstname"] == "Jo"

    async def test_hubspot_treats_an_existing_contact_as_success(self, monkeypatch):
        # 409 means the person is already in the CRM, which is the outcome we
        # promised. Recording it as a failure would light up a healthy connection.
        async def fake_post(self, url, **kwargs):
            return httpx.Response(
                409, text="Contact already exists", request=httpx.Request("POST", url)
            )

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
        result = await deliver(
            get_provider("hubspot"), _payload(), credential="x", config=None, endpoint_url=None
        )
        assert result.ok

    async def test_mailchimp_derives_its_host_from_the_key_suffix(self, monkeypatch):
        seen = {}

        async def fake_post(self, url, **kwargs):
            seen["url"] = url
            return httpx.Response(200, request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
        result = await deliver(
            get_provider("mailchimp"),
            _payload(),
            credential="abc123-us21",
            config={"list_id": "list1"},
            endpoint_url=None,
        )
        assert result.ok
        assert seen["url"].startswith("https://us21.api.mailchimp.com/3.0/lists/list1/members")

    async def test_mailchimp_without_a_datacenter_suffix_is_a_configuration_error(self):
        with pytest.raises(ProviderError, match="datacenter"):
            await deliver(
                get_provider("mailchimp"),
                _payload(),
                credential="nodatacenter",
                config={"list_id": "l"},
                endpoint_url=None,
            )

    async def test_webhook_signature_covers_the_exact_bytes_sent(self, monkeypatch):
        import hashlib
        import hmac

        seen = {}

        async def fake_post(self, url, **kwargs):
            seen["content"] = kwargs.get("content")
            seen["headers"] = kwargs.get("headers") or {}
            return httpx.Response(200, request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
        result = await deliver(
            get_provider("webhook"),
            _payload(),
            credential=None,
            config=None,
            endpoint_url="https://hooks.example.com/in",
            signing_secret="shhh",
        )

        assert result.ok
        expected = hmac.new(b"shhh", seen["content"], hashlib.sha256).hexdigest()
        # The whole point: a receiver verifying the header against the body it
        # actually received must get a match.
        assert seen["headers"]["X-Magnit-Signature"] == f"sha256={expected}"
        assert json.loads(seen["content"])["lead"]["email"] == "jo@example.com"

    async def test_an_endpoint_pointing_at_a_private_address_is_refused(self):
        result = await deliver(
            get_provider("webhook"),
            _payload(),
            credential=None,
            config=None,
            endpoint_url="http://169.254.169.254/latest/meta-data/",
        )
        assert not result.ok

    async def test_a_redirect_is_never_treated_as_success(self, monkeypatch):
        # Following it would defeat the SSRF validation done on the original host.
        async def fake_post(self, url, **kwargs):
            return httpx.Response(
                302, headers={"Location": "http://127.0.0.1/"}, request=httpx.Request("POST", url)
            )

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
        result = await deliver(
            get_provider("webhook"),
            _payload(),
            credential=None,
            config=None,
            endpoint_url="https://hooks.example.com/in",
        )
        assert not result.ok

    async def test_a_timeout_is_reported_not_raised(self, monkeypatch):
        async def fake_post(self, url, **kwargs):
            raise httpx.ConnectTimeout("too slow")

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
        result = await deliver(
            get_provider("webhook"),
            _payload(),
            credential=None,
            config=None,
            endpoint_url="https://hooks.example.com/in",
        )
        assert not result.ok
        assert "did not respond" in (result.error or "")


class TestConnectionScope:
    def test_none_covers_every_tool_including_future_ones(self):
        import uuid

        integration = Integration(provider="hubspot", widget_ids=None)
        assert integration_covers(integration, uuid.uuid4())

    def test_an_empty_list_covers_nothing(self):
        import uuid

        integration = Integration(provider="hubspot", widget_ids=[])
        assert not integration_covers(integration, uuid.uuid4())

    def test_a_named_list_covers_only_those_tools(self):
        import uuid

        wanted, other = uuid.uuid4(), uuid.uuid4()
        integration = Integration(provider="hubspot", widget_ids=[str(wanted)])
        assert integration_covers(integration, wanted)
        assert not integration_covers(integration, other)


class TestUpsert:
    async def test_stores_the_credential_encrypted_with_a_hint(self, db, user):
        integration = await upsert_integration(
            db, user.id, "hubspot", {"access_token": "pat-eu1-abcd1234"}, None
        )
        await db.commit()

        assert integration.credential_encrypted != "pat-eu1-abcd1234"
        assert integration.credential_hint == "••••1234"
        assert decrypt_secret(integration.credential_encrypted) == "pat-eu1-abcd1234"

    async def test_a_missing_required_field_is_rejected(self, db, user):
        with pytest.raises(ProviderError, match="missing_field"):
            await upsert_integration(db, user.id, "mailchimp", {"api_key": "k-us1"}, None)

    async def test_reconnecting_updates_rather_than_duplicating(self, db, user):
        first = await upsert_integration(
            db, user.id, "hubspot", {"access_token": "pat-old-1111"}, None
        )
        second = await upsert_integration(
            db, user.id, "hubspot", {"access_token": "pat-new-2222"}, None
        )
        await db.commit()

        assert first.id == second.id
        assert second.credential_hint == "••••2222"


class TestRoutes:
    async def test_catalog_marks_what_this_plan_can_use(self, user, as_user):
        response = await (as_user(user)).get("/api/integrations/catalog")
        assert response.status_code == 200
        providers = {p["id"]: p for p in response.json()["providers"]}
        assert "hubspot" in providers
        # Locked providers are shown, not hidden: seeing what an upgrade buys is
        # the point of the screen.
        assert "available" in providers["hubspot"]

    async def test_connect_then_list_then_disconnect(self, user, as_user):
        client = as_user(user)
        created = await client.post(
            "/api/integrations",
            json={"provider": "slack", "values": {"endpoint_url": "https://hooks.slack.com/x/y"}},
        )
        assert created.status_code == 201
        assert created.json()["status"] == "connected"

        listed = await client.get("/api/integrations")
        assert [i["provider"] for i in listed.json()["integrations"]] == ["slack"]

        removed = await client.delete(f"/api/integrations/{created.json()['id']}")
        assert removed.status_code == 204
        assert (await client.get("/api/integrations")).json()["integrations"] == []

    async def test_the_credential_is_never_returned(self, user, as_user):
        response = await (as_user(user)).post(
            "/api/integrations",
            json={"provider": "hubspot", "values": {"access_token": "pat-eu1-secret9999"}},
        )
        body = response.text
        assert "pat-eu1-secret9999" not in body
        assert response.json()["credential_hint"] == "••••9999"

    async def test_an_internal_endpoint_is_refused_at_connect_time(self, user, as_user):
        response = await (as_user(user)).post(
            "/api/integrations",
            json={"provider": "webhook", "values": {"endpoint_url": "http://127.0.0.1:8000/admin"}},
        )
        assert response.status_code == 422

    async def test_pausing_keeps_the_credential(self, db, user, as_user):
        client = as_user(user)
        created = await client.post(
            "/api/integrations",
            json={"provider": "hubspot", "values": {"access_token": "pat-eu1-keep1234"}},
        )
        integration_id = created.json()["id"]

        paused = await client.patch(f"/api/integrations/{integration_id}", json={"enabled": False})
        assert paused.status_code == 200
        assert paused.json()["status"] == "disabled"
        # Still there, so resuming does not require pasting the key again.
        assert paused.json()["credential_hint"] == "••••1234"

    async def test_another_workspace_cannot_touch_a_connection(self, user, other_user, as_user):
        created = await (as_user(user)).post(
            "/api/integrations",
            json={"provider": "slack", "values": {"endpoint_url": "https://hooks.slack.com/a/b"}},
        )
        intruder = as_user(other_user)
        integration_id = created.json()["id"]
        paused = await intruder.patch(
            f"/api/integrations/{integration_id}", json={"enabled": False}
        )
        assert paused.status_code == 404
        assert (await intruder.delete(f"/api/integrations/{integration_id}")).status_code == 404

    async def test_test_endpoint_records_the_attempt(self, user, as_user, monkeypatch):
        # Patched at the service seam, not at httpx: the test client is itself an
        # httpx.AsyncClient, so stubbing the class here would intercept the very
        # request under test and never reach the app.
        async def fake_deliver(*args, **kwargs):
            return DeliveryResult(True, 200)

        monkeypatch.setattr("app.features.integrations.service.deliver", fake_deliver)
        client = as_user(user)
        created = await client.post(
            "/api/integrations",
            json={"provider": "slack", "values": {"endpoint_url": "https://hooks.slack.com/a/b"}},
        )
        response = await client.post(f"/api/integrations/{created.json()['id']}/test")
        assert response.status_code == 200
        assert response.json()["ok"] is True

    async def test_a_failed_test_marks_the_connection_and_explains_why(
        self, user, as_user, monkeypatch
    ):
        async def fake_deliver(*args, **kwargs):
            return DeliveryResult(False, 401, "invalid_token")

        monkeypatch.setattr("app.features.integrations.service.deliver", fake_deliver)
        client = as_user(user)
        created = await client.post(
            "/api/integrations",
            json={"provider": "slack", "values": {"endpoint_url": "https://hooks.slack.com/a/b"}},
        )
        response = await client.post(f"/api/integrations/{created.json()['id']}/test")
        assert response.json()["ok"] is False
        assert "invalid_token" in response.json()["message"]

        listed = (await client.get("/api/integrations")).json()["integrations"][0]
        assert listed["status"] == "error"


class TestLeadFanOut:
    """Getting a captured lead to every connected system, and keeping trying.

    Delivery used to be one best-effort pass: a connection that failed was
    marked broken and then excluded from the query for every subsequent lead, so
    one bad afternoon at a CRM quietly stopped a business receiving leads there
    until somebody happened to look. These go through the outbox, which is what
    makes a failure a retry rather than a loss.
    """

    async def _lead(self, db, user):
        widget = Widget(
            user_id=user.id,
            target_url="https://example.com",
            widget_type="readiness_quiz",
            title="Quiz",
            status="active",
        )
        db.add(widget)
        await db.commit()
        lead = Lead(widget_id=widget.id, email="jo@example.com", name="Jo", score=77)
        db.add(lead)
        await db.commit()
        await db.refresh(lead)
        return widget, lead

    async def _deliver(self, db, session_factory, lead, widget):
        """Enqueue and attempt, exactly as the submit endpoint does."""
        rows = await enqueue_lead_deliveries(db, lead, widget)
        await db.commit()
        integration_ids = [row.id for row in rows if row.channel == "integration"]
        return await run_deliveries(integration_ids, session_factory=session_factory)

    async def test_delivers_to_every_covering_connection(
        self, db, user, session_factory, monkeypatch
    ):
        calls = []

        async def fake_post(self, url, **kwargs):
            calls.append(url)
            return httpx.Response(200, request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
        widget, lead = await self._lead(db, user)
        await upsert_integration(
            db, user.id, "slack", {"endpoint_url": "https://hooks.slack.com/a/b"}, None
        )
        await upsert_integration(
            db, user.id, "webhook", {"endpoint_url": "https://hooks.example.com/in"}, None
        )
        await db.commit()

        assert await self._deliver(db, session_factory, lead, widget) == 2
        await db.refresh(lead)
        assert lead.forwarded is True

    async def test_skips_connections_scoped_to_other_tools(
        self, db, user, session_factory, monkeypatch
    ):
        import uuid

        async def fake_post(self, url, **kwargs):
            raise AssertionError("should not have delivered")

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
        widget, lead = await self._lead(db, user)
        await upsert_integration(
            db,
            user.id,
            "slack",
            {"endpoint_url": "https://hooks.slack.com/a/b"},
            [str(uuid.uuid4())],
        )
        await db.commit()

        assert await self._deliver(db, session_factory, lead, widget) == 0

    async def test_a_failing_provider_is_recorded_and_retried_later(
        self, db, user, session_factory, monkeypatch
    ):
        # A visitor on a customer's website must never see a CRM outage — and
        # the lead must not be quietly abandoned because of one either.
        async def fake_post(self, url, **kwargs):
            return httpx.Response(500, text="upstream boom", request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
        widget, lead = await self._lead(db, user)
        integration = await upsert_integration(
            db, user.id, "slack", {"endpoint_url": "https://hooks.slack.com/a/b"}, None
        )
        await db.commit()

        assert await self._deliver(db, session_factory, lead, widget) == 0

        async with session_factory() as check:
            from sqlalchemy import select

            refreshed = await check.get(Integration, integration.id)
            assert refreshed.status == "error"
            assert refreshed.failed_count == 1

            attempts = (
                (
                    await check.execute(
                        select(IntegrationDelivery).where(
                            IntegrationDelivery.integration_id == integration.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert [a.status for a in attempts] == ["failed"]

            # The lead is still owed to this connection, with a time to try again.
            owed = (
                (
                    await check.execute(
                        select(LeadDelivery).where(LeadDelivery.channel == "integration")
                    )
                )
                .scalars()
                .all()
            )
            assert [row.status for row in owed] == ["pending"]
            assert owed[0].attempts == 1
            assert owed[0].next_attempt_at is not None

    async def test_a_connection_that_failed_before_still_gets_the_next_lead(
        self, db, user, session_factory, monkeypatch
    ):
        """The bug this rewrite exists to kill.

        One failure used to set the connection to `error`, and the fan-out only
        ever queried connections in `connected`. Every lead after that skipped
        it — no attempt, no record, no warning — so a business could lose weeks
        of leads to a token that expired one Tuesday.
        """

        async def fake_post(self, url, **kwargs):
            return httpx.Response(200, request=httpx.Request("POST", url))

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
        widget, lead = await self._lead(db, user)
        integration = await upsert_integration(
            db, user.id, "slack", {"endpoint_url": "https://hooks.slack.com/a/b"}, None
        )
        integration.status = "error"
        integration.last_error = "yesterday's outage"
        await db.commit()

        assert await self._deliver(db, session_factory, lead, widget) == 1

        async with session_factory() as check:
            refreshed = await check.get(Integration, integration.id)
            # Recovered, not just delivered: a connection that works again must
            # stop being reported as broken.
            assert refreshed.status == "connected"
            assert refreshed.last_error is None

    async def test_a_disabled_connection_receives_nothing(
        self, db, user, session_factory, monkeypatch
    ):
        async def fake_post(self, url, **kwargs):
            raise AssertionError("should not have delivered")

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
        widget, lead = await self._lead(db, user)
        integration = await upsert_integration(
            db, user.id, "slack", {"endpoint_url": "https://hooks.slack.com/a/b"}, None
        )
        integration.status = "disabled"
        await db.commit()

        assert await self._deliver(db, session_factory, lead, widget) == 0
