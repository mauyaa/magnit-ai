import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";
import { renderWorkspaceRoute } from "@/test/workspace";

/**
 * The screen an owner opens to answer one question: is this tool working?
 *
 * Mocked at the HTTP layer rather than at the hooks, so React Query stays real
 * and the loading-to-loaded transition is the real one. The tab lives in the
 * URL, so each tab is mounted at its own path rather than clicked into — that is
 * how a shared link arrives, and it is the case most likely to break.
 */
const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn() }));

vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-client")>();
  return { ...actual, api: { ...actual.api, ...mocks } };
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

const { Route } = await import("./$widgetId");
const WidgetDetailRoute = Route.options.component as React.FunctionComponent;

const WIDGET_ID = "w1";
const PATH = "/dashboard/widgets/$widgetId";

function widget(over: Record<string, unknown> = {}) {
  return {
    id: WIDGET_ID,
    title: "Recovered bookings calculator",
    target_url: "https://northside.example/",
    widget_type: "roi_calculator",
    status: "active",
    deployment_url: "https://magai-widget-abcdef12.vercel.app",
    embed_code: '<iframe src="https://magai-widget-abcdef12.vercel.app"></iframe>',
    leads_count: 1,
    // The live panel falls back to these while the funnel query is in flight,
    // so omitting them crashes the overview on first paint rather than later.
    impressions_count: 120,
    starts_count: 64,
    completions_count: 40,
    cta_clicks_count: 7,
    build_stage: null,
    build_progress: null,
    build_error: null,
    created_at: "2026-06-01T00:00:00Z",
    ...over,
  };
}

const READINESS = {
  ready: true,
  completed: 3,
  total: 3,
  checks: [
    {
      id: "published",
      label: "Published",
      detail: "The tool is live at its own address.",
      done: true,
      action: "",
      blocking: true,
    },
    {
      id: "embedded",
      label: "Embedded",
      detail: "The snippet is on your site.",
      done: true,
      action: "",
      blocking: true,
    },
    {
      id: "capture",
      label: "Capturing leads",
      detail: "Lead capture is switched on.",
      done: true,
      action: "",
      blocking: false,
    },
  ],
};

function healEvent(over: Record<string, unknown> = {}) {
  return {
    id: "h1",
    check_type: "brand_drift",
    status: "healed",
    diff_summary: { primary_color: { old: "#17324d", new: "#0b5cd5" } },
    detected_at: "2026-07-01T09:00:00Z",
    healed_at: "2026-07-01T09:04:00Z",
    ...over,
  };
}

function lead(over: Record<string, unknown> = {}) {
  return {
    id: "l1",
    widget_id: WIDGET_ID,
    email: "ada@example.com",
    name: "Ada Lovelace",
    score: 82,
    answers: { monthly_patients: 25 },
    metadata: null,
    qualification_status: "qualified",
    result_key: "high",
    forwarded: false,
    forwarded_at: null,
    created_at: "2026-07-02T10:00:00Z",
    ...over,
  };
}

/**
 * Answer every GET the screen and its shell make.
 *
 * Matched on path *shape*, not on a literal id: the ad-hoc test router mounts
 * the route at its declared path, so `useParams` yields the literal "$widgetId"
 * and the requests go to `/api/widgets/$widgetId/...`. Keying on the real id
 * would silently fall through to the collection endpoint and hand the screen an
 * array where it expects one tool.
 */
const DETAIL_PATH = /^\/api\/widgets\/[^/]+$/;

function respondWith({
  detail = widget(),
  leads = [] as unknown[],
  heals = [] as unknown[],
  deployments = [] as unknown[],
  funnel = { views: 120, starts: 64, completions: 40, leads: 12, cta_clicks: 7 },
}: Record<string, unknown> = {}) {
  mocks.get.mockImplementation((path: string) => {
    const [route] = path.split("?");
    if (route.endsWith("/heal-events")) return Promise.resolve(heals);
    if (route.endsWith("/deployments")) return Promise.resolve(deployments);
    if (route.endsWith("/funnel")) return Promise.resolve(funnel);
    if (route.endsWith("/leads")) return Promise.resolve(leads);
    if (route.endsWith("/readiness")) return Promise.resolve(READINESS);
    if (route.includes("/entitlements")) return Promise.resolve(ENTITLEMENTS);
    if (route.includes("/plans")) return Promise.resolve([PLAN]);
    if (DETAIL_PATH.test(route)) return Promise.resolve(detail);
    if (route.includes("/widgets")) return Promise.resolve([detail]);
    return Promise.resolve({});
  });
}

/**
 * The shell's sidebar renders usage meters straight from the plan, so a partial
 * plan object crashes every screen inside it rather than the one under test.
 */
const PLAN = {
  id: "scale",
  name: "Scale",
  tagline: "For teams",
  monthly_price: 19900,
  currency: "usd",
  live_tool_limit: 10,
  monthly_build_limit: 50,
  lead_limit_per_tool: 5000,
  analytics_window_days: 365,
  features: ["self_healing", "outcome_editor", "question_editor", "lead_capture", "custom_domains"],
  highlights: [],
  purchasable: true,
};

