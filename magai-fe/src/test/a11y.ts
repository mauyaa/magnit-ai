/**
 * Automated accessibility assertions using axe-core.
 *
 * Scoped to WCAG 2.1 A and AA, which is the bar PRODUCT.md commits to. Automated
 * checks catch roughly a third of real accessibility problems — missing labels,
 * contrast failures, invalid ARIA — so passing here is a floor, not proof of an
 * accessible experience. Keyboard and screen-reader walkthroughs still matter.
 */

import axe, { type AxeResults, type Result } from "axe-core";
import { expect } from "vitest";

const WCAG_AA_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

function formatViolations(violations: Result[]): string {
  return violations
    .map((violation) => {
      const targets = violation.nodes.map((node) => `      ${node.target.join(", ")}`).join("\n");
      return (
        `  [${violation.impact ?? "unknown"}] ${violation.id}: ${violation.help}\n` +
        `    ${violation.helpUrl}\n${targets}`
      );
    })
    .join("\n\n");
}

/** Run axe against `container` and fail the test with readable output. */
export async function expectNoA11yViolations(container: HTMLElement): Promise<void> {
  const results: AxeResults = await axe.run(container, {
    runOnly: { type: "tag", values: WCAG_AA_TAGS },
    // jsdom does not lay out or paint, so geometry- and paint-dependent rules
    // produce false results here. Contrast is verified against the design tokens
    // in DESIGN.md instead.
    rules: {
      "color-contrast": { enabled: false },
      "landmark-one-main": { enabled: false },
      region: { enabled: false },
    },
  });

  if (results.violations.length > 0) {
    expect.fail(
      `Found ${results.violations.length} accessibility violation(s):\n\n` +
        formatViolations(results.violations),
    );
  }
}
