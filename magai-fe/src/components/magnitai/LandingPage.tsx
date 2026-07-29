import { Link } from "@tanstack/react-router";
import { ArrowRight, Play } from "lucide-react";

import { IntentSystem } from "./IntentSystem";
import { OutputShowcase } from "./OutputShowcase";

/**
 * The landing page, rebuilt as a composition.
 *
 * The previous version was a wireframe with good fonts: 2,900px tall, roughly
 * 40% empty, every element left-aligned on one axis, and three naked paragraphs
 * where a real product page carries density. Worse, the demo — the single thing
 * that sells this — rendered a near-white card on our near-white paper, so the
 * centrepiece dissolved into the background.
 *
 * Three structural decisions fix that:
 *
 *   1. THE DEMO GETS A DARK STAGE. Every reference site anchors an otherwise
 *      light page with one ink panel (sensiq #0f0f16, eleken #1d1e22). Putting
 *      the demo on ink gives the page weight, makes every brand skin pop
 *      instead of dissolve, and lets the lime read at full strength.
 *
 *   2. THE PAGE SHOWS THE PRODUCT, NOT CLAIMS ABOUT IT. The embed snippet is
 *      real, the numbers are the ones the product tracks. A visitor should be
 *      able to work out what they get without reading a single adjective.
 *
 *   3. VERTICAL RHYTHM IS TIGHTENED. Sections are separated by content, not by
 *      160px of nothing.
 */

const STEPS = [
  {
    n: "01",
    title: "We read the business",
    body: "Your offer, audience, colours, type and voice—from one website address.",
  },
  {
    n: "02",
    title: "We build the right magnet",
    body: "A working calculator, quiz or audit shaped around what your buyers need to know.",
  },
  {
    n: "03",
    title: "You add one line",
    body: "Paste the embed into your existing site. Captured leads and performance appear in Magnit.",
  },
];

