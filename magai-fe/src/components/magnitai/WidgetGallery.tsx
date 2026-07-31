import { Link } from "@tanstack/react-router";
import { ArrowRight, ChartNoAxesCombined, MapPin, Target } from "lucide-react";
import { useState } from "react";

import { SHOWCASE } from "@/lib/showcase";
import { DecisionPreview } from "./DecisionPreview";
import { MarketingFooter } from "./MarketingFooter";

export function WidgetGallery() {
  const [openId, setOpenId] = useState(SHOWCASE[0].id);
  const open = SHOWCASE.find((example) => example.id === openId) ?? SHOWCASE[0];
  const decision = open.architect.decision;

  return (
    <>
      <main>
        <section className="mx-auto max-w-6xl px-6 pb-12 pt-36 lg:px-8 lg:pb-16 lg:pt-44">
          <div className="grid items-end gap-10 lg:grid-cols-[1.05fr_0.95fr]">
            <div>
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Playable examples
              </span>
              <h1 className="mt-5 max-w-[12ch] text-balance font-display text-[clamp(3.2rem,6.3vw,6rem)] font-normal leading-[0.9] tracking-[-0.055em]">
                See what a qualified lead magnet feels like.
              </h1>
            </div>
            <div className="border-t border-foreground pt-5 lg:mb-2">
              <p className="max-w-md text-base leading-7 text-muted-foreground">
                Open a finished calculator, quiz or audit. Answer it as a visitor, reach the result
                and see what the business learns—no account required.
              </p>
              <Link to="/build" className="btn btn-primary mt-7">
                Build from my website
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-6 pb-24 lg:px-8">
          <div
            className="flex flex-wrap gap-2 border-t border-border pt-7"
            role="tablist"
            aria-label="Lead magnet examples"
          >
            {SHOWCASE.map((example) => {
              const selected = example.id === open.id;
              return (
                <button
                  key={example.id}
                  type="button"
                  role="tab"
                  aria-selected={selected}
                  aria-controls="example-panel"
                  onClick={() => setOpenId(example.id)}
                  className={`rounded-full border px-4 py-2 text-sm transition-colors motion-reduce:transition-none ${
                    selected
                      ? "border-foreground bg-foreground text-background"
                      : "border-border bg-card text-muted-foreground hover:border-foreground/30 hover:text-foreground"
                  }`}
                >
                  {example.business}
                </button>
              );
            })}
          </div>

          <div
            id="example-panel"
            role="tabpanel"
            className="mt-6 grid items-start gap-6 lg:grid-cols-[0.82fr_1.18fr]"
          >
            <article className="surface overflow-hidden">
              <div className="border-b border-border p-6">
                <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                  {open.sector}
                </span>
                <h2 className="mt-3 text-2xl font-medium tracking-[-0.035em]">{open.business}</h2>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">{open.reasoning}</p>
              </div>

              <div className="divide-y divide-border">
                <div className="grid grid-cols-[1.5rem_1fr] gap-3 p-5">
                  <Target className="mt-0.5 size-4 text-brand-solid" aria-hidden="true" />
                  <div>
                    <p className="text-xs font-medium text-muted-foreground">Visitor decides</p>
                    <p className="mt-1 text-sm leading-6">{decision?.buyer_question}</p>
                  </div>
                </div>
                <div className="grid grid-cols-[1.5rem_1fr] gap-3 p-5">
                  <ChartNoAxesCombined
                    className="mt-0.5 size-4 text-brand-solid"
                    aria-hidden="true"
                  />
                  <div>
                    <p className="text-xs font-medium text-muted-foreground">Business learns</p>
                    <p className="mt-1 text-sm leading-6">{decision?.qualification_goal}</p>
                  </div>
                </div>
                <div className="grid grid-cols-[1.5rem_1fr] gap-3 p-5">
                  <MapPin className="mt-0.5 size-4 text-brand-solid" aria-hidden="true" />
                  <div>
                    <p className="text-xs font-medium text-muted-foreground">Best placement</p>
                    <p className="mt-1 text-sm leading-6">{decision?.recommended_placement}</p>
                  </div>
                </div>
              </div>

              <div className="border-t border-border bg-secondary/45 p-5">
                <p className="text-xs leading-5 text-muted-foreground">
                  The visitor sees their result before the contact step.
                </p>
                <Link to="/build" className="btn btn-primary mt-4 w-full">
                  Build mine
                  <ArrowRight className="size-4" aria-hidden="true" />
                </Link>
              </div>
            </article>

            <DecisionPreview key={open.id} architect={open.architect} />
          </div>
        </section>
      </main>

      <MarketingFooter />
    </>
  );
}
