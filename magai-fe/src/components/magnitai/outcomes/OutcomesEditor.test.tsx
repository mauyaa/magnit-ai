import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithRouter } from "@/test/router";

/**
 * The HTTP layer is mocked, not the hooks.
 *
 * The behaviour worth guarding is the editor keeping the band set a valid
 * partition of 0-100 while someone types, and that only happens through the real
 * state the real query populates.
 */
const mocks = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn(), del: vi.fn() }));

vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-client")>();
  return {
    ...actual,
    api: { ...actual.api, get: mocks.get, put: mocks.put, delete: mocks.del },
  };
});

const { OutcomesEditor } = await import("./OutcomesEditor");

const WIDGET = {
  id: "w1",
  title: "Practice Readiness Check",
  brand_tokens: {
    primary_color: "#0E3A53",
    secondary_color: "#22303A",
    background_color: "#FBFAF7",
    accent_color: "#1E88A8",
    font_headings: "Fraunces",
    font_body: "Inter",
  },
} as never;

const CONFIG = {
  bands: [
    {
      key: "high",
      label: "Ready to grow",
      minimum_score: 70,
      maximum_score: 100,
      importance: "high",
      description: "You have the systems in place.",
      accent_color: "#16A34A",
    },
    {
      key: "low",
      label: "Foundations first",
      minimum_score: 0,
      maximum_score: 69,
      importance: "low",
      description: "The basics need attention.",
      accent_color: "#DC2626",
    },
  ],
  advice: [{ text: "Book a growth call.", band_key: "high" }],
  email_capture: {
    enabled: true,
    heading: "Get your full results",
    subheading: "We'll email a breakdown.",
    button_label: "Send my results",
    placeholder: "Enter your work email",
    require_name: false,
    consent_text: "",
  },
  cta: { label: "Book a growth call", url: "", note: "" },
  next_steps: [],
};

const ENTITLEMENTS = {
  plan: { id: "studio", name: "Studio", live_tool_limit: 3, monthly_build_limit: 25 },
  status: "active",
  usage: { live_tools: 1, total_tools: 1, builds_this_period: 2 },
  allowance: { builds_remaining: 23, live_tools_remaining: 2, can_build: true, can_publish: true },
  features: ["outcome_editor", "question_editor"],
  period_started_at: "2026-07-01T00:00:00Z",
  current_period_end: null,
  granted_widget_ids: [],
};

function route(path: string) {
  if (path.includes("/outcomes")) return Promise.resolve({ config: CONFIG, customised: false });
  if (path.includes("/entitlements")) return Promise.resolve(ENTITLEMENTS);
  return Promise.resolve({});
}

describe("outcomes editor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.get.mockImplementation(route);
    mocks.put.mockResolvedValue({ config: CONFIG, customised: true });
  });

  it("renders the bands the server sent, highest first", async () => {
    renderWithRouter(() => <OutcomesEditor widget={WIDGET} />);

    await screen.findByDisplayValue("Ready to grow");
    const labels = screen.getAllByRole("textbox").map((input) => (input as HTMLInputElement).value);
    expect(labels.indexOf("Ready to grow")).toBeLessThan(labels.indexOf("Foundations first"));
  });

  it("shows the visitor's result screen in the tool's own brand", async () => {
    renderWithRouter(() => <OutcomesEditor widget={WIDGET} />);

    // The preview is the argument for the editor: it has to show the band a
    // score lands in, not a generic mock.
    expect(await screen.findByText("Ready to grow", { selector: "h3" })).toBeInTheDocument();
    expect(screen.getByText("Book a growth call.")).toBeInTheDocument();
    expect(screen.getByText("Get your full results")).toBeInTheDocument();
  });

  it("moving a boundary moves its neighbour so no score is orphaned", async () => {
    const user = userEvent.setup();
    renderWithRouter(() => <OutcomesEditor widget={WIDGET} />);
    await screen.findByDisplayValue("Ready to grow");

    // Raising the top band's floor to 80 has to lower the band below it to 79,
    // or scores 70-79 would fall through a gap the server rejects. Committed on
    // blur, so clearing the field mid-edit never clamps against a half-typed
    // number.
    const startsAt = screen.getByDisplayValue("70");
    await user.clear(startsAt);
    await user.type(startsAt, "80");
    await user.tab();

    await waitFor(() => expect(screen.getByText("80 – 100")).toBeInTheDocument());
    expect(screen.getByText("0 – 79")).toBeInTheDocument();
  });

  it("saves the edited configuration", async () => {
    const user = userEvent.setup();
    renderWithRouter(() => <OutcomesEditor widget={WIDGET} />);

    const label = await screen.findByDisplayValue("Ready to grow");
    await user.clear(label);
    await user.type(label, "Ready to scale");
    await user.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(mocks.put).toHaveBeenCalled());
    const [path, body] = mocks.put.mock.calls[0];
    expect(path).toBe("/api/widgets/w1/outcomes");
    expect(body.config.bands[0].label).toBe("Ready to scale");
  });

  it("cannot save until something changes", async () => {
    renderWithRouter(() => <OutcomesEditor widget={WIDGET} />);
    const save = await screen.findByRole("button", { name: /save changes/i });
    expect(save).toBeDisabled();
  });

  it("offers an upgrade instead of the editor when the plan excludes it", async () => {
    mocks.get.mockImplementation((path: string) => {
      if (path.includes("/entitlements")) {
        return Promise.resolve({ ...ENTITLEMENTS, features: [] });
      }
      return route(path);
    });

    renderWithRouter(() => <OutcomesEditor widget={WIDGET} />);

    expect(await screen.findByText(/write your own results/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /save changes/i })).not.toBeInTheDocument();
  });
});
