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

const { BuildShell } = await import("./build");

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
