import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * Guards on the design tokens themselves.
 *
 * These pin the specific defects the palette rebuild fixed, because every one
 * of them is invisible in review — the CSS is valid, the app renders, nothing
 * fails. They only show up as "it looks a bit flat" months later.
 *
 * jsdom cannot resolve oklch() to rgb, so this reads the stylesheet as text and
 * asserts on the declared values. Measured contrast is verified in the browser
 * against the running app; what is checked here is that the *structure* of the
 * system stays intact.
 */

// Resolved from the project root: under jsdom, import.meta.url is an http URL
// rather than a file one, so fileURLToPath cannot be used here.
const CSS = readFileSync(resolve(process.cwd(), "src/styles.css"), "utf8");

/** Pull one custom property's declared value out of the :root block. */
function token(name: string): string {
  const match = CSS.match(new RegExp(`^\\s*--${name}:\\s*([^;]+);`, "m"));
  if (!match) throw new Error(`token --${name} is not declared`);
  return match[1].trim();
}

/** Follow one level of var() indirection so semantic tokens resolve to a colour. */
function resolved(name: string): string {
  const value = token(name);
  const ref = value.match(/^var\(--([\w-]+)\)$/);
  return ref ? token(ref[1]) : value;
}

describe("colour tokens", () => {
  it("keeps the page ground and cards visibly apart", () => {
    // The original bug: background sat at L 0.985 and card at L 1.0. A 1.5%
    // difference is invisible, so nothing on any screen looked layered — which
    // was most of why the interface read as flat and unfinished.
    const bg = resolved("background");
    const card = resolved("card");
    expect(bg).not.toBe(card);

    const lightness = (v: string) => Number(v.match(/oklch\(([\d.]+)/)?.[1]);
    const gap = Math.abs(lightness(card) - lightness(bg));
    expect(gap).toBeGreaterThan(0.02);
  });

  it("uses Celery as the accent", () => {
    // oklch(0.953 0.105 124) resolves to #e1fcad. Nudging it leaves the
    // interface and the palette as two greens that nearly agree, which reads as
    // sloppy rather than as a second colour.
    expect(resolved("brand")).toBe("oklch(0.953 0.105 124)");
  });

  /**
   * The single most dangerous pairing in this palette.
   *
   * Celery sits at L 95, so white on it measures 1.10:1 — invisible. The token
   * that decides what sits on the accent was `--n-0` (white) while the accent
   * was a mid-dark red, and carrying that over unchanged would have shipped
   * white labels on a near-white green across the product.
   */
  it("puts ink on the accent, never white", () => {
    expect(resolved("accent-foreground")).toBe(resolved("ink"));
    expect(resolved("accent-foreground")).not.toBe(resolved("n-0"));
  });

  it("keeps a separate, darker green for anything carrying a white label", () => {
    // --brand-solid is L 0.52 at the accent's hue: 5.25:1 against white. If the
    // two are ever collapsed into one token, every accent button fails.
    expect(resolved("brand-solid")).not.toBe(resolved("brand"));
  });

  it("carries the same accent onto dark panels", () => {
    // The red this replaced measured 4.24:1 on ink and needed a lifted variant.
    // Celery reaches 16.7:1, so the dark side uses the actual brand colour.
    expect(resolved("brand-on-inverse")).toBe(resolved("brand"));
  });

  /**
   * The signature red survives the move to Celery.
   *
   * It is no longer the brand, but it still does one job: the display word in
   * the output showcase, on the ink stage. That rule pointed at `--accent`, so
   * changing the accent turned the loudest word on the landing page into a
   * near-white green on near-black. Giving it its own token is what stops the
   * next palette change doing the same thing.
   */
  it("keeps the signature red for display type on ink", () => {
    expect(resolved("accent-hot")).toBe("oklch(0.618 0.244 28)");
    expect(resolved("accent-hot")).not.toBe(resolved("accent"));
  });

  it("uses that red for the showcase word rather than the accent", () => {
    expect(CSS).toMatch(/\.showcase-wing-right\s*>\s*span\s*\{[^}]*color:\s*var\(--accent-hot\)/s);
  });

  it("gives the assisted paths their own surface", () => {
    // Oasis is what makes the two build routes separable by colour before a
    // word is read. If it collapses into the accent, that distinction is gone.
    expect(resolved("oasis")).not.toBe(resolved("brand"));
  });

  it("does not paint errors in the brand colour", () => {
    expect(resolved("destructive")).not.toBe(resolved("brand"));
    expect(resolved("destructive")).not.toBe(resolved("brand-solid"));
  });

  it("does not give three semantic roles the same value", () => {
    // --secondary, --muted and --accent were all oklch(0.965 0.008 45): three
    // tokens, one colour, so no component could express hierarchy even when it
    // asked for it.
    const roles = ["secondary", "muted", "accent"].map(resolved);
    expect(new Set(roles).size).toBe(roles.length);
  });

  it("keeps a real neutral ramp rather than one grey", () => {
    const steps = ["n-0", "n-25", "n-50", "n-100", "n-200", "n-300", "n-400", "n-500", "n-600"];
    const values = steps.map((s) => token(s));
    expect(new Set(values).size).toBe(steps.length);

    // Monotonically darker, so a component can pick a step by number and trust
    // that a higher number is always a stronger colour.
    const lightness = values.map((v) => Number(v.match(/oklch\(([\d.]+)/)?.[1]));
    for (let i = 1; i < lightness.length; i++) {
      expect(lightness[i]).toBeLessThan(lightness[i - 1]);
    }
  });

  it("states every colour in oklch", () => {
    // The project rule, and the reason the ramps interpolate evenly.
    const root = CSS.slice(CSS.indexOf(":root {"), CSS.indexOf("@layer base"))
      // Comments are stripped first: they legitimately cite hex values when
      // explaining what an oklch() triple resolves to.
      .replace(/\/\*[\s\S]*?\*\//g, "");
    const hexes = root.match(/#[0-9a-f]{3,8}\b/gi) ?? [];
    expect(hexes).toEqual([]);
  });

  it("has no dark-mode block that would silently override light values", () => {
    // The product is deliberately light-only. A stale .dark block is how a
    // half-maintained second theme leaks into screenshots.
    expect(CSS).not.toMatch(/^\.dark\s*\{/m);
  });
});

describe("button system", () => {
  it("defines every variant the app uses", () => {
    for (const variant of [".btn-primary", ".btn-accent", ".btn-secondary", ".btn-ghost"]) {
      expect(CSS).toContain(variant);
    }
  });

  it("lets a caller size a button without fighting specificity", () => {
    /*
     * `.btn` used to declare `font-size` normally, which beat Tailwind's own
     * type scale. Every one of the 79 places that wrote `btn ... text-sm` or
     * `btn ... text-xs` therefore rendered at the same 15px, so quiet
     * secondary actions shouted at exactly the volume of the primary one — and
     * nothing in the markup showed it, because the class was right there.
     *
     * Stated inside `:where()` the default carries zero specificity: `.btn`
     * alone still sizes itself, and a utility beside it wins.
     */
    const zeroSpecificity = CSS.slice(CSS.indexOf(":where(.btn)"));
    const block = zeroSpecificity.slice(0, zeroSpecificity.indexOf("}"));
    expect(block).toContain("font-size");

    const btnBlock = CSS.slice(CSS.indexOf("\n  .btn {"));
    expect(btnBlock.slice(0, btnBlock.indexOf("}"))).not.toContain("font-size");
  });

  it("gives the primary and accent buttons a real hover state", () => {
    // After the accent change, `hover:bg-primary` on a `bg-foreground` button
    // became a no-op — every primary action in the product had quietly lost its
    // hover. These rules are what replaced it.
    expect(CSS).toMatch(/\.btn-primary:hover:not\(:disabled\)\s*\{[^}]*background/);
    expect(CSS).toMatch(/\.btn-accent:hover:not\(:disabled\)\s*\{[^}]*background/);
  });
});

describe("the inverse (ink panel) ramp", () => {
  it("declares a named step for every job text does on a dark panel", () => {
    // Before these existed, a dark card set its text with white at /38, /40,
    // /45, /50, /55, /68 and /70 — seven values doing three jobs, none of them
    // measured. Naming the steps is what makes them checkable at all.
    for (const step of [
      "inverse",
      "inverse-raised",
      "inverse-foreground",
      "inverse-muted",
      "inverse-subtle",
      "inverse-border",
      "brand-on-inverse",
    ]) {
      expect(() => token(step)).not.toThrow();
    }
  });

  /**
   * Under the red accent this asserted the opposite — that the dark-panel step
   * must *differ* from the accent, because red measured 4.24:1 on ink and had
   * to be lifted to a separate value to clear AA.
   *
   * Celery removes the need: at L 95 it reaches 16.7:1 on ink, so the accent is
   * the same colour on both sides of the system. What still has to hold is that
   * whatever this token resolves to is legible on ink, which is now satisfied by
   * pointing at the accent rather than by maintaining a second value in step.
   */
  it("carries an accent that is legible on ink", () => {
    const lightness = (v: string) => Number(v.match(/oklch\(([\d.]+)/)?.[1]);
    expect(lightness(resolved("brand-on-inverse"))).toBeGreaterThan(
      lightness(resolved("ink")) + 0.4,
    );
  });

  it("keeps the chart's remainder neutral distinct from its lead colour", () => {
    // The activity chart is a part-to-whole: the accent is the converted share
    // and the neutral is everyone else. One value for both erases the reading.
    expect(resolved("chart-lead")).not.toBe(resolved("chart-rest"));
  });
});

describe("the landing CTA green", () => {
  /*
   * The app once shipped two brand colours at once: the tokens and the logo
   * said red, while the dashboard, the nav, analytics, settings, the auth
   * screens and the checkout hardcoded an acid lime left over from a previous
   * identity — 72 hex literals that no token could reach. That split is most of
   * what made the product look assembled rather than designed, and it survived
   * precisely because nothing failed when it drifted.
   *
   * The lime itself is not the problem and stays: it is the landing page's own
   * green, brighter than Celery on purpose, because the hero button is the
   * loudest thing on the marketing page and should be louder than the accent
   * used inside the product.
   *
   * What has to hold is that it is declared exactly once, scoped to `.build-cta`
   * — one place to change it, and no way for it to creep back into the app
   * screens. Every *other* green from the old identity stays retired.
   */
  const RETIRED = ["#e4ff72", "#e3ff71", "#9ac11b", "#a7cb26", "#8eae1c", "#63810e"];

  it("declares the landing green exactly once, inside .build-cta", () => {
    expect(CSS.match(/#d8ff3e/gi) ?? []).toHaveLength(1);
    expect(CSS).toMatch(/\.build-cta\s*\{[^}]*--landing-cta:\s*#d8ff3e;/s);
  });

  it("keeps it out of the accent token, which the product screens use", () => {
    // The two greens have different jobs. Collapsing them puts marketing volume
    // on every chip and badge in the dashboard.
    expect(resolved("brand").toLowerCase()).not.toContain("#d8ff3e");
  });

  it("keeps every other old lime out of the stylesheet", () => {
    for (const hex of RETIRED) {
      expect(CSS.toLowerCase()).not.toContain(hex);
    }
  });

  it("is gone from every component", async () => {
    const { readdirSync, statSync } = await import("node:fs");
    const { join } = await import("node:path");

    const walk = (dir: string): string[] =>
      readdirSync(dir).flatMap((entry) => {
        const full = join(dir, entry);
        return statSync(full).isDirectory()
          ? walk(full)
          : /\.tsx?$/.test(entry) && !entry.endsWith(".test.tsx")
            ? [full]
            : [];
      });

    const offenders = walk(resolve(process.cwd(), "src"))
      .filter((file) => !file.includes("styles.test"))
      .flatMap((file) => {
        const body = readFileSync(file, "utf8").toLowerCase();
        return RETIRED.filter((hex) => body.includes(hex)).map((hex) => `${file}: ${hex}`);
      });

    expect(offenders).toEqual([]);
  });
});

/**
 * The small caps label.
 *
 * The workspace had seven versions of one label — 9, 10 and 11px crossed with
 * five letter-spacings, three weights and both families — because each screen
 * re-derived it instead of reaching for a class. Nobody chose those
 * differences. They accumulated, and the result was a product that felt
 * approximate without any single screen being wrong, which is the hardest kind
 * of inconsistency to argue anyone into fixing.
 *
 * Scoped to the workspace on purpose. The marketing pages have their own voice
 * and are not covered here; this is the ground a customer works on every day,
 * and it is the ground that has to be quiet.
 */
describe("the workspace's small caps label", () => {
  const WORKSPACE = [
    "src/routes/dashboard",
    "src/routes/analytics.tsx",
    "src/components/magnitai/shell",
    "src/components/magnitai/EmbedCodePanel.tsx",
    "src/components/magnitai/PublishChecklist.tsx",
    "src/components/magnitai/LeadDeliveryPanel.tsx",
  ];

  const workspaceFiles = async (): Promise<string[]> => {
    const { readdirSync, statSync, existsSync } = await import("node:fs");
    const { join } = await import("node:path");

    const walk = (target: string): string[] => {
      if (!existsSync(target)) return [];
      if (!statSync(target).isDirectory()) {
        return /\.tsx?$/.test(target) && !target.includes(".test.") ? [target] : [];
      }
      return readdirSync(target).flatMap((entry) => walk(join(target, entry)));
    };

    return WORKSPACE.flatMap((entry) => walk(resolve(process.cwd(), entry)));
  };

  it("is defined once, as a class", () => {
    expect(CSS.match(/\.group-label\s*\{/g)).toHaveLength(1);
  });

  it("decides the typography and leaves the colour to the surface", () => {
    // This label sits on paper, on ink panels and on a customer's own brand
    // colour. Baking one colour in would force every caller to override it,
    // which is how a shared class quietly becomes seven again.
    const block = CSS.slice(CSS.indexOf(".group-label {"));
    const body = block.slice(0, block.indexOf("}"));

    expect(body).toContain("text-transform: uppercase");
    expect(body).toContain("letter-spacing");
    expect(body).toContain("font-size");
    expect(body).not.toContain("color:");
  });

  it("is not hand-rolled anywhere in the workspace", async () => {
    const offenders: string[] = [];
    for (const file of await workspaceFiles()) {
      const body = readFileSync(file, "utf8");
      // A tracked, uppercased label written out by hand rather than named.
      for (const match of body.match(/uppercase tracking-\[[^\]]+\]/g) ?? []) {
        offenders.push(`${file}: ${match}`);
      }
    }

    expect(offenders).toEqual([]);
  });

  it("does not reintroduce an off-scale type size on a workspace screen", async () => {
    /*
     * 9, 10, 11 and 12px were all written by hand as captions, between and
     * below the scale's own caption step. Four unnamed sizes doing one job,
     * none of them chosen — each was simply what fitted the box that day.
     *
     * A bracketed pixel size is the tell. If a screen genuinely needs a step
     * the scale does not have, the scale should gain it by name rather than
     * one component quietly inventing it.
     */
    const offenders: string[] = [];
    for (const file of await workspaceFiles()) {
      const body = readFileSync(file, "utf8");
      for (const match of body.match(/text-\[\d+(?:\.\d+)?px\]/g) ?? []) {
        offenders.push(`${file}: ${match}`);
      }
    }

    expect(offenders).toEqual([]);
  });
});

/**
 * The display face.
 *
 * Iowan Old Style ships with macOS and with essentially nothing else, so the
 * fallback chain is not decoration — it is what most visitors actually see.
 * This serif was once hardcoded at several call sites with three different
 * chains, so the same "display face" resolved to Palatino in one component and
 * Georgia in another. One token, declared once, is the fix; these pin it.
 */
describe("the display face", () => {
  it("is declared exactly once, as a token", () => {
    expect(CSS.match(/Iowan Old Style/g) ?? []).toHaveLength(1);
    expect(token("font-display")).toContain("Iowan Old Style");
  });

  it("degrades through a designed serif rather than to Times", () => {
    const stack = token("font-display");
    for (const fallback of ["Palatino Linotype", "Book Antiqua", "Palatino", "Georgia"]) {
      expect(stack).toContain(fallback);
    }
  });

  /**
   * Product chrome stays on the sans. A serif at 13px in a dense table is a
   * costume; the portfolio this system borrows from uses its serif at display
   * scale only, and so does this.
   */
  it("is not what in-product headings use", () => {
    expect(token("font-heading")).not.toContain("Iowan");
    expect(token("font-heading")).toContain("Geist");
  });

  it("is reached through the token, never re-typed in a component", async () => {
    const { readdirSync, statSync } = await import("node:fs");
    const { join } = await import("node:path");

    const walk = (dir: string): string[] =>
      readdirSync(dir).flatMap((entry) => {
        const full = join(dir, entry);
        return statSync(full).isDirectory()
          ? walk(full)
          : /\.tsx?$/.test(entry) && !entry.endsWith(".test.tsx")
            ? [full]
            : [];
      });

    // InteractiveWidgetDemo is exempt: its serifs are simulated *customer*
    // brands — a law firm, a dental practice — and are meant to differ from ours.
    // Test files are exempt for the obvious reason that this one names the face.
    const offenders = walk(resolve(process.cwd(), "src"))
      .filter((file) => !file.includes("InteractiveWidgetDemo"))
      .filter((file) => !/\.test\.tsx?$/.test(file))
      .filter((file) => readFileSync(file, "utf8").includes("Iowan Old Style"));

    expect(offenders).toEqual([]);
  });
});