export function LandingPage() {
  return (
    <div className="text-foreground">
      {/* A single, product-level promise before the working proof. */}
      <section className="mx-auto flex min-h-[68vh] max-w-6xl items-center justify-center px-6 pb-14 pt-24 lg:px-8">
        <div className="w-full text-center">
          {/* Display face at regular weight, matching the auth hero and the
              tracking/leading pair the type system uses at display scale. It was
              `font-bold` sans, which made the product's two biggest headlines —
              this one and the sign-in screen — speak in different voices. */}
          <h1 className="mx-auto max-w-[18ch] text-balance font-display text-[clamp(2.75rem,6vw,5.5rem)] font-normal leading-[0.98] tracking-[-0.045em] text-foreground">
            Turn passive pages into <span className="headline-underline">moments</span> that
            convert.
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-balance text-base leading-7 text-muted-foreground">
            Calculators, quizzes and audits built from your own website — in your colours, your type
            and your voice. Embedded with one line.
          </p>

          <div className="mt-10 flex flex-col items-center justify-center gap-6 sm:flex-row">
            <Link to="/build" className="build-cta">
              <span className="build-cta-face">
                <span>Start building</span>
                <span className="build-cta-arrow">
                  <ArrowRight className="size-4" aria-hidden="true" />
                </span>
              </span>
            </Link>
            <Link to="/how-it-works" className="how-it-works-cta">
              <span>See how it works</span>
              <span className="how-it-works-cta-play" aria-hidden="true">
                <Play />
              </span>
            </Link>
          </div>
        </div>
      </section>

      <OutputShowcase />

      <IntentSystem />

      {/* ---- the three steps, with numerals carrying the structure ---- */}
      <section className="scroll-mt-20 border-t border-border">
        <div className="mx-auto max-w-6xl px-6 py-16 lg:px-8">
          <div className="grid gap-x-10 gap-y-10 sm:grid-cols-3">
            {STEPS.map(({ n, title, body }) => (
              <div key={n}>
                <div className="tabular font-mono text-sm text-muted-foreground">{n}</div>
                <h2 className="text-subheading mt-3 text-foreground">{title}</h2>
                <p className="mt-2 text-[15px] leading-relaxed text-muted-foreground">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---- the deliverable, shown rather than described ---- */}
      <section id="how-it-works" className="scroll-mt-20 border-t border-border">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 py-20 lg:grid-cols-2 lg:px-8">
          <div>
            <h2 className="text-title max-w-[16ch]">
              One line on your site. That's the whole job.
            </h2>
            <p className="text-body mt-5 max-w-md text-muted-foreground">
              Your tool lives on its own address. When we rebuild it — because you rebranded, or
              because it stopped answering — the address doesn't change, so the snippet never does
              either.
            </p>
            <Link to="/how-it-works" className="btn btn-secondary mt-8">
              See exactly what runs
            </Link>
          </div>

          <div className="surface-sunken overflow-x-auto p-5">
            <pre className="font-mono text-[13px] leading-relaxed text-foreground">
              <code>{`<iframe
  src="https://your-tool.magnitai.app"
  width="100%"
  height="640"
  style="border:0"
></iframe>`}</code>
            </pre>
          </div>
        </div>
      </section>

      {/*
        The one claim a competitor cannot copy this quarter.

        Every other tool in this category generates from a prompt or a URL — that
        is table stakes now, not a differentiator. None of them keeps watching
        afterwards. This used to be a subordinate clause in the paragraph above
        ("when we rebuild it — because you rebranded"), which is where a
        product's only real moat goes to die.

        The limitation is stated in the same breath as the promise, deliberately.
        "It repairs itself" invites the reader to imagine it fixes anything, and
        the first time it does not, the whole claim reads as marketing.
      */}
      <section className="scroll-mt-20 border-t border-border bg-secondary/40">
        <div className="mx-auto max-w-6xl px-6 py-20 lg:px-8">
          <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            After it ships · Included from Studio
          </span>
          <h2 className="text-title mt-5 max-w-[20ch]">
            Everyone builds you a tool. We keep it from going stale.
          </h2>
          <p className="text-body mt-5 max-w-2xl text-muted-foreground">
            A lead magnet decays quietly. You change your brand, or a deployment stops answering,
            and the thing sitting on your busiest page is off-brand or broken — usually noticed by a
            customer, weeks later. Magnitai checks every published tool on a schedule and fixes both
            without being asked.
          </p>

          <div className="mt-10 grid gap-px overflow-hidden rounded-[--radius-surface] border border-border bg-border sm:grid-cols-3">
            {[
              {
                title: "It re-reads your site",
                body: "Colours, heading type and layout are compared against what the tool was built from.",
              },
              {
                title: "It rebuilds on drift",
                body: "A real change triggers a regenerate and redeploy. The embed address never moves, so your snippet never changes.",
              },
              {
                title: "It republishes if it dies",
                body: "An unreachable address brings the last known-good build back, without a rebuild.",
              },
            ].map((item) => (
              <div key={item.title} className="bg-card p-6">
                <h3 className="text-sm font-medium text-foreground">{item.title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.body}</p>
              </div>
            ))}
          </div>

          <p className="mt-6 max-w-2xl text-sm leading-6 text-muted-foreground">
            What it deliberately does not do: touch your page. Tools run in a sandboxed iframe, so
            your CSS cannot reach in and break their layout — and there is nothing there for us to
            repair. Every check is written to the tool's timeline, including the ones that found
            nothing.
          </p>
        </div>
      </section>

      {/* ---- close ---- */}
      <section id="pricing" className="scroll-mt-20 border-t border-border">
        <div className="mx-auto max-w-6xl px-6 py-20 lg:px-8">
          <div className="grid items-end gap-8 lg:grid-cols-[0.85fr_1.15fr]">
            <div>
              <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                Plans
              </span>
              <h2 className="text-title mt-4 max-w-[12ch]">
                Start with the result. Upgrade when it earns its place.
              </h2>
              <p className="mt-5 max-w-md text-sm leading-6 text-muted-foreground">
                The first two directions are yours to compare before entering a workspace.
              </p>
            </div>

            <div className="grid overflow-hidden rounded-[1.6rem] border border-border bg-card shadow-card sm:grid-cols-2">
              <article className="p-7 sm:p-8">
                <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                  Explore
                </span>
                <div className="mt-5 text-4xl font-medium tracking-[-0.05em]">$0</div>
                <ul className="mt-7 space-y-3 text-sm text-muted-foreground">
                  {["One website read", "Two tailored directions", "Choose before signup"].map(
                    (item) => (
                      <li key={item} className="flex items-center gap-2.5">
                        <span className="size-1.5 rounded-full bg-foreground" />
                        {item}
                      </li>
                    ),
                  )}
                </ul>
                <Link to="/build" className="btn btn-secondary mt-8 w-full">
                  See my directions
                </Link>
              </article>

              <article className="bg-inverse p-7 text-white sm:p-8">
                <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-inverse-subtle">
                  Studio
                </span>
                <div className="mt-5 text-2xl font-medium tracking-[-0.035em]">
                  Continue inside Magnit
                </div>
                <ul className="mt-7 space-y-3 text-sm text-inverse-muted">
                  {["Build and refine", "Publish to your website", "Track every response"].map(
                    (item) => (
                      <li key={item} className="flex items-center gap-2.5">
                        <span className="size-1.5 rounded-full bg-brand-solid" />
                        {item}
                      </li>
                    ),
                  )}
                </ul>
                <Link
                  to="/build"
                  className="mt-8 flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-brand-solid text-sm font-semibold text-white"
                >
                  Start with the preview
                  <ArrowRight className="size-4" />
                </Link>
              </article>
            </div>
          </div>
        </div>
      </section>

      <footer id="faq" className="scroll-mt-20 border-t border-border">
        <div className="mx-auto max-w-6xl px-6 py-10 lg:px-8">
          <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
            {/*
             * Wordmark only, and it is the way home.
             *
             * The mark repeated here read as a plant rather than as a monogram,
             * and a decorative glyph in a footer is exactly the kind of element
             * that makes a page feel assembled. The name alone is enough this
             * far down the page — the mark has already done its work in the nav.
             */}
            <Link
              to="/"
              aria-label="Magnitai — back to top"
              className="text-lg font-semibold tracking-[-0.03em] text-foreground transition-opacity hover:opacity-70"
            >
              magnitai
            </Link>
            <nav className="flex flex-wrap gap-x-6 gap-y-2" aria-label="Footer">
              {[
                { label: "How it works", to: "/how-it-works" },
                { label: "What we build", to: "/examples" },
                { label: "Pricing", to: "/pricing" },
                { label: "Privacy", to: "/privacy" },
                { label: "Terms", to: "/terms" },
              ].map(({ label, to }) => (
                <Link
                  key={to}
                  to={to}
                  className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  {label}
                </Link>
              ))}
            </nav>
            <p className="text-sm text-muted-foreground">© 2026 Magnitai</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