const ENTITLEMENTS = {
  plan: PLAN,
  status: "active",
  usage: { live_tools: 1, total_tools: 1, builds_this_period: 1 },
  allowance: {
    builds_remaining: 49,
    live_tools_remaining: 9,
    can_build: true,
    can_publish: true,
  },
  features: PLAN.features,
  period_started_at: "2026-07-01T00:00:00Z",
  current_period_end: "2026-08-01T00:00:00Z",
  granted_widget_ids: [WIDGET_ID],
};

beforeEach(() => {
  vi.clearAllMocks();
  respondWith();
});

describe("widget detail · overview", () => {
  it("leads with the tool's name, address and live status", async () => {
    renderWorkspaceRoute(WidgetDetailRoute, PATH);

    expect(
      await screen.findByRole("heading", { name: /recovered bookings calculator/i }),
    ).toBeInTheDocument();
    expect(await screen.findByText("Live")).toBeInTheDocument();
    // The scheme is stripped: the host is the identifying part.
    expect(screen.getByText("northside.example/")).toBeInTheDocument();
  });

  it("shows the funnel so the owner can see where visitors drop", async () => {
    renderWorkspaceRoute(WidgetDetailRoute, PATH);

    // "Viewed" and "CTA clicks" belong only to the funnel strip; the live
    // confirmation panel above it reuses Started/Finished/Leads, so those are
    // asserted as "at least one" rather than uniquely.
    expect(await screen.findByText("Viewed")).toBeInTheDocument();
    expect(await screen.findByText("CTA clicks")).toBeInTheDocument();
    for (const shared of ["Started", "Finished", "Leads"]) {
      expect(screen.getAllByText(shared).length).toBeGreaterThan(0);
    }
    expect(screen.getAllByText("120").length).toBeGreaterThan(0);
  });

  it("embeds the live tool in a sandboxed frame", async () => {
    const { container } = renderWorkspaceRoute(WidgetDetailRoute, PATH);

    await screen.findByText("Live");
    const frame = container.querySelector("iframe");
    expect(frame).toHaveAttribute("src", "https://magai-widget-abcdef12.vercel.app");
    // Without the sandbox, generated code runs with full rights on our origin.
    expect(frame).toHaveAttribute("sandbox", "allow-scripts allow-same-origin allow-forms");
  });

  it("reports build progress instead of a preview while it is still building", async () => {
    respondWith({
      detail: widget({
        status: "building",
        deployment_url: null,
        build_stage: "codegen",
        build_progress: 65,
      }),
    });
    renderWorkspaceRoute(WidgetDetailRoute, PATH);

    expect(await screen.findByText("Still building")).toBeInTheDocument();
    expect(await screen.findByText(/codegen · 65%/i)).toBeInTheDocument();
  });

  it("offers a way forward when the tool was never published", async () => {
    respondWith({ detail: widget({ status: "analyzed", deployment_url: null }) });
    renderWorkspaceRoute(WidgetDetailRoute, PATH);

    expect(await screen.findByText("Not published yet")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /continue building/i })).toBeInTheDocument();
  });

  it("marks a failed build as needing attention", async () => {
    respondWith({ detail: widget({ status: "failed", deployment_url: null }) });
    renderWorkspaceRoute(WidgetDetailRoute, PATH);

    expect(await screen.findByText("Needs attention")).toBeInTheDocument();
  });

  it("says it could not find a tool that does not exist", async () => {
    mocks.get.mockRejectedValue(new Error("not found"));
    renderWorkspaceRoute(WidgetDetailRoute, PATH);

    expect(await screen.findByText(/couldn't find that tool/i)).toBeInTheDocument();
  });
});

describe("widget detail · activity", () => {
  it("describes a repair by what happened, not by its status code", async () => {
    respondWith({ heals: [healEvent()] });
    renderWorkspaceRoute(WidgetDetailRoute, PATH, `${PATH}?tab=activity`);

    expect(await screen.findByText("Their site changed")).toBeInTheDocument();
    expect(screen.getByText(/auto-repaired/i)).toBeInTheDocument();
  });

  it("shows the old and new values as the evidence of drift", async () => {
    respondWith({ heals: [healEvent()] });
    renderWorkspaceRoute(WidgetDetailRoute, PATH, `${PATH}?tab=activity`);

    expect(await screen.findByText("#17324d")).toBeInTheDocument();
    expect(screen.getByText("#0b5cd5")).toBeInTheDocument();
    expect(screen.getByText("primary color")).toBeInTheDocument();
  });

  it("flags a failed repair as needing a person", async () => {
    respondWith({
      heals: [
        healEvent({
          status: "failed",
          healed_at: null,
          diff_summary: { error: "no saved build artifacts to redeploy" },
        }),
      ],
    });
    renderWorkspaceRoute(WidgetDetailRoute, PATH, `${PATH}?tab=activity`);

    expect(await screen.findByText(/manual review/i)).toBeInTheDocument();
  });

  it("hides routine no-drift checks so the timeline stays meaningful", async () => {
    respondWith({
      heals: [healEvent({ id: "h2", status: "no_drift", diff_summary: null }), healEvent()],
    });
    renderWorkspaceRoute(WidgetDetailRoute, PATH, `${PATH}?tab=activity`);

    await screen.findByText("Their site changed");
    // One event rendered, not two: the quiet check is not news.
    expect(screen.getAllByText("Their site changed")).toHaveLength(1);
  });

  it("reassures rather than looking broken when nothing has needed fixing", async () => {
    respondWith({ heals: [] });
    renderWorkspaceRoute(WidgetDetailRoute, PATH, `${PATH}?tab=activity`);

    expect(await screen.findByText(/nothing has needed repairing/i)).toBeInTheDocument();
  });
});

