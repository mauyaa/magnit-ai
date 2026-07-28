import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWorkspaceRoute } from "@/test/workspace";

/** As elsewhere: mock the HTTP layer, keep React Query real. */
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

const logout = vi.hoisted(() => vi.fn());

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
        display_name: "Magnitai Founder",
        workspace_name: "Magnitai",
        workspace_timezone: "Africa/Nairobi",
        workspace_id: "u1",
        notify_weekly_summary: true,
        notify_product_updates: false,
        labs_enabled: false,
      },
      isLoading: false,
      isAuthenticated: true,
      logout,
      login: {} as never,
      signup: {} as never,
    }),
  };
});

const { Route } = await import("./settings");
const SettingsRoute = Route.options.component as React.FunctionComponent;

function respond(over: Record<string, unknown> = {}) {
  mocks.get.mockImplementation((path: string) => {
    if (path === "/api/auth/mfa")
      return Promise.resolve({ enabled: false, recovery_codes_remaining: 0, ...over });
    if (path === "/api/widgets") return Promise.resolve({ widgets: [] });
    if (path === "/api/payments/subscription")
      return Promise.resolve({
        plan: "free",
        status: "free",
        active_experiences: 0,
        experience_limit: 0,
        monthly_price: 0,
        currency: "usd",
      });
    return Promise.resolve(null);
  });
}

describe("settings route", () => {
  beforeEach(() => {
    mocks.get.mockReset();
    mocks.post.mockReset();
    mocks.patch.mockReset();
    mocks.del.mockReset();
    logout.mockReset();
  });

  describe("deleting the account", () => {
    /**
     * The whole safety mechanism. Deletion takes every tool and every captured
     * lead with it, so the button stays disabled until the owner has supplied a
     * password *and* typed the word — not one or the other.
     */
    it("stays disabled until both the password and the confirm word are given", async () => {
      respond();
      renderWorkspaceRoute(SettingsRoute, "/dashboard/settings");
      await userEvent.click(await screen.findByRole("link", { name: /data & export/i }));

      const button = await screen.findByRole("button", { name: /delete my account/i });
      expect(button).toBeDisabled();

      await userEvent.type(screen.getByLabelText(/your password/i), "hunter2");
      expect(button).toBeDisabled();

      await userEvent.type(screen.getByLabelText(/type "delete" to confirm/i), "delete");
      expect(button).toBeEnabled();
    });

    it("does not accept a near-miss confirmation word", async () => {
      respond();
      renderWorkspaceRoute(SettingsRoute, "/dashboard/settings");
      await userEvent.click(await screen.findByRole("link", { name: /data & export/i }));

      await screen.findByRole("button", { name: /delete my account/i });
      await userEvent.type(screen.getByLabelText(/your password/i), "hunter2");
      await userEvent.type(screen.getByLabelText(/type "delete" to confirm/i), "delet");

      expect(screen.getByRole("button", { name: /delete my account/i })).toBeDisabled();
    });

    /**
     * A wrong password must surface the message, not vanish into an unhandled
     * rejection — which is what an awaited `mutateAsync` in a bare submit
     * handler produced.
     */
    it("shows the server's reason when deletion is refused, and keeps the session", async () => {
      respond();
      const unhandled = vi.fn();
      window.addEventListener("unhandledrejection", unhandled);
      mocks.del.mockRejectedValue(new Error("That password is incorrect."));

      renderWorkspaceRoute(SettingsRoute, "/dashboard/settings");
      await userEvent.click(await screen.findByRole("link", { name: /data & export/i }));
      await screen.findByRole("button", { name: /delete my account/i });
      await userEvent.type(screen.getByLabelText(/your password/i), "wrong");
      await userEvent.type(screen.getByLabelText(/type "delete" to confirm/i), "delete");
      await userEvent.click(screen.getByRole("button", { name: /delete my account/i }));

      expect(await screen.findByRole("alert")).toHaveTextContent("That password is incorrect.");
      expect(logout).not.toHaveBeenCalled();

      await new Promise((resolve) => setTimeout(resolve, 0));
      expect(unhandled).not.toHaveBeenCalled();
      window.removeEventListener("unhandledrejection", unhandled);
    });

    it("signs the owner out once deletion succeeds", async () => {
      respond();
      mocks.del.mockResolvedValue({ deleted: true });

      renderWorkspaceRoute(SettingsRoute, "/dashboard/settings");
      await userEvent.click(await screen.findByRole("link", { name: /data & export/i }));
      await screen.findByRole("button", { name: /delete my account/i });
      await userEvent.type(screen.getByLabelText(/your password/i), "hunter2");
      await userEvent.type(screen.getByLabelText(/type "delete" to confirm/i), "delete");
      await userEvent.click(screen.getByRole("button", { name: /delete my account/i }));

      await waitFor(() => expect(logout).toHaveBeenCalled());
    });
  });

  describe("two-factor authentication", () => {
    it("reports how many recovery codes are left once enabled", async () => {
      respond({ enabled: true, recovery_codes_remaining: 7 });
      renderWorkspaceRoute(SettingsRoute, "/dashboard/settings");
      await userEvent.click(await screen.findByRole("link", { name: /security/i }));

      expect(await screen.findByText(/two-factor authentication is on/i)).toBeInTheDocument();
      expect(screen.getByText(/7 recovery codes left/i)).toBeInTheDocument();
    });

    it("uses the singular when one code is left", async () => {
      respond({ enabled: true, recovery_codes_remaining: 1 });
      renderWorkspaceRoute(SettingsRoute, "/dashboard/settings");
      await userEvent.click(await screen.findByRole("link", { name: /security/i }));

      expect(await screen.findByText(/1 recovery code left/i)).toBeInTheDocument();
    });
  });

  describe("changing the password", () => {
    it("requires both fields before it will submit", async () => {
      respond();
      renderWorkspaceRoute(SettingsRoute, "/dashboard/settings");
      await userEvent.click(await screen.findByRole("link", { name: /profile/i }));

      const button = await screen.findByRole("button", { name: /update password/i });
      expect(button).toBeDisabled();

      await userEvent.type(screen.getByLabelText(/current password/i), "old-one");
      expect(button).toBeDisabled();

      await userEvent.type(screen.getByLabelText(/new password/i), "a-much-longer-new-one");
      expect(button).toBeEnabled();
    });

    it("clears both fields after a successful change", async () => {
      respond();
      mocks.patch.mockResolvedValue({ changed: true });

      renderWorkspaceRoute(SettingsRoute, "/dashboard/settings");
      await userEvent.click(await screen.findByRole("link", { name: /profile/i }));
      await screen.findByRole("button", { name: /update password/i });

      const current = screen.getByLabelText(/current password/i);
      const next = screen.getByLabelText(/new password/i);
      await userEvent.type(current, "old-one");
      await userEvent.type(next, "a-much-longer-new-one");
      await userEvent.click(screen.getByRole("button", { name: /update password/i }));

      // Leaving a password sitting in a filled input after it has been changed
      // is exactly the thing the next person at the machine should not find.
      await waitFor(() => expect(current).toHaveValue(""));
      expect(next).toHaveValue("");
    });
  });
});
