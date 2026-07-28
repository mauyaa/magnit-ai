import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWorkspaceRoute } from "@/test/workspace";

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn(), del: vi.fn() }));

vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-client")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      get: mocks.get,
      post: mocks.post,
      patch: mocks.patch,
      delete: mocks.del,
    },
  };
});

vi.mock("@/lib/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/auth")>();
  return {
    ...actual,
    useAuth: () => ({
      user: {
        id: "u1",
        email: "founder@magnitai.dev",
        role: "owner",
        created_at: "2026-01-01T00:00:00Z",
        email_verified: true,
        mfa_enabled: false,
        notify_on_lead: true,
      },
      isLoading: false,
      isAuthenticated: true,
      logout: vi.fn(),
      login: {} as never,
      signup: {} as never,
    }),
  };
});

const { Route } = await import("./integrations");
const IntegrationsRoute = Route.options.component as React.FunctionComponent;

const HUBSPOT = {
  id: "hubspot",
  name: "HubSpot",
  category: "CRM",
  description: "Create or update a contact for every lead.",
  auth: "api_key",
  setup_hint: "Create a private app with the contacts scope.",
  docs_url: "https://developers.hubspot.com",
  feature: "crm_integrations",
  available: true,
  fields: [
    {
      name: "access_token",
      label: "Private app token",
      help_text: "Settings → Integrations → Private Apps.",
      kind: "secret",
      required: true,
      placeholder: "pat-eu1-…",
    },
  ],
};

const ENTITLEMENTS = {
  plan: { id: "scale", name: "Scale", live_tool_limit: 10, monthly_build_limit: 100 },
  status: "active",
  usage: { live_tools: 2, total_tools: 3, builds_this_period: 4 },
  allowance: { builds_remaining: 96, live_tools_remaining: 8, can_build: true, can_publish: true },
  features: ["crm_integrations", "webhook_delivery"],
  period_started_at: "2026-07-01T00:00:00Z",
  current_period_end: null,
  granted_widget_ids: [],
};

function baseRoutes(connected: unknown[] = []) {
  return (path: string) => {
    if (path.includes("/integrations/catalog")) {
      return Promise.resolve({ providers: [HUBSPOT] });
    }
    if (path.startsWith("/api/integrations")) return Promise.resolve({ integrations: connected });
    if (path.includes("/entitlements")) return Promise.resolve(ENTITLEMENTS);
    if (path.includes("/billing/plans")) return Promise.resolve({ plans: [], currency: "usd" });
    if (path.includes("/widgets")) return Promise.resolve({ widgets: [] });
    return Promise.resolve({});
  };
}

describe("integrations route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.get.mockImplementation(baseRoutes());
  });

  it("lists providers from the server's catalogue", async () => {
    renderWorkspaceRoute(IntegrationsRoute, "/dashboard/integrations");
    expect(await screen.findByText("HubSpot")).toBeInTheDocument();
    expect(screen.getByText("CRM")).toBeInTheDocument();
  });

  it("builds the connect form from the provider's declared fields", async () => {
    const user = userEvent.setup();
    renderWorkspaceRoute(IntegrationsRoute, "/dashboard/integrations");

    await user.click(await screen.findByRole("button", { name: /connect/i }));

    // Rendered from the provider definition, so a new provider on the server
    // needs no matching frontend change.
    expect(await screen.findByText("Private app token")).toBeInTheDocument();
    expect(screen.getByText(/private apps/i)).toBeInTheDocument();
  });

  it("will not submit until every required field is filled", async () => {
    const user = userEvent.setup();
    renderWorkspaceRoute(IntegrationsRoute, "/dashboard/integrations");

    await user.click(await screen.findByRole("button", { name: /^connect$/i }));
    const dialog = await screen.findByRole("dialog");
    const submit = within(dialog).getByRole("button", { name: /^connect$/i });
    expect(submit).toBeDisabled();
  });

  it("sends the credential to the connect endpoint", async () => {
    const user = userEvent.setup();
    mocks.post.mockResolvedValue({ id: "i1", provider: "hubspot" });
    renderWorkspaceRoute(IntegrationsRoute, "/dashboard/integrations");

    await user.click(await screen.findByRole("button", { name: /^connect$/i }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText(/private app token/i), "pat-eu1-secret");
    await user.click(within(dialog).getByRole("button", { name: /^connect$/i }));

    await waitFor(() => expect(mocks.post).toHaveBeenCalled());
    const [path, body] = mocks.post.mock.calls[0];
    expect(path).toBe("/api/integrations");
    expect(body.provider).toBe("hubspot");
    expect(body.values.access_token).toBe("pat-eu1-secret");
  });

  it("shows a connected provider with its delivery counts and masked key", async () => {
    mocks.get.mockImplementation(
      baseRoutes([
        {
          id: "i1",
          provider: "hubspot",
          status: "connected",
          config: null,
          credential_hint: "••••1234",
          endpoint_url: null,
          widget_ids: null,
          last_test_at: null,
          last_status_code: null,
          last_error: null,
          delivered_count: 42,
          failed_count: 0,
          created_at: "2026-07-01T00:00:00Z",
        },
      ]),
    );

    renderWorkspaceRoute(IntegrationsRoute, "/dashboard/integrations");

    expect(await screen.findByText("42 delivered")).toBeInTheDocument();
    expect(screen.getByText(/••••1234/)).toBeInTheDocument();
  });

  it("surfaces the reason a connection is failing", async () => {
    mocks.get.mockImplementation(
      baseRoutes([
        {
          id: "i1",
          provider: "hubspot",
          status: "error",
          config: null,
          credential_hint: "••••1234",
          endpoint_url: null,
          widget_ids: null,
          last_test_at: "2026-07-20T00:00:00Z",
          last_status_code: 401,
          last_error: "invalid_token",
          delivered_count: 0,
          failed_count: 3,
          created_at: "2026-07-01T00:00:00Z",
        },
      ]),
    );

    renderWorkspaceRoute(IntegrationsRoute, "/dashboard/integrations");
    // The provider's own words, not "something went wrong" — it is the
    // difference between a customer fixing it and filing a ticket.
    expect(await screen.findByText("invalid_token")).toBeInTheDocument();
  });

  it("marks a provider the plan does not cover instead of hiding it", async () => {
    mocks.get.mockImplementation((path: string) => {
      if (path.includes("/integrations/catalog")) {
        return Promise.resolve({ providers: [{ ...HUBSPOT, available: false }] });
      }
      if (path.includes("/entitlements")) {
        return Promise.resolve({ ...ENTITLEMENTS, features: [] });
      }
      return baseRoutes()(path);
    });

    renderWorkspaceRoute(IntegrationsRoute, "/dashboard/integrations");

    expect(await screen.findByText("HubSpot")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^connect$/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /upgrade/i })).toBeInTheDocument();
  });
});
