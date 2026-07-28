import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";
import { renderWorkspaceRoute } from "@/test/workspace";

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  put: vi.fn(),
}));

vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-client")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      get: mocks.get,
      put: mocks.put,
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

const BRAND = {
  accent_color: "#45604F",
  background_color: null,
  font_pairing: "inter_inter",
  corner_radius: 12,
  tone: "soft" as const,
  logo_url: null,
  brand_personality: "Calm and clear",
  configured: true,
  font_pairings: [
    {
      id: "inter_fraunces",
      label: "Inter + Fraunces",
      heading: "Fraunces",
      body: "Inter",
      note: "Clean and modern",
    },
    {
      id: "inter_inter",
      label: "Inter",
      heading: "Inter",
      body: "Inter",
      note: "Neutral, gets out of the way",
    },
  ],
};

const ENTITLEMENTS = {
  plan: { id: "studio", name: "Studio", live_tool_limit: 3, monthly_build_limit: 20 },
  status: "active",
  usage: { live_tools: 1, total_tools: 2, builds_this_period: 4 },
  allowance: { builds_remaining: 16, live_tools_remaining: 2, can_build: true, can_publish: true },
  features: ["brand_kit"],
  period_started_at: "2026-07-01T00:00:00Z",
  current_period_end: null,
  granted_widget_ids: [],
};

function respond() {
  mocks.get.mockImplementation((path: string) => {
    if (path === "/api/users/me/brand") return Promise.resolve(BRAND);
    if (path === "/api/billing/entitlements") return Promise.resolve(ENTITLEMENTS);
    if (path === "/api/billing/plans") {
      return Promise.resolve({
        plans: [
          {
            id: "studio",
            name: "Studio",
            live_tool_limit: 3,
            monthly_build_limit: 20,
          },
        ],
        currency: "usd",
      });
    }
    return Promise.resolve({});
  });
}

const { Route } = await import("./brand");
const BrandRoute = Route.options.component as React.FunctionComponent;

describe("brand studio route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    respond();
  });

  it("surfaces every supported brand decision and explains the website fallback", async () => {
    const user = userEvent.setup();
    renderWorkspaceRoute(BrandRoute, "/dashboard/brand");

    expect(await screen.findByRole("heading", { name: "Colour system" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /type pinned/i }));
    expect(screen.getByRole("heading", { name: "Typography" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /shape pinned/i }));
    expect(screen.getByRole("heading", { name: "Shape" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /logo following website/i }));
    expect(screen.getByRole("heading", { name: "Logo" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /voice pinned/i }));
    expect(screen.getByRole("heading", { name: "Voice direction" })).toBeInTheDocument();

    expect(screen.getByText(/5\/6 choices pinned/i)).toBeInTheDocument();
    expect(screen.getByText(/unpinned choices come from the source website/i)).toBeInTheDocument();
  });

  it("has no automated WCAG A or AA violations", async () => {
    const { container } = renderWorkspaceRoute(BrandRoute, "/dashboard/brand");
    await screen.findByRole("heading", { name: "Colour system" });
    await expectNoA11yViolations(container);
  });

  it("shows all three real tool moments in the live preview", async () => {
    const user = userEvent.setup();
    renderWorkspaceRoute(BrandRoute, "/dashboard/brand");

    expect(
      await screen.findByText(/what is the biggest constraint on your growth/i),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Result" }));
    expect(screen.getByText(/strong foundation for scalable growth/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Lead capture" }));
    expect(
      screen.getByText(/where should we send your personalised recommendations/i),
    ).toBeInTheDocument();
  });

  it("blocks an invalid colour before it can reach the API", async () => {
    const user = userEvent.setup();
    renderWorkspaceRoute(BrandRoute, "/dashboard/brand");

    const accent = await screen.findByLabelText("Action colour hex");
    await user.clear(accent);
    await user.type(accent, "forest");

    expect(screen.getByRole("alert")).toHaveTextContent(/3- or 6-digit hex colour/i);
    expect(screen.getByRole("button", { name: /^save$/i })).toBeDisabled();
    expect(mocks.put).not.toHaveBeenCalled();
  });

  it("saves the complete house-style draft after a visual change", async () => {
    const user = userEvent.setup();
    mocks.put.mockResolvedValue({ ...BRAND, accent_color: "#B65C3A" });
    renderWorkspaceRoute(BrandRoute, "/dashboard/brand");

    await user.click(await screen.findByRole("button", { name: "Use Clay #B65C3A" }));
    await user.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() =>
      expect(mocks.put).toHaveBeenCalledWith("/api/users/me/brand", {
        accent_color: "#B65C3A",
        background_color: null,
        font_pairing: "inter_inter",
        corner_radius: 12,
        tone: "soft",
        logo_url: null,
        brand_personality: "Calm and clear",
      }),
    );
    expect(await screen.findByText("Brand saved")).toBeInTheDocument();
  });

  it("can hand every decision back to the source website without saving immediately", async () => {
    const user = userEvent.setup();
    renderWorkspaceRoute(BrandRoute, "/dashboard/brand");

    await user.click(await screen.findByRole("button", { name: /follow website for everything/i }));

    expect(screen.getByText(/0\/6 choices pinned/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^save$/i })).toBeEnabled();
    expect(mocks.put).not.toHaveBeenCalled();
  });
});
