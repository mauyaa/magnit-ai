import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";

import { MagnitaiLogo, MagnitaiMark, MARK_ASPECT } from "./MagnitaiLogo";

describe("MagnitaiLogo", () => {
  it("uses the supplied monogram artwork without redrawing it", () => {
    const { container } = render(<MagnitaiMark />);
    expect(container.querySelector("img")).toHaveAttribute("src", "/magnit-logo-cropped.png");
  });

  it("does not add colour layers over the supplied mark", () => {
    const { container } = render(<MagnitaiMark />);
    expect(container.querySelector("svg")).not.toBeInTheDocument();
  });

  it("is laid out from its real aspect ratio", () => {
    // The mark is markedly wider than tall (100 x 71.45). Sizing it square
    // would either squash it or make it tower over the wordmark.
    expect(MARK_ASPECT).toBeCloseTo(100 / 71.45, 4);
    const { container } = render(<MagnitaiLogo showWordmark={false} />);
    expect(container.querySelector("img")).toHaveClass("w-11");
  });

  it("shows the wordmark by default and hides it on request", () => {
    const { rerender } = render(<MagnitaiLogo />);
    expect(screen.getByText("magnitai")).toBeInTheDocument();
    rerender(<MagnitaiLogo showWordmark={false} />);
    expect(screen.queryByText("magnitai")).not.toBeInTheDocument();
  });

  it("hides the decorative mark from assistive tech", async () => {
    // The wordmark already carries the name; a second announcement is noise.
    const { container } = render(<MagnitaiLogo />);
    expect(container.querySelector("img")).toHaveAttribute("aria-hidden", "true");
    await expectNoA11yViolations(container);
  });
});
