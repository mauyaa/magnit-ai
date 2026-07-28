import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";
import { renderWithRouter } from "@/test/router";

import { LandingPage } from "./LandingPage";
import { TransparencyDashboard } from "./TransparencyDashboard";
import { WidgetGallery } from "./WidgetGallery";

/**
 * These three pages are what a stranger sees before they trust anything, and
 * all three previously shipped invented proof: a testimonial from a person who
 * does not exist, a "97.4% confidence" readout, performance multipliers, and
 * model attributions for models the pipeline never calls.
 *
 * Guarding the absence of specific strings is unusual, but a copy edit is
 * exactly how this comes back, and a fabricated statistic is the one bug a
 * reviewer cannot catch by reading the diff.
 */

const FABRICATIONS = [
  /97\.4/,
  /3\.1s/,
  /Priya Nair/i,
  /Northstar Studio/i,
  /GPT-4o/i,
  /Sentinel Watchdog/i,
  /Antigravity v3/i,
  /\+4\.8x/,
  /99\.4%/,
  /Guard Active/i,
  /pages crawled/i,
];

function expectNoFabrications(container: HTMLElement) {
  const text = container.textContent ?? "";
  for (const pattern of FABRICATIONS) {
    expect(text).not.toMatch(pattern);
  }
}

describe("LandingPage", () => {
  it("moves a visitor directly from the promise into the builder", async () => {
    renderWithRouter(LandingPage);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /start building/i })).toHaveAttribute("href", "/build");
    expect(screen.getByRole("link", { name: /see how it works/i })).toHaveAttribute(
      "href",
      "/how-it-works",
    );
  });

  it("keeps the website analyzer on the build screen", async () => {
    renderWithRouter(LandingPage);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument());

    expect(screen.queryByLabelText(/website domain to analyze/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /analyze & build/i })).not.toBeInTheDocument();
  });

  /**
   * The live-preview block keeps its input — it drives the mockup while you
   * type, which is the page's only real proof. What it must not do is submit,
   * because that made it a second front door onto the journey the hero already
   * opens, asked half a page apart in different words.
   */
  it("keeps the preview demo as a demo, not a second way in", async () => {
    renderWithRouter(LandingPage);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument());

    expect(screen.getByLabelText(/type any company name/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /show me/i })).not.toBeInTheDocument();

    // It now offers the same link the hero does, rather than its own form.
    expect(screen.getByRole("link", { name: /from my real website/i })).toHaveAttribute(
      "href",
      "/build",
    );
  });

  it("previews the made-and-used output collection on the landing page", async () => {
    renderWithRouter(LandingPage);
    await waitFor(() => expect(screen.getByText("MADE")).toBeInTheDocument());
    expect(screen.getByText("USED.")).toBeInTheDocument();
  });

  it("carries no invented metrics, testimonials, or model names", async () => {
    const { container } = renderWithRouter(LandingPage);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument());
    expectNoFabrications(container);
  });

  it("has no accessibility violations", async () => {
    const { container } = renderWithRouter(LandingPage);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument());
    await expectNoA11yViolations(container);
  });
});

describe("TransparencyDashboard", () => {
  it("explains the pipeline without fake telemetry", async () => {
    const { container } = renderWithRouter(TransparencyDashboard);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument());
    expectNoFabrications(container);
  });

  it("has no accessibility violations", async () => {
    const { container } = renderWithRouter(TransparencyDashboard);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument());
    await expectNoA11yViolations(container);
  });
});

describe("WidgetGallery", () => {
  it("lists only the tool types the analyzer can actually choose", async () => {
    const { container } = renderWithRouter(WidgetGallery);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument());
    // Mirrors the analyzer prompt's enum: roi_calculator, readiness_quiz,
    // competitive_comparison, audit_tool, interactive_checklist.
    for (const name of [
      /ROI calculator/i,
      /Readiness quiz/i,
      /Audit tool/i,
      /Comparison tool/i,
      /Interactive checklist/i,
    ]) {
      expect(container.textContent).toMatch(name);
    }
    expectNoFabrications(container);
  });

  it("has no accessibility violations", async () => {
    const { container } = renderWithRouter(WidgetGallery);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument());
    await expectNoA11yViolations(container);
  });
});
