import { screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { saveJourney, type SavedJourney } from "@/lib/journey-storage";
import { renderWorkspaceRoute } from "@/test/workspace";

/** As in leads.test.tsx: mock the HTTP layer so React Query stays real. */
const mocks = vi.hoisted(() => ({ get: vi.fn() }));

vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-client")>();
  return { ...actual, api: { ...actual.api, get: mocks.get } };
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

const { Route } = await import("./index");
const DashboardRoute = Route.options.component as React.FunctionComponent;

function widget(over: Record<string, unknown> = {}) {
  return {
    id: "w1",
    title: "Revenue Calculator",
    widget_type: "calculator",
    status: "active",
    target_url: "https://example.com",
    deployment_url: "https://w1.vercel.app",
    embed_code: "<iframe></iframe>",
    leads_count: 12,
    impressions_count: 400,
    starts_count: 100,
    completions_count: 40,
    cta_clicks_count: 10,
    conversion_rate: 12.5,
    plan_tier: "studio",
    lead_cap: 1000,
    entitlement_status: "paid",
    can_build: true,
    launch_settings: null,
    delivery_webhook_url: null,
    consent_text: null,
    creation_brief: null,
    brand_tokens: null,
    visual_language: null,
    widget_logic: null,
    copywriting: null,
    design_tokens: null,
    build_stage: null,
    build_progress: null,
    build_error: null,
    created_at: "2026-06-01T00:00:00Z",
    deployed_at: "2026-06-02T00:00:00Z",
    last_heal_check_at: null,
    last_brand_check_at: null,
    ...over,
  };
}

function respond(widgets: unknown[]) {
  mocks.get.mockImplementation((path: string) => {
    if (path.startsWith("/api/widgets/portfolio/analytics"))
      return Promise.resolve({ daily: [], totals: null });
    if (path === "/api/widgets") return Promise.resolve({ widgets });
    if (path === "/api/payments/subscription") return Promise.resolve(null);
    return Promise.resolve(null);
  });
}

describe("dashboard overview route", () => {
  beforeEach(() => {
    mocks.get.mockReset();
    saveJourney(null);
  });

  it("renders each tool as a link to its own page, with its all-time numbers", async () => {
    respond([widget()]);
    renderWorkspaceRoute(DashboardRoute, "/dashboard");

    // The title appears twice by design — once on the branded canvas, once as
    // the card's label — so the link is the unambiguous handle on the card.
    const card = await screen.findByRole("link", { name: /Revenue Calculator/ });
    expect(card).toHaveAttribute("href", "/dashboard/widgets/w1");

    expect(within(card).getByText("400")).toBeInTheDocument(); // views
    expect(within(card).getByText("12")).toBeInTheDocument(); // leads
    expect(within(card).getByText("12.5%")).toBeInTheDocument(); // lead rate
  });

  it("summarises how many tools are live", async () => {
    respond([widget(), widget({ id: "w2", title: "Growth Quiz", status: "draft" })]);
    renderWorkspaceRoute(DashboardRoute, "/dashboard");

    expect(await screen.findByText(/1 of 2 tools live/i)).toBeInTheDocument();
  });

  it("invites a first website when nothing is built", async () => {
    respond([]);
    renderWorkspaceRoute(DashboardRoute, "/dashboard");

    expect(await screen.findByText(/start with your website/i)).toBeInTheDocument();
  });

  /**
   * A failed widgets call must say so. Rendering an empty workspace instead
   * would tell an owner their tools are gone, which is worse than an error.
   */
  it("reports a failure instead of pretending the workspace is empty", async () => {
    mocks.get.mockImplementation((path: string) => {
      if (path === "/api/widgets") return Promise.reject(new Error("Service unavailable"));
      return Promise.resolve(null);
    });

    renderWorkspaceRoute(DashboardRoute, "/dashboard");

    expect(await screen.findByText(/couldn't open your workspace/i)).toBeInTheDocument();
    expect(screen.queryByText(/start with your website/i)).not.toBeInTheDocument();
  });

  it("surfaces a build in progress", async () => {
    respond([widget({ status: "building", build_progress: 40, build_stage: "codegen" })]);
    renderWorkspaceRoute(DashboardRoute, "/dashboard");

    expect(await screen.findByText(/codegen/i)).toBeInTheDocument();
  });

  it("flags a tool that stopped responding", async () => {
    respond([widget({ status: "failed" })]);
    renderWorkspaceRoute(DashboardRoute, "/dashboard");

    expect(await screen.findByText(/stopped responding/i)).toBeInTheDocument();
  });

  it("shows the AI-selected result when a direct build reaches the dashboard", async () => {
    saveJourney({
      target_url: "https://northsidedental.com",
      session_token: "saved-session",
      selectedIndex: 0,
      widgetId: "w-ai",
      brief: {
        mode: "autopilot",
        intent: "",
        audience: "",
        goal: "capture_qualified_leads",
        offer: "",
        visitor_question: "",
        preferred_type: null,
        tone: "match_site",
        result_style: "recommendation",
        question_count: 4,
        instructions: "",
      },
      concepts: [
        {
          blueprint: {
            type: "roi_calculator",
            title: "Treatment Cost Planner",
            description: "A clear planning experience for prospective patients.",
            rationale: "Answers the highest-intent question.",
          },
          architect: {
            widget_type: "roi_calculator",
            brand: {
              primary_color: "#101014",
              secondary_color: "#3b3b44",
              background_color: "#f5f4f0",
              accent_color: "#b8e430",
              font_headings: "Geist",
              font_body: "Geist",
              tone: "direct",
              logo_url: null,
            },
            visual_language: {
              layout: "centered",
              spacing: "roomy",
              card_style: "soft",
              border_radius: "16px",
              shadow_depth: "low",
              button_style: "solid",
              decorative_elements: "none",
              icon_style: "line",
              visual_energy: "calm",
            },
            logic: { formula: "x", variables: [], example_calculation: "e" },
            copywriting: { headline: "Plan your treatment with confidence" },
            decision: null,
            claims: [],
          },
        },
        {
          blueprint: {
            type: "readiness_quiz",
            title: "Treatment Readiness Quiz",
            description: "A second direction.",
            rationale: "Builds confidence.",
          },
          architect: {
            widget_type: "readiness_quiz",
            brand: {
              primary_color: "#101014",
              secondary_color: "#3b3b44",
              background_color: "#f5f4f0",
              accent_color: "#b8e430",
              font_headings: "Geist",
              font_body: "Geist",
              tone: "direct",
              logo_url: null,
            },
            visual_language: {
              layout: "centered",
              spacing: "roomy",
              card_style: "soft",
              border_radius: "16px",
              shadow_depth: "low",
              button_style: "solid",
              decorative_elements: "none",
              icon_style: "line",
              visual_energy: "calm",
            },
            logic: { formula: "x", variables: [], example_calculation: "e" },
            copywriting: { headline: "Are you ready?" },
            decision: null,
            claims: [],
          },
        },
      ],
    } as SavedJourney);
    respond([
      widget({
        id: "w-ai",
        title: "Treatment Cost Planner",
        status: "analyzed",
        widget_type: "roi_calculator",
        target_url: "https://northsidedental.com",
        deployment_url: null,
      }),
    ]);

    renderWorkspaceRoute(DashboardRoute, "/dashboard");

    expect(await screen.findByText(/your ai-built direction is ready/i)).toBeInTheDocument();
    expect(
      screen.getByText(/saved in your workspace for northsidedental\.com/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /treatment cost planner/i })).toHaveAttribute(
      "href",
      "/dashboard/widgets/w-ai",
    );
    expect(screen.getByRole("link", { name: /review and continue/i })).toHaveAttribute(
      "href",
      "/build",
    );
  });
});
