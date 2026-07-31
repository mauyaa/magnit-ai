import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";

import { percentChange, StatCard, StatRow } from "./StatCard";

/**
 * The metric card is the first thing anyone looks at, on the two screens they
 * open most. Its job is to be readable without being read: the number leads,
 * and one object underneath says what to make of it.
 *
 * These pin the part that kept drifting — the line under the number. It used
 * to be a tinted pill, a grey pill, loose text or nothing at all depending on
 * which data happened to exist, so a row of four cards had three different
 * silhouettes for reasons no customer could see. That is the kind of
 * difference nobody chooses and everybody feels.
 */
function contextOf(card: HTMLElement): HTMLElement | null {
  return card.querySelector(".rounded-full");
}

describe("the metric card's context line", () => {
  it("shows a rise as a single object, not a sentence", () => {
    const { container } = render(
      <StatCard label="Leads captured" value="128" delta={{ percent: 36.8 }} />,
    );

    const pill = contextOf(container.firstElementChild as HTMLElement);
    expect(pill).not.toBeNull();
    expect(pill).toHaveTextContent("+36.8%");
  });

  it("keeps the caption beside the change rather than inside it", () => {
    // "+36.8%  vs last month" — the change is the object, the period is the
    // caption. Merging them makes a pill nobody can scan.
    render(<StatCard label="Leads" value="128" delta={{ percent: 36.8 }} note="vs last month" />);

    expect(screen.getByText("vs last month")).toBeInTheDocument();
    expect(screen.getByText("vs last month").className).not.toContain("rounded-full");
  });

  it("gives the caption the pill when there is no change to show", () => {
    // Otherwise this card is the one in the row with loose text where its
    // neighbours have an object.
    const { container } = render(<StatCard label="Live tools" value="3" note="6 in total" />);

    const pill = contextOf(container.firstElementChild as HTMLElement);
    expect(pill).toHaveTextContent("6 in total");
  });

  it("says so when there is no prior period, rather than leaving a gap", () => {
    const { container } = render(
      <StatCard label="Start → lead" value="70.0%" delta={{ percent: null }} />,
    );

    expect(contextOf(container.firstElementChild as HTMLElement)).toHaveTextContent(
      "No prior period",
    );
  });

  it("colours a fall by whether falling is bad, not by direction", () => {
    // Drop-off going down is good news. Painting every decline red would make
    // the one metric a customer wants falling look like a problem.
    const { container } = render(
      <StatCard label="Drop-off" value="12%" delta={{ percent: -20, higherIsBetter: false }} />,
    );

    expect(contextOf(container.firstElementChild as HTMLElement)?.className).toContain("success");
  });
});

describe("the metric card's hierarchy", () => {
  it("makes the number outrank its own label", () => {
    /*
     * The number was 30px against a 14px label on a card over 300px wide —
     * barely twice its size — so a screen of metrics read as a screen of
     * sentences with figures in them and nothing led the eye.
     */
    const { container } = render(<StatCard label="Leads captured" value="128" />);
    const card = container.firstElementChild as HTMLElement;

    const label = within(card).getByText("Leads captured");
    const value = within(card).getByText("128");

    expect(label.className).toContain("text-xs");
    expect(value.className).toContain("text-4xl");
  });

  it("renders the value in tabular figures so a row cannot jitter", () => {
    const { container } = render(<StatCard label="Leads" value="1,284" />);
    expect(within(container).getByText("1,284").className).toContain("tabular");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <StatRow>
        <StatCard label="Leads captured" value="128" delta={{ percent: 36.8 }} note="vs last" />
        <StatCard label="Live tools" value="3" note="6 in total" />
      </StatRow>,
    );
    await expectNoA11yViolations(container);
  });
});

describe("percentChange", () => {
  it("refuses to divide by an empty previous period", () => {
    // "Up ∞%" from a standing start is not a fact anyone can act on.
    expect(percentChange(10, 0)).toBeNull();
  });

  it("reports a real change", () => {
    expect(percentChange(150, 100)).toBe(50);
  });
});