describe("widget detail · leads", () => {
  it("lists captured leads and links each one to its detail", async () => {
    respondWith({ leads: [lead()] });
    renderWorkspaceRoute(WidgetDetailRoute, PATH, `${PATH}?tab=leads`);

    const link = await screen.findByRole("link", { name: "ada@example.com" });
    expect(link).toHaveAttribute("href", "/dashboard/leads/l1");
  });

  it("keeps the answers behind a disclosure rather than flooding the row", async () => {
    respondWith({ leads: [lead()] });
    renderWorkspaceRoute(WidgetDetailRoute, PATH, `${PATH}?tab=leads`);

    const summary = await screen.findByText("View answers");
    await userEvent.click(summary);

    expect(screen.getByText("monthly patients")).toBeInTheDocument();
    expect(screen.getByText("25")).toBeInTheDocument();
  });

  it("explains the empty state instead of showing a bare table", async () => {
    respondWith({ leads: [] });
    renderWorkspaceRoute(WidgetDetailRoute, PATH, `${PATH}?tab=leads`);

    expect(await screen.findByText("No leads yet")).toBeInTheDocument();
  });
});

describe("widget detail · maintenance", () => {
  it("republishes the last build on request", async () => {
    mocks.post.mockResolvedValue({ status: "queued" });
    renderWorkspaceRoute(WidgetDetailRoute, PATH, `${PATH}?tab=settings`);

    await userEvent.click(await screen.findByRole("button", { name: /^republish$/i }));

    await waitFor(() =>
      expect(mocks.post).toHaveBeenCalledWith(`/api/widgets/${WIDGET_ID}/deploy`),
    );
  });

  it("offers a revert only when there is an earlier version to revert to", async () => {
    respondWith({ deployments: [{ id: "d1", url: "https://old.vercel.app", is_current: true }] });
    renderWorkspaceRoute(WidgetDetailRoute, PATH, `${PATH}?tab=settings`);

    await screen.findByRole("button", { name: /^republish$/i });
    expect(screen.queryByRole("button", { name: /revert/i })).not.toBeInTheDocument();
  });

  it("reverts to the previous deployment when one exists", async () => {
    respondWith({
      deployments: [
        { id: "d1", url: "https://old.vercel.app", is_current: false },
        { id: "d2", url: "https://new.vercel.app", is_current: true },
      ],
    });
    mocks.post.mockResolvedValue({ status: "queued" });
    renderWorkspaceRoute(WidgetDetailRoute, PATH, `${PATH}?tab=settings`);

    await userEvent.click(await screen.findByRole("button", { name: /revert/i }));

    await waitFor(() =>
      expect(mocks.post).toHaveBeenCalledWith(`/api/widgets/${WIDGET_ID}/rollback`),
    );
  });

  it("surfaces the server's reason when republishing fails", async () => {
    mocks.post.mockRejectedValue(new Error("Vercel deploy failed: 402"));
    renderWorkspaceRoute(WidgetDetailRoute, PATH, `${PATH}?tab=settings`);

    await userEvent.click(await screen.findByRole("button", { name: /^republish$/i }));

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/vercel deploy failed: 402/i)).toBeInTheDocument();
  });
});

describe("widget detail · embed", () => {
  it("hands over the snippet to paste into the host page", async () => {
    renderWorkspaceRoute(WidgetDetailRoute, PATH, `${PATH}?tab=embed`);

    expect(await screen.findByText(/magai-widget-abcdef12\.vercel\.app/)).toBeInTheDocument();
  });
});

describe("widget detail · accessibility", () => {
  it("has no violations on the overview", async () => {
    // Checked in the unpublished state: axe cannot reach into the live-preview
    // iframe under jsdom ("Respondable target must be a frame in the current
    // window"), and the iframe's own contents are a separately deployed page
    // that this suite could not audit meaningfully anyway.
    respondWith({ detail: widget({ status: "analyzed", deployment_url: null }) });
    const { container } = renderWorkspaceRoute(WidgetDetailRoute, PATH);

    await screen.findByRole("heading", { name: /recovered bookings calculator/i });
    await expectNoA11yViolations(container);
  });

  it("has no violations on the activity timeline", async () => {
    respondWith({ heals: [healEvent()] });
    const { container } = renderWorkspaceRoute(WidgetDetailRoute, PATH, `${PATH}?tab=activity`);

    await screen.findByText("Their site changed");
    await expectNoA11yViolations(container);
  });
});
