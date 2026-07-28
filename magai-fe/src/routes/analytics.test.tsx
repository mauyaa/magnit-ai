import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWorkspaceRoute } from "@/test/workspace";

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

const { Route } = await import("./analytics");
const AnalyticsRoute = Route.options.component as React.FunctionComponent;

/** `count` days of identical activity, so sums are trivially predictable. */
function days(count: number, starts: number, leads: number, completions = 0) {
  return Array.from({ length: count }, (_, index) => ({
    date: `2026-06-${String(index + 1).padStart(2, "0")}`,
    starts,
    completions,
    leads,
    cta_clicks: 0,
  }));
}

function analytics(over: Record<string, unknown> = {}) {
  return {
    period_days: 60,
    experiences: [],
    daily: [],
    sources: [],
    totals: {},
    rates: {},
    dropoff_by_step: {},
    ...over,
  };
}

function respond(payload: unknown) {
  mocks.get.mockImplementation((path: string) => {
    if (path.startsWith("/api/widgets/portfolio/analytics")) return Promise.resolve(payload);
    if (path === "/api/widgets") return Promise.resolve({ widgets: [] });
    if (path === "/api/payments/subscription") return Promise.resolve(null);
    return Promise.resolve(null);
  });
}

describe("analytics route", () => {
  beforeEach(() => {
    mocks.get.mockReset();
  });

  it("reports a load failure rather than an empty dashboard", async () => {
    mocks.get.mockImplementation((path: string) => {
      if (path.startsWith("/api/widgets/portfolio/analytics"))
        return Promise.reject(new Error("Service unavailable"));
      return Promise.resolve(null);
    });

    renderWorkspaceRoute(AnalyticsRoute, "/analytics");

    expect(await screen.findByText(/couldn't load analytics/i)).toBeInTheDocument();
    expect(screen.getByText("Service unavailable")).toBeInTheDocument();
  });

  /**
   * The page asks for twice the selected window so the older half can act as the
   * comparison period. Only the recent half is the headline figure — summing the
   * whole response would silently double every number on the screen.
   */
  it("totals only the current half of the requested window", async () => {
    // 60 days back, 30 of them "previous" at 1/day and 30 "current" at 10/day.
    respond(analytics({ daily: [...days(30, 1, 0), ...days(30, 10, 0)] }));
    renderWorkspaceRoute(AnalyticsRoute, "/analytics");

    // 30 × 10 = 300, not 330.
    expect(await screen.findByText("300")).toBeInTheDocument();
    expect(screen.queryByText("330")).not.toBeInTheDocument();
  });

  it("says so when the range is too wide to have a comparison", async () => {
    respond(analytics({ daily: days(90, 1, 0) }));
    renderWorkspaceRoute(AnalyticsRoute, "/analytics");
    await screen.findByRole("button", { name: /90 days/i });

    // At 90 days the doubled window would exceed the 90-day cap, so there is no
    // earlier period left to compare against and the page has to admit it.
    await userEvent.click(screen.getByRole("button", { name: /90 days/i }));

    expect(await screen.findByText(/no comparison at 90 days/i)).toBeInTheDocument();
  });

  it("renders zeroes rather than breaking on a period with no activity", async () => {
    respond(analytics({ daily: [] }));
    renderWorkspaceRoute(AnalyticsRoute, "/analytics");

    expect(await screen.findByText(/tools started/i)).toBeInTheDocument();
    expect(screen.getAllByText("0").length).toBeGreaterThan(0);
  });
});
