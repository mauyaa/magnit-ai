import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";
import { renderWithRouter } from "@/test/router";

import { LandingPage } from "./LandingPage";
import { TransparencyDashboard } from "./TransparencyDashboard";
import { WidgetGallery } from "./WidgetGallery";

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
  it("lets a visitor start with their real website from the first screen", async () => {
    renderWithRouter(LandingPage);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument());

    await userEvent.type(screen.getByLabelText(/your website address/i), "northsidedental.com");
    await userEvent.click(screen.getByRole("button", { name: /build from my website/i }));

    await waitFor(() =>
      expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument(),
    );
  });

  it("proves the value exchange before asking for an account", async () => {
    renderWithRouter(LandingPage);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument());

    expect(screen.getByRole("link", { name: /try finished examples/i })).toHaveAttribute(
      "href",
      "/examples",
    );
    expect(screen.getByText(/preview before signup/i)).toBeInTheDocument();
    expect(screen.getByText(/nothing publishes without you/i)).toBeInTheDocument();
    expect(screen.getByText(/what the business learns/i)).toBeInTheDocument();
  });

  it("rejects an incomplete website before leaving the landing page", async () => {
    renderWithRouter(LandingPage);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument());

    await userEvent.type(screen.getByLabelText(/your website address/i), "not-a-website");
    await userEvent.click(screen.getByRole("button", { name: /build from my website/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/complete website/i);
    expect(screen.getByLabelText(/your website address/i)).toHaveFocus();
  });

  it("keeps one dominant URL entry point", async () => {
    renderWithRouter(LandingPage);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument());

    expect(screen.getAllByLabelText(/your website address/i)).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: /build from my website/i })).toHaveLength(1);
    expect(screen.getByRole("heading", { name: /useful for the visitor/i })).toBeInTheDocument();
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
  it("explains the buyer journey without fake telemetry or pipeline jargon", async () => {
    const { container } = renderWithRouter(TransparencyDashboard);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument());
    expect(screen.getByText(/four steps\. a working outcome/i)).toBeInTheDocument();
    expect(container).not.toHaveTextContent(/deterministic stages/i);
    expectNoFabrications(container);
  });

  it("has no accessibility violations", async () => {
    const { container } = renderWithRouter(TransparencyDashboard);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument());
    await expectNoA11yViolations(container);
  });
});

describe("WidgetGallery", () => {
  it("opens with playable proof and business context", async () => {
    const { container } = renderWithRouter(WidgetGallery);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument());
    expect(screen.getByRole("tablist", { name: /lead magnet examples/i })).toBeInTheDocument();
    expect(screen.getByText(/visitor decides/i)).toBeInTheDocument();
    expect(screen.getByText("Business learns")).toBeInTheDocument();
    expectNoFabrications(container);
  });

  it("has no accessibility violations", async () => {
    const { container } = renderWithRouter(WidgetGallery);
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument());
    await expectNoA11yViolations(container);
  });
});
