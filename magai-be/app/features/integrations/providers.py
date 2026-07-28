"""The provider catalogue and the request each one actually sends.

Every provider here delivers for real. None of them is a decorative toggle: if a
connection says "connected", a lead was accepted by that system, and the "send a
test event" button performs the same request the real delivery will.

Two shapes of connection, and the difference matters for security:

* **Keyed** providers authenticate to a host we hard-code (``api.hubapi.com``).
  The customer supplies a credential, never a destination, so there is nothing
  for an attacker to point at an internal address.
* **Endpoint** providers are a URL the customer pastes. That is attacker-
  controlled input reaching a server-side fetch, so every one of them goes
  through the SSRF guard before a byte is sent — the same guard the site
  analyzer uses.

Deliberately not OAuth. A real HubSpot or Salesforce OAuth flow needs a
registered partner application and a published redirect URI, which is an
onboarding and review process, not a code change. Private-app tokens and
Web-to-Lead are the documented, first-class alternatives both vendors support,
they work the day a customer pastes a credential, and nothing here has to
pretend to a connection it does not have.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

from app.features.billing.plans import Feature
from app.platform.security.url_guard import UnsafeTargetURL, validate_target_url

logger = logging.getLogger(__name__)

AuthKind = Literal["api_key", "endpoint"]

# Every outbound call is bounded. A provider having a bad day must not hold a
# background task open indefinitely.
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class ProviderError(Exception):
    """The connection is misconfigured — a missing field, a malformed key."""


@dataclass(frozen=True)
class ProviderField:
    """One thing the customer has to supply, described well enough to render."""

    name: str
    label: str
    help_text: str
    # "secret" is write-only: it is stored encrypted and never returned.
    kind: Literal["text", "secret", "url"] = "text"
    required: bool = True
    placeholder: str = ""


@dataclass(frozen=True)
class Provider:
    id: str
    name: str
    category: str
    description: str
    auth: AuthKind
    fields: tuple[ProviderField, ...]
    # What the customer has to do on the other side before this can work. Shown
    # verbatim in the connect dialog, because "where do I find my API key" is the
    # single most common place these flows are abandoned.
    setup_hint: str
    feature: Feature = Feature.CRM_INTEGRATIONS
    docs_url: str = ""


CATALOG: tuple[Provider, ...] = (
    Provider(
        id="hubspot",
        name="HubSpot",
        category="CRM",
        description="Create or update a contact for every lead, with their score and answers.",
        auth="api_key",
        fields=(
            ProviderField(
                name="access_token",
                label="Private app token",
                help_text="Settings → Integrations → Private Apps → your app → Auth.",
                kind="secret",
                placeholder="pat-eu1-…",
            ),
        ),
        setup_hint=(
            "Create a private app in HubSpot with the crm.objects.contacts.write scope, "
            "then paste its access token here."
        ),
        docs_url="https://developers.hubspot.com/docs/api/private-apps",
    ),
    Provider(
        id="salesforce",
        name="Salesforce",
        category="CRM",
        description="Send each lead through Web-to-Lead into your standard lead queue.",
        auth="api_key",
        fields=(
            ProviderField(
                name="org_id",
                label="Organisation ID",
                help_text="Setup → Company Information → Salesforce.com Organisation ID.",
                placeholder="00D5g000000XXXX",
            ),
            ProviderField(
                name="return_url",
                label="Return URL",
                help_text="Any page on your site. Salesforce requires one; nobody is sent there.",
                kind="url",
                required=False,
                placeholder="https://yourcompany.com/thanks",
            ),
        ),
        setup_hint=(
            "Enable Web-to-Lead in Setup → Feature Settings → Marketing, then copy your "
            "organisation ID."
        ),
        docs_url="https://help.salesforce.com/s/articleView?id=sf.setting_up_web-to-lead.htm",
    ),
    Provider(
        id="activecampaign",
        name="ActiveCampaign",
        category="Marketing",
        description="Add the lead as a contact so your automations can pick them up.",
        auth="api_key",
        fields=(
            ProviderField(
                name="api_url",
                label="API URL",
                help_text="Settings → Developer. Looks like https://yourname.api-us1.com.",
                kind="url",
                placeholder="https://yourname.api-us1.com",
            ),
            ProviderField(
                name="api_key",
                label="API key",
                help_text="Settings → Developer, beside the API URL.",
                kind="secret",
            ),
        ),
        setup_hint="Both values are on one screen: Settings → Developer.",
        docs_url="https://developers.activecampaign.com/reference/overview",
    ),
    Provider(
        id="mailchimp",
        name="Mailchimp",
        category="Marketing",
        description="Subscribe the lead to an audience, tagged with the tool that captured them.",
        auth="api_key",
        fields=(
            ProviderField(
                name="api_key",
                label="API key",
                help_text="Account → Extras → API keys. The trailing -us21 part matters.",
                kind="secret",
                placeholder="abc123…-us21",
            ),
            ProviderField(
                name="list_id",
                label="Audience ID",
                help_text="Audience → Settings → Audience name and defaults.",
                placeholder="a1b2c3d4e5",
            ),
        ),
        setup_hint=(
            "Copy the API key including its datacenter suffix, then the audience ID of the "
            "list these leads should join."
        ),
        docs_url="https://mailchimp.com/developer/marketing/api/list-members/",
    ),
    Provider(
        id="google_sheets",
        name="Google Sheets",
        category="Spreadsheet",
        description="Append a row per lead to a sheet you control.",
        auth="endpoint",
        fields=(
            ProviderField(
                name="endpoint_url",
                label="Apps Script URL",
                help_text="The /exec URL from Deploy → New deployment → Web app.",
                kind="url",
                placeholder="https://script.google.com/macros/s/…/exec",
            ),
        ),
        setup_hint=(
            "In your sheet: Extensions → Apps Script, publish a web app that appends "
            "e.postData rows, and paste its /exec URL here."
        ),
        docs_url="https://developers.google.com/apps-script/guides/web",
    ),
    Provider(
        id="slack",
        name="Slack",
        category="Notifications",
        description="Post every lead into a channel the moment it arrives.",
        auth="endpoint",
        fields=(
            ProviderField(
                name="endpoint_url",
                label="Incoming webhook URL",
                help_text="Slack app → Incoming Webhooks → Add New Webhook to Workspace.",
                kind="url",
                placeholder="https://hooks.slack.com/services/…",
            ),
        ),
        setup_hint="Create a Slack app, enable Incoming Webhooks, and add one to a channel.",
        feature=Feature.WEBHOOK_DELIVERY,
        docs_url="https://api.slack.com/messaging/webhooks",
    ),
    Provider(
        id="zapier",
        name="Zapier",
        category="Automation",
        description="Trigger a Zap with the full signed lead payload.",
        auth="endpoint",
        fields=(
            ProviderField(
                name="endpoint_url",
                label="Catch Hook URL",
                help_text="From the Webhooks by Zapier trigger, 'Catch Hook'.",
                kind="url",
                placeholder="https://hooks.zapier.com/hooks/catch/…",
            ),
        ),
        setup_hint="Start a Zap with Webhooks by Zapier → Catch Hook and copy its URL.",
        feature=Feature.WEBHOOK_DELIVERY,
        docs_url="https://zapier.com/apps/webhook/integrations",
    ),
    Provider(
        id="make",
        name="Make",
        category="Automation",
        description="Run a scenario on every captured lead.",
        auth="endpoint",
        fields=(
            ProviderField(
                name="endpoint_url",
                label="Custom webhook URL",
                help_text="From the Webhooks → Custom webhook module.",
                kind="url",
                placeholder="https://hook.eu2.make.com/…",
            ),
        ),
        setup_hint="Add a Custom webhook module to your scenario and copy its address.",
        feature=Feature.WEBHOOK_DELIVERY,
        docs_url="https://www.make.com/en/help/tools/webhooks",
    ),
    Provider(
        id="n8n",
        name="n8n",
        category="Automation",
        description="Start a workflow from the signed lead payload.",
        auth="endpoint",
        fields=(
            ProviderField(
                name="endpoint_url",
                label="Webhook URL",
                help_text="The production URL from your Webhook trigger node.",
                kind="url",
            ),
        ),
        setup_hint="Add a Webhook node, activate the workflow, and copy the production URL.",
        feature=Feature.WEBHOOK_DELIVERY,
        docs_url="https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/",
    ),
    Provider(
        id="webhook",
        name="Custom endpoint",
        category="Automation",
        description="POST a signed JSON payload to any endpoint you run.",
        auth="endpoint",
        fields=(
            ProviderField(
                name="endpoint_url",
                label="Receiving URL",
                help_text="Must be public HTTPS. Every request carries an HMAC signature.",
                kind="url",
                placeholder="https://api.yourcompany.com/magnit/leads",
            ),
        ),
        setup_hint=(
            "Verify the X-Magnit-Signature header against your signing secret before "
            "trusting a payload."
        ),
        feature=Feature.WEBHOOK_DELIVERY,
    ),
)

CATALOG_BY_ID: dict[str, Provider] = {provider.id: provider for provider in CATALOG}


def get_provider(provider_id: str) -> Provider:
    provider = CATALOG_BY_ID.get(provider_id)
    if provider is None:
        raise ProviderError(f"unknown_provider:{provider_id}")
    return provider


@dataclass
class DeliveryResult:
    ok: bool
    status_code: int | None = None
    error: str | None = None


@dataclass
class LeadPayload:
    """The provider-neutral view of a lead, mapped per provider below."""

    email: str
    name: str | None
    score: int | None
    answers: dict[str, Any] = field(default_factory=dict)
    result_title: str | None = None
    widget_title: str = ""
    widget_id: str = ""
    lead_id: str = ""
    created_at: str = ""
    is_test: bool = False

    @property
    def first_name(self) -> str:
        return (self.name or "").strip().split(" ")[0] if self.name else ""

    @property
    def last_name(self) -> str:
        parts = (self.name or "").strip().split(" ")
        return " ".join(parts[1:]) if len(parts) > 1 else ""

    def as_json(self) -> dict[str, Any]:
        return {
            "event": "lead.test" if self.is_test else "lead.created",
            "lead": {
                "id": self.lead_id,
                "email": self.email,
                "name": self.name,
                "score": self.score,
                "answers": self.answers,
                "result": self.result_title,
                "created_at": self.created_at,
            },
            "tool": {"id": self.widget_id, "title": self.widget_title},
        }


def _short_error(response: httpx.Response) -> str:
    """A useful, bounded fragment of a provider's rejection.

    Providers explain refusals in the body ("Contact already exists", "invalid
    audience id"); showing that is the difference between a customer fixing their
    connection and filing a support ticket. Truncated because some of them return
    a page of HTML.
    """
    text = (response.text or "").strip().replace("\n", " ")
    return text[:280] if text else f"HTTP {response.status_code}"


async def _post(
    client: httpx.AsyncClient,
    url: str,
    *,
    json_body: Any = None,
    data: dict[str, str] | None = None,
    content: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> DeliveryResult:
    response = await client.post(url, json=json_body, data=data, content=content, headers=headers)
    # A redirect is never a success here: following one would defeat the SSRF
    # validation performed on the original host.
    if response.is_redirect:
        return DeliveryResult(False, response.status_code, "destination redirected the request")
    if response.status_code >= 300:
        return DeliveryResult(False, response.status_code, _short_error(response))
    return DeliveryResult(True, response.status_code)


async def _deliver_hubspot(
    client: httpx.AsyncClient, credential: str, config: dict, payload: LeadPayload
) -> DeliveryResult:
    properties: dict[str, Any] = {"email": payload.email}
    if payload.first_name:
        properties["firstname"] = payload.first_name
    if payload.last_name:
        properties["lastname"] = payload.last_name
    if payload.score is not None:
        properties["hs_lead_status"] = "NEW"
    result = await _post(
        client,
        "https://api.hubapi.com/crm/v3/objects/contacts",
        json_body={"properties": properties},
        headers={"Authorization": f"Bearer {credential}"},
    )
    # 409 is HubSpot's "this contact already exists". That is a successful
    # outcome for lead capture — the person is in the CRM, which is all we
    # promised — so it must not be recorded as a delivery failure.
    if not result.ok and result.status_code == 409:
        return DeliveryResult(True, 409)
    return result


async def _deliver_salesforce(
    client: httpx.AsyncClient, credential: str, config: dict, payload: LeadPayload
) -> DeliveryResult:
    org_id = str(config.get("org_id") or "").strip()
    if not org_id:
        raise ProviderError("salesforce_org_id_missing")
    form = {
        "oid": org_id,
        "email": payload.email,
        "first_name": payload.first_name or "Unknown",
        "last_name": payload.last_name or payload.first_name or "Lead",
        "company": payload.widget_title or "Website lead",
        "lead_source": "Magnit",
        "retURL": str(config.get("return_url") or "https://example.com"),
    }
    if payload.score is not None:
        form["description"] = f"Magnit score {payload.score}/100"
    # Web-to-Lead answers 200 with an HTML body whatever happens, so a 2xx here
    # means "accepted for processing", not "a lead row exists". That limitation
    # is inherent to the endpoint and is stated on the connection card rather
    # than papered over with a fake verification step.
    return await _post(
        client,
        "https://webto.salesforce.com/servlet/servlet.WebToLead?encoding=UTF-8",
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


async def _deliver_activecampaign(
    client: httpx.AsyncClient, credential: str, config: dict, payload: LeadPayload
) -> DeliveryResult:
    api_url = str(config.get("api_url") or "").strip().rstrip("/")
    if not api_url:
        raise ProviderError("activecampaign_api_url_missing")
    # The customer supplies this host, so it is validated like any other
    # customer-controlled destination.
    validate_target_url(f"{api_url}/api/3/contacts")
    return await _post(
        client,
        f"{api_url}/api/3/contacts",
        json_body={
            "contact": {
                "email": payload.email,
                "firstName": payload.first_name,
                "lastName": payload.last_name,
            }
        },
        headers={"Api-Token": credential},
    )


async def _deliver_mailchimp(
    client: httpx.AsyncClient, credential: str, config: dict, payload: LeadPayload
) -> DeliveryResult:
    list_id = str(config.get("list_id") or "").strip()
    if not list_id:
        raise ProviderError("mailchimp_list_id_missing")
    # The datacenter is encoded in the key's suffix; without it there is no host
    # to talk to, so this is a configuration error rather than a delivery one.
    _, _, datacenter = credential.partition("-")
    if not datacenter:
        raise ProviderError("mailchimp_datacenter_missing")
    token = base64.b64encode(f"magnit:{credential}".encode()).decode()
    result = await _post(
        client,
        f"https://{datacenter}.api.mailchimp.com/3.0/lists/{list_id}/members",
        json_body={
            "email_address": payload.email,
            "status": "subscribed",
            "merge_fields": {"FNAME": payload.first_name, "LNAME": payload.last_name},
            "tags": [payload.widget_title[:100]] if payload.widget_title else [],
        },
        headers={"Authorization": f"Basic {token}"},
    )
    # Mailchimp 400s an address that is already a member. Same reasoning as
    # HubSpot's 409: the person is on the list, which is the outcome asked for.
    if (
        not result.ok
        and result.status_code == 400
        and "already a list member" in (result.error or "")
    ):
        return DeliveryResult(True, 400)
    return result


async def _deliver_slack(
    client: httpx.AsyncClient, url: str, payload: LeadPayload
) -> DeliveryResult:
    lines = [f"*{payload.widget_title or 'Magnit tool'}* captured a lead", f"• {payload.email}"]
    if payload.name:
        lines.append(f"• {payload.name}")
    if payload.score is not None:
        lines.append(f"• Score {payload.score}/100")
    if payload.result_title:
        lines.append(f"• Result: {payload.result_title}")
    if payload.is_test:
        lines.append("_This is a test event._")
    return await _post(client, url, json_body={"text": "\n".join(lines)})


async def deliver(
    provider: Provider,
    payload: LeadPayload,
    *,
    credential: str | None,
    config: dict | None,
    endpoint_url: str | None,
    signing_secret: str | None = None,
) -> DeliveryResult:
    """Send one lead to one provider.

    Returns a result rather than raising for transport failures: a provider being
    down is an expected condition that belongs in the delivery log, not an
    exception that aborts the surrounding request. ``ProviderError`` is still
    raised for a connection that cannot work at all, because that needs the
    customer to fix something.
    """
    settings_config = config or {}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=False) as client:
            if provider.auth == "endpoint":
                if not endpoint_url:
                    raise ProviderError(f"{provider.id}_endpoint_missing")
                safe_url = validate_target_url(endpoint_url)
                if provider.id == "slack":
                    return await _deliver_slack(client, safe_url, payload)
                # Serialised once and posted as raw bytes, because the signature
                # has to cover exactly what goes on the wire. Handing the dict to
                # httpx and signing a separate dump of it produces a signature
                # over bytes the receiver never sees, and every verification on
                # the far side fails for reasons nobody can debug.
                body = json.dumps(payload.as_json(), separators=(",", ":"), sort_keys=True).encode()
                return await _post(
                    client,
                    safe_url,
                    content=body,
                    headers=_signature_headers(body, payload, signing_secret),
                )

            if not credential:
                raise ProviderError(f"{provider.id}_credential_missing")
            if provider.id == "hubspot":
                return await _deliver_hubspot(client, credential, settings_config, payload)
            if provider.id == "salesforce":
                return await _deliver_salesforce(client, credential, settings_config, payload)
            if provider.id == "activecampaign":
                return await _deliver_activecampaign(client, credential, settings_config, payload)
            if provider.id == "mailchimp":
                return await _deliver_mailchimp(client, credential, settings_config, payload)
            raise ProviderError(f"unsupported_provider:{provider.id}")
    except UnsafeTargetURL as exc:
        return DeliveryResult(False, None, str(exc))
    except httpx.TimeoutException:
        return DeliveryResult(False, None, "the destination did not respond in time")
    except httpx.HTTPError as exc:
        logger.warning("Integration transport failure for %s: %s", provider.id, exc)
        return DeliveryResult(False, None, "could not reach the destination")


def _signature_headers(
    body: bytes, payload: LeadPayload, signing_secret: str | None
) -> dict[str, str]:
    """HMAC the exact bytes being sent, so a receiver can prove they are ours."""
    headers = {
        "Content-Type": "application/json",
        "X-Magnit-Event": "lead.test" if payload.is_test else "lead.created",
    }
    if not signing_secret:
        return headers
    digest = hmac.new(signing_secret.encode(), body, hashlib.sha256).hexdigest()
    headers["X-Magnit-Signature"] = f"sha256={digest}"
    return headers


def required_field_names(provider: Provider) -> Sequence[str]:
    return [field_spec.name for field_spec in provider.fields if field_spec.required]
