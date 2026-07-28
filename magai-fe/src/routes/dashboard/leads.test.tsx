import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWorkspaceRoute } from "@/test/workspace";

/**
 * The HTTP layer is mocked rather than the `useAllLeads`/`useWidgets` hooks.
 *
 * That matters for the first test below: stubbing the hooks lets a test pick a
 * loading flag and hold it, whereas the crash this file guards against only
 * appears on the *transition* from loading to loaded. Mocking `api.get` keeps
 * React Query real, so the transition is the real one.
 */
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

const { Route } = await import("./leads");
const LeadsRoute = Route.options.component as React.FunctionComponent;

const WIDGET = {
  id: "w1",
  title: "Revenue Calculator",
  widget_type: "calculator",
  status: "deployed",
  leads_count: 2,
};

function lead(over: Partial<Record<string, unknown>> = {}) {
  return {
    id: "l1",
    widget_id: "w1",
    email: "ada@example.com",
    name: "Ada Lovelace",
    score: 82,
    answers: null,
    metadata: null,
    qualification_status: null,
    result_key: null,
    forwarded: false,
    forwarded_at: null,
    created_at: new Date().toISOString(),
    ...over,
  };
}

/** Routes the screen and its shell call, keyed by path suffix. */
function respondWith(leads: unknown[]) {
  mocks.get.mockImplementation((path: string) => {
    if (path === "/api/widgets") return Promise.resolve({ widgets: [WIDGET] });
    if (path.endsWith("/leads")) return Promise.resolve(leads);
    if (path === "/api/payments/subscription") return Promise.resolve(null);
    return Promise.resolve(null);
  });
}

describe("dashboard leads route", () => {
  beforeEach(() => {
    mocks.get.mockReset();
  });

  /**
   * The regression guard.
   *
   * `useState` for the selected-lead drawer sat *below* the `if (isLoading)`
   * early return, so the first render registered five hooks and the render
   * after the leads arrived registered six. React throws "Rendered more hooks
   * than during the previous render" and the page dies — every time, for any
   * account that owns at least one tool.
   */
  it("survives the loading to loaded transition", async () => {
    respondWith([lead()]);
    renderWorkspaceRoute(LeadsRoute, "/dashboard/leads");

    expect(await screen.findByText("ada@example.com")).toBeInTheDocument();
  });

  it("lists the captured leads", async () => {
    respondWith([lead(), lead({ id: "l2", email: "grace@example.com", name: "Grace Hopper" })]);
    renderWorkspaceRoute(LeadsRoute, "/dashboard/leads");

    expect(await screen.findByText("ada@example.com")).toBeInTheDocument();
    expect(screen.getByText("grace@example.com")).toBeInTheDocument();
    // The count in the description is what tells an owner the page is complete.
    expect(screen.getByText(/2 people have left their details/i)).toBeInTheDocument();
  });

  it("shows the empty state when no one has converted yet", async () => {
    respondWith([]);
    renderWorkspaceRoute(LeadsRoute, "/dashboard/leads");

    expect(await screen.findByText(/no leads yet/i)).toBeInTheDocument();
  });

  it("filters by the search box", async () => {
    respondWith([lead(), lead({ id: "l2", email: "grace@example.com", name: "Grace Hopper" })]);
    renderWorkspaceRoute(LeadsRoute, "/dashboard/leads");
    await screen.findByText("ada@example.com");

    await userEvent.type(screen.getByRole("searchbox", { name: /search leads/i }), "grace");

    await waitFor(() => expect(screen.queryByText("ada@example.com")).not.toBeInTheDocument());
    expect(screen.getByText("grace@example.com")).toBeInTheDocument();
  });

  /**
   * `useAllLeads` swallows per-widget failures with `Promise.allSettled`, so one
   * unreachable widget must not blank the whole table.
   */
  it("still renders the leads it could fetch when one widget fails", async () => {
    mocks.get.mockImplementation((path: string) => {
      if (path === "/api/widgets")
        return Promise.resolve({ widgets: [WIDGET, { ...WIDGET, id: "w2" }] });
      if (path === "/api/widgets/w1/leads") return Promise.resolve([lead()]);
      if (path === "/api/widgets/w2/leads") return Promise.reject(new Error("boom"));
      return Promise.resolve(null);
    });

    renderWorkspaceRoute(LeadsRoute, "/dashboard/leads");
    expect(await screen.findByText("ada@example.com")).toBeInTheDocument();
  });

  it("sorts by score when the column is chosen", async () => {
    respondWith([
      lead({ id: "l1", email: "low@example.com", score: 10 }),
      lead({ id: "l2", email: "high@example.com", score: 95 }),
    ]);
    renderWorkspaceRoute(LeadsRoute, "/dashboard/leads");
    await screen.findByText("low@example.com");

    await userEvent.click(screen.getByRole("button", { name: /score/i }));

    await waitFor(() => {
      const rows = screen.getAllByRole("row").slice(1); // drop the header row
      expect(within(rows[0]).getByText("high@example.com")).toBeInTheDocument();
    });
  });
});
