import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWorkspaceRoute } from "@/test/workspace";

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  del: vi.fn(),
}));

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

// The route reads its own params, so it is mounted at a fixed id below.
vi.mock("@tanstack/react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-router")>();
  return actual;
});

const { Route } = await import("./leads_.$leadId");
const LeadDetailRoute = Route.options.component as React.FunctionComponent;

const DETAIL = {
  lead: {
    id: "l1",
    widget_id: "w1",
    email: "priya.sharma@technova.example",
    name: "Priya Sharma",
    score: 86,
    answers: { company_size: "11-50 employees", online_booking: true },
    metadata: null,
    qualification_status: null,
    result_key: "high",
    forwarded: true,
    forwarded_at: "2026-07-20T10:30:00Z",
    created_at: "2026-07-20T10:24:00Z",
    status: "new",
    tags: ["high intent"],
    contacted_at: null,
    note_count: 1,
  },
  widget_title: "Practice Readiness Check",
  widget_id: "w1",
  notes: [{ id: "n1", body: "Spoke on the phone.", created_at: "2026-07-20T11:10:00Z" }],
  timeline: [
    {
      kind: "delivered",
      title: "Delivery failed",
      detail: "invalid_token",
      occurred_at: "2026-07-20T10:31:00Z",
      tone: "failed",
    },
    {
      kind: "captured",
      title: "Lead captured",
      detail: 'Completed "Practice Readiness Check".',
      occurred_at: "2026-07-20T10:24:00Z",
      tone: "ok",
    },
  ],
  // Two destinations with different outcomes: the owner's alert landed, the
  // CRM did not. "We captured it" and "your CRM has it" are separate claims and
  // the screen has to keep them separate.
  deliveries: [
    {
      id: "d1",
      channel: "owner_email",
      provider: null,
      status: "delivered",
      attempts: 1,
      last_error: null,
      next_attempt_at: null,
      delivered_at: "2026-07-20T10:25:00Z",
      retryable: false,
    },
    {
      id: "d2",
      channel: "integration",
      provider: "hubspot",
      status: "failed",
      attempts: 5,
      last_error: "invalid_token",
      next_attempt_at: null,
      delivered_at: null,
      retryable: true,
    },
  ],
};

const ENTITLEMENTS = {
  plan: { id: "studio", name: "Studio", live_tool_limit: 3, monthly_build_limit: 25 },
  status: "active",
  usage: { live_tools: 1, total_tools: 1, builds_this_period: 0 },
  allowance: { builds_remaining: 25, live_tools_remaining: 2, can_build: true, can_publish: true },
  features: ["lead_pipeline"],
  period_started_at: "2026-07-01T00:00:00Z",
  current_period_end: null,
  granted_widget_ids: [],
};

function routes(path: string) {
  if (path.includes("/detail")) return Promise.resolve(DETAIL);
  if (path.includes("/entitlements")) return Promise.resolve(ENTITLEMENTS);
  if (path.includes("/billing/plans")) return Promise.resolve({ plans: [], currency: "usd" });
  return Promise.resolve({});
}

const AT = "/dashboard/leads_/$leadId";

