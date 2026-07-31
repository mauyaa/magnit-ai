import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { clearTokens, setTokens } from "@/lib/auth-storage";
import { renderWorkspaceRoute } from "@/test/workspace";

/**
 * The HTTP layer is mocked rather than the hooks.
 *
 * That matters for the first test below: stubbing the hooks lets a test pick a
 * loading flag and hold it, whereas the crash this file guards against only
 * appears on the *transition* from loading to loaded. Mocking `api.get` keeps
 * React Query real, so the transition is the real one.
 *
 * It also lets these tests assert the request the screen makes. Filtering,
 * sorting and paging now happen on the server, so "does the search box work"
 * is answered by what was asked for, not by what the browser sifted afterwards.
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

const ENTITLEMENTS = {
  plan: { id: "studio", name: "Studio", live_tool_limit: 3, monthly_build_limit: 25 },
  status: "active",
  usage: { live_tools: 1, total_tools: 1, builds_this_period: 0 },
  allowance: { builds_remaining: 25, live_tools_remaining: 2, can_build: true, can_publish: true },
  features: ["csv_export", "lead_pipeline"],
  period_started_at: "2026-07-01T00:00:00Z",
  current_period_end: null,
  granted_widget_ids: [],
};

/** The query string of the most recent leads request the screen made. */
function lastLeadQuery(): URLSearchParams {
  const call = [...mocks.get.mock.calls]
    .reverse()
    .find((call) => String(call[0]).startsWith("/api/leads"));
  return new URLSearchParams(String(call?.[0] ?? "").split("?")[1] ?? "");
}

/**
 * A server that answers the way the real one does.
 *
 * It honours the filters rather than ignoring them, because the screen no
 * longer has any way to compensate: if the request is wrong, the page is wrong.
 */
function respondWith(leads: Array<Record<string, unknown>>) {
  mocks.get.mockImplementation((path: string) => {
    if (path === "/api/widgets") return Promise.resolve({ widgets: [WIDGET] });
    if (path === "/api/payments/subscription") return Promise.resolve(null);
    // A subscribed workspace, so the plan-gated export control is on screen.
    if (path.includes("/entitlements")) return Promise.resolve(ENTITLEMENTS);
    if (path.startsWith("/api/leads")) {
      const params = new URLSearchParams(path.split("?")[1] ?? "");
      const needle = (params.get("query") ?? "").toLowerCase();
      let matched = leads.filter(
        (item) =>
          !needle ||
          String(item.email).toLowerCase().includes(needle) ||
          String(item.name ?? "")
            .toLowerCase()
            .includes(needle),
      );
      if (params.get("sort") === "score") {
        const factor = params.get("direction") === "asc" ? 1 : -1;
        matched = [...matched].sort(
          (a, b) => factor * (Number(a.score ?? -1) - Number(b.score ?? -1)),
        );
      }
      return Promise.resolve({
        items: matched.map((item) => ({ widget_title: WIDGET.title, ...item })),
        total: matched.length,
        limit: Number(params.get("limit") ?? 25),
        offset: Number(params.get("offset") ?? 0),
      });
    }
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
    // The search reached the server. Filtering one page in the browser would
    // hide matches that are on page two and call it a result.
    expect(lastLeadQuery().get("query")).toBe("grace");
  });

  /**
   * The behaviour this screen used to have, deliberately removed.
   *
   * It fanned out one request per tool and kept whichever ones resolved. A
   * workspace with ten tools therefore showed a *subset* of its leads whenever
   * a single request failed — indistinguishable, on screen, from having fewer
   * leads. One request means a failure is a failure and says so.
   */
  it("asks for the workspace's leads in one paginated request", async () => {
    respondWith([lead()]);
    renderWorkspaceRoute(LeadsRoute, "/dashboard/leads");
    await screen.findByText("ada@example.com");

    const perWidget = mocks.get.mock.calls.filter((call) =>
      /widgets\/[^/]+\/leads/.test(String(call[0])),
    );
    expect(perWidget).toHaveLength(0);
    expect(lastLeadQuery().get("limit")).toBe("25");
  });

  it("downloads the export as the signed-in user, not as an anonymous link", async () => {
    /*
     * The API authenticates with a bearer token. A plain `<a href download>`
     * sends no headers, so the browser would cheerfully save a 401 as the
     * customer's "leads export" — a file that looks like a download and is not.
     * The request has to be made properly and the response saved from memory.
     */
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("Email,Name\nada@example.com,Ada", {
        status: 200,
        headers: { "Content-Type": "text/csv" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn(() => "blob:leads"),
      revokeObjectURL: vi.fn(),
    });

    setTokens({ accessToken: "test-access-token", refreshToken: "test-refresh-token" });
    respondWith([lead()]);
    renderWorkspaceRoute(LeadsRoute, "/dashboard/leads");
    await screen.findByText("ada@example.com");

    await userEvent.click(screen.getByRole("button", { name: /export csv/i }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/api/leads/export.csv");
    expect((init?.headers ?? {}).Authorization).toBe("Bearer test-access-token");
    clearTokens();

    vi.unstubAllGlobals();
  });

  it("carries the on-screen filters into the download", async () => {
    // A download that quietly ignores the filter above it is a trap: the
    // customer acts on a file they believe matches what they were looking at.
    const fetchMock = vi.fn().mockResolvedValue(new Response("Email\n", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn(() => "blob:leads"),
      revokeObjectURL: vi.fn(),
    });

    respondWith([lead(), lead({ id: "l2", email: "grace@example.com", name: "Grace Hopper" })]);
    renderWorkspaceRoute(LeadsRoute, "/dashboard/leads");
    await screen.findByText("ada@example.com");

    await userEvent.type(screen.getByRole("searchbox", { name: /search leads/i }), "grace");
    await waitFor(() => expect(screen.queryByText("ada@example.com")).not.toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /export csv/i }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(String(fetchMock.mock.calls[0][0])).toContain("query=grace");

    vi.unstubAllGlobals();
  });

  it("reports the server's count, not the size of the page", async () => {
    mocks.get.mockImplementation((path: string) => {
      if (path === "/api/widgets") return Promise.resolve({ widgets: [WIDGET] });
      if (path === "/api/payments/subscription") return Promise.resolve(null);
      if (path.startsWith("/api/leads")) {
        // One page of a much larger table: the number an owner reads has to be
        // the whole of what they have, not the twenty-five in front of them.
        return Promise.resolve({ items: [lead()], total: 3214, limit: 25, offset: 0 });
      }
      return Promise.resolve(null);
    });

    renderWorkspaceRoute(LeadsRoute, "/dashboard/leads");

    expect(await screen.findByText(/3,214 people have left their details/i)).toBeInTheDocument();
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
    // Sorted by the side that can see every row. Ordering a single page and
    // labelling the column "sorted by score" is a claim the screen cannot keep.
    expect(lastLeadQuery().get("sort")).toBe("score");
    expect(lastLeadQuery().get("direction")).toBe("desc");
  });
});
