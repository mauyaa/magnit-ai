import { Link } from "@tanstack/react-router";
import { ArrowRight, Check, MapPin, Target } from "lucide-react";

import { SHOWCASE } from "@/lib/showcase";
import { DecisionPreview } from "./DecisionPreview";

const EXAMPLE = SHOWCASE[1];

/**
 * The product's value exchange, shown as one complete story.
 *
 * The old landing page displayed three unrelated visual specimens, then a
 * separate website-reading demo. Visitors had to infer how any of it became a
 * useful business lead. This uses the real decision renderer and puts the
 * visitor outcome beside the business signal it creates.
 */
export function ConversionProof() {
  const decision = EXAMPLE.architect.decision;

  return (
    <section
      className="editorial-grid-dark relative overflow-hidden bg-inverse text-inverse-foreground"
      aria-labelledby="conversion-proof-title"
    >
      <div className="relative mx-auto max-w-6xl px-6 py-16 lg:px-8 lg:py-20">
        <header className="grid gap-5 border-b border-inverse-border pb-8 lg:grid-cols-[1fr_auto] lg:items-end">
          <div>
            <span className="font-mono text-[10px] uppercase tracking-[0.17em] text-brand-on-inverse">
              A complete value exchange
            </span>
            <h2
              id="conversion-proof-title"
              className="mt-4 max-w-[17ch] font-display text-[clamp(2.5rem,5vw,4.6rem)] font-normal leading-[0.94] tracking-[-0.05em]"
            >
              Useful for the visitor. Actionable for the business.
            </h2>
          </div>
          <Link
            to="/examples"
            className="group inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-inverse-foreground"
          >
            Try finished examples
            <ArrowRight
              className="size-4 transition-transform group-hover:translate-x-1"
              aria-hidden="true"
            />
          </Link>
        </header>

        <div className="mt-8 grid gap-5 lg:grid-cols-[1.08fr_0.92fr]">
          <article className="overflow-hidden rounded-[1.75rem] bg-brand text-foreground shadow-float">
            <div className="flex items-center justify-between border-b border-foreground/15 px-5 py-4">
              <span className="text-xs font-semibold">What the visitor experiences</span>
              <span className="font-mono text-[9px] uppercase tracking-[0.14em] opacity-55">
                Live product demo
              </span>
            </div>
            <div className="px-5 sm:px-8">
              <DecisionPreview architect={EXAMPLE.architect} />
            </div>
          </article>

          <article className="flex flex-col rounded-[1.75rem] border border-inverse-border bg-inverse-raised p-5 sm:p-7">
            <div>
              <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-inverse-subtle">
                What the business learns
              </span>
              <h3 className="mt-3 max-w-[16ch] text-3xl font-medium leading-[1] tracking-[-0.045em]">
                More than a name and email.
              </h3>
            </div>

            <div className="mt-8 divide-y divide-inverse-border border-y border-inverse-border">
              {[
                {
                  icon: Check,
                  term: "Result delivered",
                  detail: decision?.value_before_gate,
                },
                {
                  icon: Target,
                  term: "Intent captured",
                  detail: decision?.qualification_goal,
                },
                {
                  icon: MapPin,
                  term: "Best next step",
                  detail: decision?.primary_cta,
                },
              ].map(({ icon: Icon, term, detail }) => (
                <div key={term} className="grid grid-cols-[1.75rem_1fr] gap-3 py-4">
                  <Icon className="mt-0.5 size-4 text-brand-on-inverse" aria-hidden="true" />
                  <div>
                    <p className="text-xs font-medium text-inverse-foreground">{term}</p>
                    <p className="mt-1 text-sm leading-6 text-inverse-muted">{detail}</p>
                  </div>
                </div>
              ))}
            </div>

            <p className="mt-auto pt-6 text-sm leading-6 text-inverse-muted">
              The visitor receives their result before contact details are requested. Their answers,
              score and chosen next step arrive together in the lead record.
            </p>
          </article>
        </div>
      </div>
    </section>
  );
}
