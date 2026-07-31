import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useEffect, useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { renderWithRouter } from "@/test/router";

const mocks = vi.hoisted(() => ({
  logout: vi.fn(),
  unmounted: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: null,
    isLoading: false,
    isAuthenticated: false,
    logout: mocks.logout,
  }),
}));

const { BuildShell, Route } = await import("./build");

function PendingBuildProbe() {
  const [website, setWebsite] = useState("");

  useEffect(() => () => mocks.unmounted(), []);

  return (
    <label>
      Pending website
      <input value={website} onChange={(event) => setWebsite(event.target.value)} />
    </label>
  );
}

function ShellHarness() {
  const [authenticated, setAuthenticated] = useState(false);

  return (
    <>
      <button type="button" onClick={() => setAuthenticated(true)}>
        Complete authentication
      </button>
      <BuildShell isAuthenticated={authenticated}>
        <PendingBuildProbe />
      </BuildShell>
    </>
  );
}

describe("BuildShell", () => {
  it("keeps the pending build mounted while authentication changes the header", async () => {
    mocks.unmounted.mockReset();
    renderWithRouter(ShellHarness);

    const website = await screen.findByLabelText("Pending website");
    await userEvent.type(website, "northsidedental.com");
    await userEvent.click(screen.getByRole("button", { name: "Complete authentication" }));

    expect(screen.getByLabelText("Pending website")).toHaveValue("northsidedental.com");
    expect(screen.getByRole("link", { name: "Magnitai workspace" })).toBeInTheDocument();
    expect(mocks.unmounted).not.toHaveBeenCalled();
  });
});

/**
 * The return trip from Stripe.
 *
 * `validateSearch` replaces the query string wholesale, so a parameter the
 * schema does not name is not merely ignored — it is deleted before any
 * component sees it. `checkout` was missing, which is why a customer who
 * cancelled a payment came back to a tool still marked pending, with nothing on
 * the page aware that a checkout had just ended. `resume` travels with it so
 * the right tool is reopened even in a tab that lost its saved journey.
 */
describe("build search params · checkout return", () => {
  const schema = Route.options.validateSearch as
    | ((s: Record<string, unknown>) => Record<string, unknown>)
    | { parse: (s: Record<string, unknown>) => Record<string, unknown> };

  const validate = (search: Record<string, unknown>): Record<string, unknown> =>
    typeof schema === "function" ? schema(search) : schema.parse(search);

  it.each(["success", "cancelled"])("keeps %s", (outcome) => {
    expect(validate({ checkout: outcome }).checkout).toBe(outcome);
  });

  it("keeps the tool being paid for alongside the outcome", () => {
    const widgetId = "3f6b1a52-9c1e-4a1f-9f0b-2c0f5d7a1b34";
    expect(validate({ checkout: "cancelled", resume: widgetId })).toMatchObject({
      checkout: "cancelled",
      resume: widgetId,
    });
  });

  it("drops an outcome it does not recognise rather than acting on it", () => {
    // The query string is attacker-controllable; it selects a code path, and
    // must never be mistaken for evidence that money changed hands.
    expect(validate({ checkout: "paid" }).checkout).toBeUndefined();
    expect(validate({ checkout: 1 }).checkout).toBeUndefined();
  });

  it("is absent on a normal visit", () => {
    expect(validate({}).checkout).toBeUndefined();
  });
});