describe("lead detail route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.get.mockImplementation(routes);
  });

  it("shows who the lead is and which tool captured them", async () => {
    renderWorkspaceRoute(LeadDetailRoute, AT);
    expect(await screen.findByText("priya.sharma@technova.example")).toBeInTheDocument();
    expect(screen.getByText("Practice Readiness Check")).toBeInTheDocument();
  });

  it("renders the timeline the server assembled", async () => {
    renderWorkspaceRoute(LeadDetailRoute, AT);
    expect(await screen.findByText("Lead captured")).toBeInTheDocument();
    // A failed delivery has to be visibly different from a successful one.
    expect(screen.getByText("Delivery failed")).toBeInTheDocument();
    expect(screen.getByText("invalid_token")).toBeInTheDocument();
  });

  it("shows the score and the answers behind it", async () => {
    renderWorkspaceRoute(LeadDetailRoute, AT);
    expect(await screen.findByText("86")).toBeInTheDocument();
    expect(screen.getByText("11-50 employees")).toBeInTheDocument();
    // A yes/no answer reads as the visitor gave it, not as the database
    // stored it.
    expect(screen.getByText("Yes")).toBeInTheDocument();
    expect(screen.queryByText("true")).not.toBeInTheDocument();
  });

  it("moves the lead along the pipeline", async () => {
    const user = userEvent.setup();
    mocks.patch.mockResolvedValue({ ...DETAIL.lead, status: "qualified" });
    renderWorkspaceRoute(LeadDetailRoute, AT);

    await user.click(await screen.findByRole("button", { name: "Qualified" }));

    await waitFor(() => expect(mocks.patch).toHaveBeenCalled());
    expect(mocks.patch.mock.calls[0][1].status).toBe("qualified");
  });

  it("adds a note", async () => {
    const user = userEvent.setup();
    mocks.post.mockResolvedValue({ id: "n2", body: "Left a voicemail", created_at: "x" });
    renderWorkspaceRoute(LeadDetailRoute, AT);

    await user.type(await screen.findByLabelText(/add a note/i), "Left a voicemail");
    await user.click(screen.getByRole("button", { name: /add note/i }));

    await waitFor(() => expect(mocks.post).toHaveBeenCalled());
    expect(mocks.post.mock.calls[0][1].body).toBe("Left a voicemail");
  });

  it("says where the lead reached and where it did not", async () => {
    /*
     * "We captured it" and "your CRM has it" are different claims. A business
     * that relies on the second one has to be able to see which is true — a
     * single `forwarded` boolean could not tell them, and neither could a
     * delivery that failed in silence.
     */
    renderWorkspaceRoute(LeadDetailRoute, AT);

    expect(await screen.findByText("Delivered to")).toBeInTheDocument();
    expect(screen.getByText("hubspot")).toBeInTheDocument();
    expect(screen.getByText(/failed after 5 attempts/i)).toBeInTheDocument();
    expect(screen.getByText("Delivered")).toBeInTheDocument();
  });

  it("does not print the provider's error twice on one screen", async () => {
    // The timeline is the chronology and owns the reason; the panel is the
    // current state and owns the action. Saying it in both places is how a
    // screen starts reading as noise rather than as an answer.
    renderWorkspaceRoute(LeadDetailRoute, AT);

    await screen.findByText("Delivered to");
    expect(screen.getAllByText("invalid_token")).toHaveLength(1);
  });

  it("offers another attempt only once the automatic ones are spent", async () => {
    const user = userEvent.setup();
    mocks.post.mockResolvedValue({ ...DETAIL.deliveries[1], status: "pending", attempts: 0 });
    renderWorkspaceRoute(LeadDetailRoute, AT);

    // One retry button, for the one delivery that has stopped trying.
    const retry = await screen.findByRole("button", { name: /retry/i });
    await user.click(retry);

    await waitFor(() => expect(mocks.post).toHaveBeenCalled());
    // The lead id comes from the route params, which this harness leaves
    // unresolved; what matters is that the right delivery is the one retried.
    expect(mocks.post.mock.calls[0][0]).toMatch(/\/deliveries\/d2\/retry$/);
  });

  it("marks a new lead contacted when the owner emails them", async () => {
    /*
     * Opening the mail client and recording the follow-up are the same act.
     * Apart, the pipeline only reflected the follow-ups someone remembered to
     * log by hand — so "New" stopped meaning anything and the queue stopped
     * being worth opening.
     */
    const user = userEvent.setup();
    mocks.patch.mockResolvedValue({ ...DETAIL.lead, status: "contacted" });
    renderWorkspaceRoute(LeadDetailRoute, AT);

    await user.click(await screen.findByRole("link", { name: /email them/i }));

    await waitFor(() => expect(mocks.patch).toHaveBeenCalled());
    expect(mocks.patch.mock.calls[0][1].status).toBe("contacted");
  });

  it("hides the pipeline controls when the plan excludes them", async () => {
    mocks.get.mockImplementation((path: string) => {
      if (path.includes("/entitlements")) {
        return Promise.resolve({ ...ENTITLEMENTS, features: [] });
      }
      return routes(path);
    });

    renderWorkspaceRoute(LeadDetailRoute, AT);

    // The lead itself stays readable — only the follow-up tools are gated.
    expect(await screen.findByText("priya.sharma@technova.example")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Qualified" })).not.toBeInTheDocument();
  });
});
