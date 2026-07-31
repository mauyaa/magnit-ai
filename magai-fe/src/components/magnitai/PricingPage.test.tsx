import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";
import { renderWithRouter } from "@/test/router";

/**
 * The public pricing page.
 *
 * Its defining behaviour is what it does when it *cannot* reach billing: it
 * says so, and shows nothing. A pricing page that falls back to a hardcoded
 * table is the exact drift between marketing and product this codebase spent
 * effort removing, so the unavailable state is tested as hard as the happy one.
 */
const mocks = vi.hoisted(() => ({ get: vi.fn() }));

vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-client")>();
  return { ...actual, api: { ...actual.api, get: mocks.get } };
});

const { PricingPage } = await import("./PricingPage");

function plan(over: Record<string, unknown> = {}) {
  return {
    id: "studio",
    name: "Studio",
    tagline: "For one brand",
    monthly_price: 4900,
    currency: "usd",
    live_tool_limit: 3,
    monthly_build_limit: 10,
    lead_limit_per_tool: 500,
    analytics_window_days: 90,
    features: ["lead_capture", "csv_export"],
    highlights: ["Three live tools", "CSV export"],
    purchasable: true,
    ...over,
  };
}

const CATALOGUE = {
  currency: "usd",
  single_tool_price: 9900,
  plans: [
    plan({ id: "free", name: "Free", monthly_price: 0, purchasable: false, live_tool_limit: 0 }),
    plan(),
    plan({ id: "scale", name: "Scale", monthly_price: 19900, live_tool_limit: 10 }),
  ],
};

/**
 * `usePlans` sets `retry: 1`, which overrides the test client's `retry: false`,
 * so the unavailable state only appears after a second attempt and its backoff.
 * A bare 1s findBy would time out while the page is still legitimately loading.
 */
const findUnavailable = () =>
  screen.findByText(/cannot verify the plans right now/i, {}, { timeout: 5000 });

beforeEach(() => {
  vi.clearAllMocks();
  mocks.get.mockResolvedValue(CATALOGUE);
});

describe("pricing page", () => {
  it("says it is checking rather than showing a blank table", async () => {
    let release: (value: unknown) => void = () => {};
    mocks.get.mockReturnValue(new Promise((resolve) => (release = resolve)));

    renderWithRouter(PricingPage);

    expect(await screen.findByRole("status")).toBeInTheDocument();
    expect(screen.getByText("Loading current plans")).toBeInTheDocument();
    release(CATALOGUE);
  });

  it("renders every plan the server publishes", async () => {
    renderWithRouter(PricingPage);

    // Each plan appears twice: once as a card, once as a comparison column.
    expect(await screen.findAllByText("Studio")).not.toHaveLength(0);
    expect(screen.getAllByText("Scale")).not.toHaveLength(0);
    expect(screen.getAllByText("Free")).not.toHaveLength(0);
  });

  it("prices come from the API, formatted as whole currency", async () => {
    renderWithRouter(PricingPage);

    // 4900 cents rendered as $49, not $49.00 and not a hardcoded string.
    expect(await screen.findByText("$49")).toBeInTheDocument();
    expect(screen.getByText("$199")).toBeInTheDocument();
    expect(screen.getByText("$0")).toBeInTheDocument();
    expect(screen.getByText(/pay \$99 once/i)).toBeInTheDocument();
  });

  it("asks the public catalogue endpoint without credentials", async () => {
    renderWithRouter(PricingPage);

    await screen.findAllByText("Studio");
    expect(mocks.get).toHaveBeenCalledWith("/api/billing/plans", { anonymous: true });
  });

  it("admits it cannot verify prices rather than inventing them", async () => {
    mocks.get.mockRejectedValue(new Error("billing unreachable"));
    renderWithRouter(PricingPage);

    expect(await findUnavailable()).toBeInTheDocument();
    expect(screen.getByText("Nothing has been guessed")).toBeInTheDocument();
    // No price is on screen at all — that is the whole point.
    expect(screen.queryByText("$49")).not.toBeInTheDocument();
  });

  it("treats an empty catalogue the same as an unreachable one", async () => {
    mocks.get.mockResolvedValue({ currency: "usd", plans: [] });
    renderWithRouter(PricingPage);

    expect(await findUnavailable()).toBeInTheDocument();
  });

  it("retries on request", async () => {
    mocks.get.mockRejectedValue(new Error("billing unreachable"));
    renderWithRouter(PricingPage);

    await findUnavailable();
    mocks.get.mockResolvedValue(CATALOGUE);
    await userEvent.click(screen.getByRole("button", { name: /check again/i }));

    expect(await screen.findAllByText("Studio")).not.toHaveLength(0);
  });

  it("still offers a way to start when pricing is down", async () => {
    mocks.get.mockRejectedValue(new Error("billing unreachable"));
    renderWithRouter(PricingPage);

    await findUnavailable();
    const link = screen.getByRole("link", { name: /preview for free/i });
    expect(link).toHaveAttribute("href", "/build");
  });

  it("has no accessibility violations", async () => {
    const { container } = renderWithRouter(PricingPage);

    await screen.findAllByText("Studio");
    await expectNoA11yViolations(container);
  });

  it("has no accessibility violations in the unavailable state", async () => {
    mocks.get.mockRejectedValue(new Error("billing unreachable"));
    const { container } = renderWithRouter(PricingPage);

    await findUnavailable();
    await expectNoA11yViolations(container);
  });
});

describe("what a one-off launch actually includes", () => {
  it("does not claim lead capture requires a subscription", async () => {
    /*
     * A one-off launch captures leads up to the cap it comes with — the server
     * enforces exactly that. The page used to say lead capture was a reason to
     * choose Studio, which meant the first thing a customer learned after
     * paying was that the pricing page had misdescribed what they bought.
     */
    renderWithRouter(PricingPage);

    const offer = await screen.findByText(/one tool, built, published and capturing leads/i);
    expect(offer).toBeInTheDocument();
  });
});
