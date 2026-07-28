import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";
import { renderWithRouter } from "@/test/router";

/**
 * The intake screen, which is the whole top of the funnel and had no tests.
 *
 * The HTTP layer is mocked so the real mutation runs; what these assert is the
 * contract the flow sends to `/api/widgets/guest-concepts`, because the brief in
 * that request body is what the analyzer actually obeys.
 */
const mocks = vi.hoisted(() => {
  const authListeners = new Set<() => void>();
  const state = {
    post: vi.fn(),
    get: vi.fn(),
    autopilotReady: vi.fn(),
    authenticated: false,
    authListeners,
    setAuthenticated(value: boolean) {
      state.authenticated = value;
      authListeners.forEach((listener) => listener());
    },
    subscribeAuth(listener: () => void) {
      authListeners.add(listener);
      return () => authListeners.delete(listener);
    },
  };
  return state;
});

vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-client")>();
  return { ...actual, api: { ...actual.api, post: mocks.post, get: mocks.get } };
});

vi.mock("@/lib/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/auth")>();
  const { useSyncExternalStore } = await import("react");
  const finishAuthentication = (_credentials: unknown, callbacks?: { onSuccess?: () => void }) => {
    mocks.setAuthenticated(true);
    // React Query's hook-level auth success updates the route before its
    // per-call success callback runs. Reproduce that ordering so a wrapper
    // remount cannot hide in a synchronous mock.
    queueMicrotask(() => callbacks?.onSuccess?.());
  };
  return {
    ...actual,
    useAuth: () => {
      const authenticated = useSyncExternalStore(
        mocks.subscribeAuth,
        () => mocks.authenticated,
        () => false,
      );
      return {
        user: authenticated
          ? {
              id: "u1",
              email: "founder@example.com",
              role: "owner",
              created_at: "2026-01-01T00:00:00Z",
              email_verified: true,
              mfa_enabled: false,
              notify_on_lead: true,
            }
          : null,
        isLoading: false,
        isAuthenticated: authenticated,
        logout: vi.fn(),
        login: { mutate: finishAuthentication, isPending: false, error: null } as never,
        signup: { mutate: finishAuthentication, isPending: false, error: null } as never,
        googleLogin: { mutate: finishAuthentication, isPending: false, error: null } as never,
      };
    },
  };
});

const { CheckoutFlow } = await import("./CheckoutFlow");

const BRAND = {
  primary_color: "#101014",
  secondary_color: "#3b3b44",
  background_color: "#f5f4f0",
  accent_color: "#f6191c",
  font_headings: "Geist",
  font_body: "Geist",
  tone: "direct",
  logo_url: null,
};

const VISUAL = {
  layout: "centered",
  spacing: "roomy",
  card_style: "soft",
  border_radius: "16px",
  shadow_depth: "low",
  button_style: "solid",
  decorative_elements: "none",
  icon_style: "line",
  visual_energy: "calm",
};

function concept(title: string) {
  return {
    blueprint: { type: "roi_calculator", title, description: "d", rationale: "r" },
    architect: {
      widget_type: "roi_calculator",
      brand: BRAND,
      visual_language: VISUAL,
      logic: { formula: "x", variables: [], example_calculation: "e" },
      copywriting: { headline: title },
      decision: null,
      claims: [],
    },
  };
}

function Flow() {
  return (
    <CheckoutFlow
      onBuildStart={vi.fn()}
      onAutopilotReady={mocks.autopilotReady}
      onBack={vi.fn()}
      initialSite="northsidedental.com"
    />
  );
}

/** The brief the flow actually posted. */
function postedBrief() {
  return mocks.post.mock.calls.find(([path]) => path === "/api/widgets/guest-concepts")?.[1]?.brief;
}

const GUEST_RESPONSE = {
  target_url: "https://northsidedental.com",
  session_token: "tok",
  concepts: [concept("Savings calculator"), concept("Readiness quiz")],
  brief: { mode: "autopilot" },
};

function respondToBuildRequests() {
  mocks.post.mockImplementation((path: string) => {
    if (path === "/api/widgets/guest-concepts") return Promise.resolve(GUEST_RESPONSE);
    if (path === "/api/widgets/claim-guest") {
      return Promise.resolve({
        widget_id: "w-ai",
        blueprints: GUEST_RESPONSE.concepts.map((item) => item.blueprint),
        selected_index: 0,
        selected_concept: GUEST_RESPONSE.concepts[0].architect,
        entitlement_status: "preview",
        can_build: false,
      });
    }
    return Promise.resolve(null);
  });
}

async function authenticateAutopilot() {
  const dialog = await screen.findByRole("dialog");
  await userEvent.type(within(dialog).getByLabelText(/email/i), "founder@example.com");
  await userEvent.type(within(dialog).getByLabelText(/password/i), "securepassword12");
  await userEvent.click(within(dialog).getByRole("button", { name: /create account/i }));
}

