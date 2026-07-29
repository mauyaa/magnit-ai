import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { SHOWCASE } from "@/lib/showcase";
import { expectNoA11yViolations } from "@/test/a11y";
import { renderWithRouter } from "@/test/router";

import { WidgetGallery } from "./WidgetGallery";

/**
 * The gallery's job is comprehension before commitment.
 *
 * It used to describe five formats and let a visitor touch none of them, which
 * asks someone to spend their own website and a minute of waiting on faith.
 * These assert the part that changed: finished tools that actually play, with no
 * URL and no account.
 */
describe("gallery · playable examples", () => {
  it("offers a finished tool for every showcase business", async () => {
    renderWithRouter(WidgetGallery);

    const tabs = await screen.findByRole("tablist", { name: /example tools/i });
    for (const example of SHOWCASE) {
      expect(within(tabs).getByRole("tab", { name: example.business })).toBeInTheDocument();
    }
  });

  it("plays the first example without asking for anything", async () => {
    renderWithRouter(WidgetGallery);

    // The real first question of the real decision spec, not a mock.
    const first = SHOWCASE[0].architect.decision!.questions[0];
    expect(await screen.findByText(first.label)).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("switches to another business on request", async () => {
    renderWithRouter(WidgetGallery);

    const solar = SHOWCASE[1];
    await userEvent.click(await screen.findByRole("tab", { name: solar.business }));

    expect(await screen.findByText(solar.architect.decision!.buyer_question)).toBeInTheDocument();
  });

  it("states what the visitor gets before any email is asked for", async () => {
    renderWithRouter(WidgetGallery);

    expect(
      await screen.findByText(SHOWCASE[0].architect.decision!.value_before_gate),
    ).toBeInTheDocument();
  });

  it("sends someone who is convinced straight to the builder", async () => {
    renderWithRouter(WidgetGallery);

    const cta = await screen.findByRole("link", { name: /build this from my website/i });
    expect(cta).toHaveAttribute("href", "/build");
  });

  it("has no accessibility violations", async () => {
    const { container } = renderWithRouter(WidgetGallery);

    await screen.findByRole("tablist", { name: /example tools/i });
    await expectNoA11yViolations(container);
  });
});

describe("showcase data", () => {
  it("every example is a complete, scoreable decision", () => {
    // A half-specified example would render an interactive tool that cannot
    // reach a result — worse than showing a screenshot.
    for (const example of SHOWCASE) {
      const spec = example.architect.decision;
      expect(spec, example.id).not.toBeNull();
      expect(spec!.questions.length).toBeGreaterThanOrEqual(2);
      expect(spec!.results.length).toBeGreaterThanOrEqual(2);
      expect(spec!.questions.some((question) => question.weight > 0)).toBe(true);
    }
  });

  it("choice questions carry a score for every option", () => {
    for (const example of SHOWCASE) {
      for (const question of example.architect.decision!.questions) {
        if (question.input_type !== "single_choice") continue;
        expect(question.options.length, `${example.id}/${question.id}`).toBeGreaterThanOrEqual(2);
        expect(question.option_scores).toHaveLength(question.options.length);
      }
    }
  });

  it("result bands cover the whole range without overlapping", () => {
    for (const example of SHOWCASE) {
      const bands = [...example.architect.decision!.results].sort(
        (a, b) => (a.minimum_score ?? 0) - (b.minimum_score ?? 0),
      );
      expect(bands[0].minimum_score, example.id).toBe(0);
      expect(bands[bands.length - 1].maximum_score, example.id).toBe(100);
      for (let index = 1; index < bands.length; index += 1) {
        expect(bands[index].minimum_score!, example.id).toBeGreaterThan(
          bands[index - 1].maximum_score!,
        );
      }
    }
  });

  it("names no real company", () => {
    // An example wearing a real brand implies a customer who does not exist.
    for (const example of SHOWCASE) {
      expect(example.business.toLowerCase()).toMatch(/^an? /);
    }
  });
});
