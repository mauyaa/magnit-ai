import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";

import { GuidedBuilder } from "./GuidedBuilder";

function setup(onBuild = vi.fn()) {
  render(
    <GuidedBuilder
      domain="northsidedental.com"
      pending={false}
      error={null}
      onBack={vi.fn()}
      onBuild={onBuild}
    />,
  );
  return onBuild;
}

function block(label: RegExp) {
  return screen.getByRole("heading", { name: label }).closest("section")!;
}

describe("GuidedBuilder", () => {
  it("starts open-ended with every structured detail handled by AI", async () => {
    setup();

    expect(screen.getByLabelText(/what should magnitai build/i)).toBeInTheDocument();
    expect(await screen.findAllByRole("button", { name: /^magnitai decides$/i })).toHaveLength(8);
    expect(screen.getByText("0", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByText("8", { selector: "span" })).toBeInTheDocument();
  });

  it("reveals any detail the user chooses to direct", async () => {
    setup();
    const audience = block(/audience/i);

    await userEvent.click(within(audience).getByRole("button", { name: /^magnitai decides$/i }));

    expect(await within(audience).findByRole("textbox", { name: /audience/i })).toBeInTheDocument();
    expect(
      within(audience).getByRole("button", { name: /let magnitai decide/i }),
    ).toBeInTheDocument();
  });

  it("tracks user direction without treating delegated choices as incomplete", async () => {
    setup();
    await userEvent.type(
      screen.getByLabelText(/what should magnitai build/i),
      "Build a savings planner",
    );

    const tone = block(/tone/i);
    await userEvent.click(within(tone).getByRole("button", { name: /^magnitai decides$/i }));

    expect(screen.getByText(/core idea/i)).toBeInTheDocument();
    expect(
      within(screen.getByRole("complementary", { name: /lead magnet brief/i })).getByText("Tone"),
    ).toBeInTheDocument();
    expect(screen.getByText("2", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByText("7", { selector: "span" })).toBeInTheDocument();
  });

  it("sends open direction plus only the structured details the user took", async () => {
    const onBuild = setup();
    await userEvent.type(
      screen.getByLabelText(/what should magnitai build/i),
      "Build a savings planner",
    );

    const audience = block(/audience/i);
    await userEvent.click(within(audience).getByRole("button", { name: /^magnitai decides$/i }));
    await userEvent.type(
      within(audience).getByRole("textbox", { name: /audience/i }),
      "Operations leaders",
    );

    const offer = block(/^offer$/i);
    await userEvent.click(within(offer).getByRole("button", { name: /^magnitai decides$/i }));
    await userEvent.type(
      within(offer).getByRole("textbox", { name: /offer/i }),
      "A free workflow review",
    );

    await userEvent.click(screen.getByRole("button", { name: /create my lead magnets/i }));

    expect(onBuild).toHaveBeenCalledTimes(1);
    const brief = onBuild.mock.calls[0][0];
    expect(brief.intent).toBe("Build a savings planner");
    expect(brief.audience).toBe("Operations leaders");
    expect(brief.offer).toBe("A free workflow review");
    expect(brief.tone).toBe("match_site");
    expect(brief.preferred_type).toBeNull();
  });

  it("discards a value when the user hands that detail back to AI", async () => {
    const onBuild = setup();
    const audience = block(/audience/i);
    await userEvent.click(within(audience).getByRole("button", { name: /^magnitai decides$/i }));
    await userEvent.type(
      within(audience).getByRole("textbox", { name: /audience/i }),
      "Homeowners",
    );
    await userEvent.click(within(audience).getByRole("button", { name: /let magnitai decide/i }));

    await userEvent.click(screen.getByRole("button", { name: /create my lead magnets/i }));
    expect(onBuild.mock.calls[0][0].audience).toBe("");
  });

  it("keeps extra free-form direction outside the structured controls", async () => {
    const onBuild = setup();
    await userEvent.type(
      screen.getByLabelText(/add anything the controls did not cover/i),
      "Never mention pricing",
    );

    await userEvent.click(screen.getByRole("button", { name: /create my lead magnets/i }));
    expect(onBuild.mock.calls[0][0].instructions).toBe("Never mention pricing");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <GuidedBuilder
        domain="northsidedental.com"
        pending={false}
        error={null}
        onBack={vi.fn()}
        onBuild={vi.fn()}
      />,
    );
    await expectNoA11yViolations(container);
  });
});
