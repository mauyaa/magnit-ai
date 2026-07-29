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
  return <CheckoutFlow onBuildStart={vi.fn()} onBack={vi.fn()} initialSite="northsidedental.com" />;
}

/** The brief the flow actually posted. */
function postedBrief() {
  return mocks.post.mock.calls.find(([path]) => path === "/api/widgets/guest-concepts")?.[1]?.brief;
}

const SITE_READ = {
  target_url: "https://northsidedental.com",
  domain: "northsidedental.com",
  business_name: "Northside Dental",
  summary: "Family dental care.",
  pages_read: 3,
  signals_found: 42,
  colors: ["#17324d", "#e8b05c"],
  fonts: ["Inter"],
  highlights: ["Confident dental care", "New patient appointments from $120."],
};

const GUEST_RESPONSE = {
  target_url: "https://northsidedental.com",
  session_token: "tok",
  concepts: [concept("Savings calculator"), concept("Readiness quiz")],
  brief: { mode: "autopilot" },
};

function respondToBuildRequests() {
  mocks.post.mockImplementation((path: string) => {
    if (path === "/api/widgets/read-site") return Promise.resolve(SITE_READ);
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

  it("analyses without an account, because every page leading here promises that", async () => {
    // The landing page says "No account needed to look" and the pricing page
    // says "Choose before signup". This used to open the signup dialog on the
    // first click and analyse nothing.
    renderWithRouter(Flow);
    await userEvent.click(await screen.findByRole("button", { name: /build for me/i }));

    await waitFor(() =>
      expect(mocks.post).toHaveBeenCalledWith(
        "/api/widgets/guest-concepts",
        expect.objectContaining({ url: "https://northsidedental.com" }),
        { anonymous: true },
      ),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows what it read while the slow half is still running", async () => {
    let finishGuestBuild!: (value: typeof GUEST_RESPONSE) => void;
    mocks.post.mockImplementation((path: string) => {
      if (path === "/api/widgets/read-site") return Promise.resolve(SITE_READ);
      if (path === "/api/widgets/guest-concepts") {
        return new Promise<typeof GUEST_RESPONSE>((resolve) => {
          finishGuestBuild = resolve;
        });
      }
      return Promise.resolve(null);
    });

    const { container } = renderWithRouter(Flow);
    await userEvent.click(await screen.findByRole("button", { name: /build for me/i }));

    // The crawl lands in about five seconds against sixty for the directions.
    // Their own business name and their own headline are the proof that the
    // wait is doing something; a spinner only asks them to assume it.
    expect(await screen.findByText(/read northside dental/i)).toBeInTheDocument();
    expect(screen.getByText(/3 pages · 42 signals/i)).toBeInTheDocument();
    expect(screen.getByText(/Confident dental care/)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/finding the strongest direction/i);
    await expectNoA11yViolations(container);

    finishGuestBuild(GUEST_RESPONSE);
    expect(await screen.findAllByText("Savings calculator")).not.toHaveLength(0);
  });

  it("a failed read costs the reassurance, not the run", async () => {
    mocks.post.mockImplementation((path: string) => {
      if (path === "/api/widgets/read-site") return Promise.reject(new Error("crawl hiccup"));
      if (path === "/api/widgets/guest-concepts") return Promise.resolve(GUEST_RESPONSE);
      return Promise.resolve(null);
    });
    renderWithRouter(Flow);
    await userEvent.click(await screen.findByRole("button", { name: /build for me/i }));

    expect(await screen.findAllByText("Savings calculator")).not.toHaveLength(0);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shapes a brief without an account too", async () => {
    renderWithRouter(Flow);
    await userEvent.click(await screen.findByRole("button", { name: /build with me/i }));
    await userEvent.type(
      await screen.findByLabelText(/what should magnitai build/i),
      "Create a workflow savings planner",
    );
    await userEvent.click(screen.getByRole("button", { name: /build my directions/i }));

    await waitFor(() => expect(postedBrief()?.mode).toBe("guided"));
    expect(postedBrief().intent).toBe("Create a workflow savings planner");
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

    expect(await screen.findByRole("alert")).toHaveTextContent("We couldn't reach that website.");
  });

  it("asks for an account only when the visitor keeps a direction", async () => {
    // Loss aversion is the whole point of gating here rather than earlier: they
    // have seen the work, so the ask is "keep this", not "trust us".
    renderWithRouter(Flow);
    await userEvent.click(await screen.findByRole("button", { name: /build for me/i }));
    await screen.findAllByText("Savings calculator");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await userEvent.click(
      (await screen.findAllByRole("button", { name: /choose this direction/i }))[0],
    );

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("adopts the chosen direction once the account exists", async () => {
    renderWithRouter(Flow);
    await userEvent.click(await screen.findByRole("button", { name: /build for me/i }));
    await screen.findAllByText("Savings calculator");
    await userEvent.click(
      (await screen.findAllByRole("button", { name: /choose this direction/i }))[0],
    );
    await authenticateAutopilot();

    await waitFor(() =>
      expect(mocks.post).toHaveBeenCalledWith("/api/widgets/claim-guest", {
        session_token: "tok",
        selected_index: 0,
      }),
    );
  });

  it("an already signed-in visitor sees the same two directions", async () => {
    mocks.setAuthenticated(true);
    renderWithRouter(Flow);
    await userEvent.click(await screen.findByRole("button", { name: /build for me/i }));

    expect(await screen.findAllByText("Savings calculator")).not.toHaveLength(0);
    expect(await screen.findAllByText("Readiness quiz")).not.toHaveLength(0);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