describe("CheckoutFlow · AI build", () => {
  beforeEach(() => {
    mocks.post.mockReset();
    mocks.get.mockReset();
    mocks.autopilotReady.mockReset();
    mocks.authListeners.clear();
    mocks.authenticated = false;
    mocks.get.mockResolvedValue(null);
    respondToBuildRequests();
  });

  it("prefills a website passed into the build route", async () => {
    renderWithRouter(Flow);
    expect(
      await screen.findByRole("heading", { name: /build your next lead magnet/i }),
    ).toBeInTheDocument();
    expect(await screen.findByLabelText(/website page to analyse/i)).toHaveValue(
      "northsidedental.com",
    );
    expect(screen.getByRole("button", { name: /build for me/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /build with me/i })).toBeInTheDocument();
  });

  it("presents direct and collaborative AI paths", async () => {
    renderWithRouter(Flow);
    expect(await screen.findByText(/publicly available page content/i)).toBeInTheDocument();
    expect(screen.getByText(/nothing is published until/i)).toBeInTheDocument();
    expect(screen.getByText(/AI chooses the format/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /build for me/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /build with me/i })).toBeInTheDocument();
  });

  it("has no accessibility violations on the URL-first entry", async () => {
    const { container } = renderWithRouter(Flow);
    await screen.findByRole("heading", { name: /build your next lead magnet/i });
    await expectNoA11yViolations(container);
  });

  it("opens the account handoff before starting a signed-out direct build", async () => {
    renderWithRouter(Flow);
    await userEvent.click(await screen.findByRole("button", { name: /build for me/i }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/let magnitai build it/i)).toBeInTheDocument();
    expect(within(dialog).getByText(/add the result to your dashboard/i)).toBeInTheDocument();
    expect(
      within(dialog).getByRole("button", { name: /sign up with google/i }),
    ).toBeInTheDocument();
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it("shows honest build status without simulated output", async () => {
    let finishGuestBuild!: (value: typeof GUEST_RESPONSE) => void;
    mocks.post.mockImplementation((path: string) => {
      if (path === "/api/widgets/guest-concepts") {
        return new Promise<typeof GUEST_RESPONSE>((resolve) => {
          finishGuestBuild = resolve;
        });
      }
      if (path === "/api/widgets/claim-guest") {
        return Promise.resolve({
          widget_id: "w-ai",
          blueprints: GUEST_RESPONSE.concepts.map((item) => item.blueprint),
          selected_index: 0,
          selected_concept: GUEST_RESPONSE.concepts[0].architect,
          entitlement_status: "preview",
          can_build: false,
        });
      }
      return Promise.resolve(null);
    });

    const { container } = renderWithRouter(Flow);
    await userEvent.click(await screen.findByRole("button", { name: /build for me/i }));
    await authenticateAutopilot();

    expect(
      await screen.findByRole("heading", {
        name: /building the best direction for northsidedental.com/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/finding the strongest direction/i);
    expect(screen.getByRole("progressbar", { name: /builder journey/i })).toHaveAttribute(
      "aria-valuenow",
      "2",
    );
    expect(screen.queryByLabelText(/two AI directions being prepared/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/previews will appear/i)).not.toBeInTheDocument();
    await expectNoA11yViolations(container);

    finishGuestBuild(GUEST_RESPONSE);
    await waitFor(() => expect(mocks.autopilotReady).toHaveBeenCalledWith("w-ai"));
  });

  it("opens the collaborative brief before asking for an account", async () => {
    renderWithRouter(Flow);
    await userEvent.click(await screen.findByRole("button", { name: /build with me/i }));

    expect(await screen.findByRole("heading", { name: /set the direction/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/what should magnitai build/i)).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("preserves the collaborative brief behind the account gate", async () => {
    renderWithRouter(Flow);
    await userEvent.click(await screen.findByRole("button", { name: /build with me/i }));
    await userEvent.type(
      await screen.findByLabelText(/what should magnitai build/i),
      "Create a workflow savings planner",
    );
    await userEvent.click(screen.getByRole("button", { name: /build my directions/i }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/save your collaboration/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue(/workflow savings planner/i)).toBeInTheDocument();
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it("refuses an incomplete website instead of calling the API", async () => {
    renderWithRouter(Flow);
    const site = await screen.findByLabelText(/website page to analyse/i);
    await userEvent.clear(site);
    await userEvent.type(site, "notadomain");
    await userEvent.click(screen.getByRole("button", { name: /build for me/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/complete website/i);
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it("surfaces the reason when the site cannot be read", async () => {
    mocks.post.mockImplementation((path: string) => {
      if (path === "/api/widgets/guest-concepts") {
        return Promise.reject(new Error("We couldn't reach that website."));
      }
      return Promise.resolve(null);
    });
    renderWithRouter(Flow);
    await userEvent.click(await screen.findByRole("button", { name: /build for me/i }));
    await authenticateAutopilot();

    expect(await screen.findByRole("alert")).toHaveTextContent("We couldn't reach that website.");
  });

  it("claims the strongest direction and hands it to the dashboard after signup", async () => {
    renderWithRouter(Flow);
    await userEvent.click(await screen.findByRole("button", { name: /build for me/i }));
    await authenticateAutopilot();

    await waitFor(() => expect(mocks.autopilotReady).toHaveBeenCalledWith("w-ai"));
    expect(postedBrief().mode).toBe("autopilot");
    expect(mocks.post).toHaveBeenCalledWith("/api/widgets/claim-guest", {
      session_token: "tok",
      selected_index: 0,
    });
  });

  it("lets an existing user sign in before the direct build", async () => {
    renderWithRouter(Flow);
    await userEvent.click(await screen.findByRole("button", { name: /build for me/i }));
    const dialog = await screen.findByRole("dialog");

    await userEvent.click(within(dialog).getByRole("button", { name: /^sign in$/i }));
    expect(
      within(dialog).getByRole("button", { name: /sign in and continue/i }),
    ).toBeInTheDocument();
  });

  it("starts immediately for a user who is already signed in", async () => {
    mocks.setAuthenticated(true);
    renderWithRouter(Flow);
    await userEvent.click(await screen.findByRole("button", { name: /build for me/i }));

    await waitFor(() => expect(mocks.autopilotReady).toHaveBeenCalledWith("w-ai"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
