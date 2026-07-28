import { Link } from "@tanstack/react-router";
import {
  ArrowRight,
  Check,
  Code2,
  Globe,
  Layers,
  Palette,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";

import { MarketingFooter } from "./MarketingFooter";

const STAGES = [
  {
    icon: Globe,
    name: "Read",
    tag: "Business and intent",
    does: "Fetches your page and works out what the business sells, who it sells to, and what a visitor should do next.",
    gives: "A plain-language model of your offer, audience and conversion goal.",
  },
  {
    icon: Palette,
    name: "Design",
    tag: "Brand system",
    does: "Pulls the palette, typefaces and voice from the page, then shapes the tool around the decision your buyer needs to make.",
    gives: "Design tokens, interface structure and first-pass copy.",
  },
  {
    icon: Layers,
    name: "Skin",
    tag: "Visual language",
    does: "Turns those tokens into real styles and loads the matching webfonts. The generated interface is constrained to your brand.",
    gives: "A complete visual system the widget can actually render.",
  },
  {
    icon: Code2,
    name: "Build",
    tag: "Code and validation",
    does: "Writes the component, compiles it, and proves that the lead-capture path is connected before anything can publish.",
    gives: "A working, tested widget rather than a static mock-up.",
  },
  {
    icon: ShieldCheck,
    name: "Publish",
    tag: "Edge deployment",
    does: "Builds static files and publishes them at one stable address, then keeps checking the brand and the deployment.",
    gives: "A live URL, one embed line and an ongoing repair timeline.",
  },
] as const;

export function TransparencyDashboard() {
  return (
    <>
      <div>
        <section className="mx-auto max-w-6xl px-6 pb-16 pt-36 lg:px-8 lg:pb-24 lg:pt-44">
          <div className="grid items-end gap-12 lg:grid-cols-[1.15fr_0.85fr]">
            <div>
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                How it works · No black box
              </span>
              <h1 className="mt-5 max-w-[13ch] text-balance font-display text-[clamp(3.2rem,6.3vw,6rem)] font-normal leading-[0.9] tracking-[-0.055em]">
                Built in five steps. Kept useful after that.
              </h1>
            </div>
            <div className="border-t border-foreground pt-5 lg:mb-2">
              <p className="max-w-md text-base leading-7 text-muted-foreground">
                Every stage maps to a real part of the pipeline. You can see what Magnitai read,
                what it built, when it published, and every repair it makes later.
              </p>
              <div className="mt-7 flex flex-wrap items-center gap-x-6 gap-y-3 text-sm">
                <span className="inline-flex items-center gap-2 text-foreground">
                  <span className="size-2 rounded-full bg-success" />
                  Real build output
                </span>
                <span className="inline-flex items-center gap-2 text-foreground">
                  <span className="size-2 rounded-full bg-brand-solid" />
                  Stable embed URL
                </span>
              </div>
            </div>
          </div>
        </section>

        <section className="editorial-grid-dark relative overflow-hidden bg-inverse text-inverse-foreground">
          <div className="relative mx-auto max-w-6xl px-6 py-8 lg:px-8 lg:py-12">
            <div className="flex flex-col gap-4 border-b border-inverse-border pb-7 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <span className="font-mono text-[10px] uppercase tracking-[0.17em] text-brand-on-inverse">
                  The build pipeline
                </span>
                <h2 className="mt-3 text-3xl font-medium tracking-[-0.04em]">
                  Website in. Working interface out.
                </h2>
              </div>
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-inverse-subtle">
                05 deterministic stages
              </span>
            </div>

            <ol className="divide-y divide-inverse-border">
              {STAGES.map((stage, index) => {
                const Icon = stage.icon;
                return (
                  <li
                    key={stage.name}
                    className="group grid gap-5 py-7 transition-colors hover:bg-white/[0.025] sm:grid-cols-[3rem_minmax(8rem,0.55fr)_minmax(0,1.45fr)] sm:px-3 lg:items-start"
                  >
                    <span className="tabular font-mono text-sm text-inverse-subtle">
                      {String(index + 1).padStart(2, "0")}
                    </span>

                    <div>
                      <span className="grid size-10 place-items-center rounded-full border border-inverse-border bg-inverse-raised text-brand-on-inverse">
                        <Icon className="size-4" aria-hidden="true" />
                      </span>
                      <h3 className="mt-4 text-2xl font-medium tracking-[-0.035em]">
                        {stage.name}
                      </h3>
                      <p className="mt-1 text-xs text-inverse-subtle">{stage.tag}</p>
                    </div>

                    <div className="grid gap-5 lg:grid-cols-2">
                      <div>
                        <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-inverse-subtle">
                          What happens
                        </span>
                        <p className="mt-2 text-sm leading-6 text-inverse-muted">{stage.does}</p>
                      </div>
                      <div className="rounded-2xl border border-inverse-border bg-inverse-raised p-4">
                        <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-brand-on-inverse">
                          You get
                        </span>
                        <p className="mt-2 text-sm leading-6 text-inverse-foreground">
                          {stage.gives}
                        </p>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ol>
          </div>
        </section>

        <section className="bg-cream">
          <div className="mx-auto max-w-6xl px-6 py-20 lg:px-8 lg:py-28">
            <div className="grid gap-12 lg:grid-cols-[0.75fr_1.25fr] lg:items-start">
              <div className="lg:sticky lg:top-28">
                <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                  After launch
                </span>
                <h2 className="mt-5 max-w-[12ch] font-display text-[clamp(2.8rem,5vw,4.8rem)] font-normal leading-[0.92] tracking-[-0.05em]">
                  The interface keeps paying attention.
                </h2>
                <p className="mt-6 max-w-md text-base leading-7 text-muted-foreground">
                  Magnitai re-reads the source site and checks the live deployment every few hours.
                  If either drifts, the safe repair path runs automatically.
                </p>
                <Link to="/pricing" className="btn btn-secondary mt-8">
                  See plans
                  <ArrowRight className="size-4" aria-hidden="true" />
                </Link>
              </div>

              <div className="grid gap-4">
                <article className="overflow-hidden rounded-[1.75rem] border border-border bg-card shadow-card">
                  <div className="flex items-center justify-between gap-4 border-b border-border px-5 py-4">
                    <span className="inline-flex items-center gap-2 text-sm font-medium">
                      <RefreshCw className="size-4" aria-hidden="true" />
                      Example repair event
                    </span>
                    <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-warning">
                      Brand drift
                    </span>
                  </div>

                  <div className="grid gap-px bg-border sm:grid-cols-2">
                    <div className="bg-n-50 p-6">
                      <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground">
                        Before
                      </span>
                      <div className="mt-5 flex items-center gap-3">
                        <span className="size-11 rounded-full bg-oasis shadow-raised" />
                        <span className="size-11 rounded-full bg-n-300 shadow-raised" />
                        <span className="size-11 rounded-full bg-card shadow-raised" />
                      </div>
                      <p className="mt-8 text-sm leading-6 text-muted-foreground">
                        The website changed its primary colour and heading face. The published tool
                        no longer matched.
                      </p>
                    </div>
                    <div className="bg-brand p-6 text-foreground">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[9px] uppercase tracking-[0.15em]">
                          Healed
                        </span>
                        <span className="grid size-7 place-items-center rounded-full bg-foreground text-background">
                          <Check className="size-3.5" aria-hidden="true" />
                        </span>
                      </div>
                      <div className="mt-5 flex items-center gap-3">
                        <span className="size-11 rounded-full bg-foreground shadow-raised" />
                        <span className="size-11 rounded-full bg-oasis shadow-raised" />
                        <span className="size-11 rounded-full bg-card shadow-raised" />
                      </div>
                      <p className="mt-8 text-sm leading-6 text-foreground/70">
                        Tokens refreshed, widget rebuilt, same embed address. No edit needed on the
                        customer’s page.
                      </p>
                    </div>
                  </div>
                </article>

                <article className="rounded-[1.75rem] border border-border bg-card p-6 shadow-card sm:p-7">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground">
                        Illustrative health timeline
                      </span>
                      <h3 className="mt-2 text-xl font-medium tracking-[-0.025em]">
                        How recovery appears
                      </h3>
                    </div>
                    <span className="inline-flex w-fit items-center gap-2 rounded-full bg-brand-wash px-3 py-1.5 text-xs font-medium text-foreground">
                      <span className="size-2 rounded-full bg-success" />
                      Healthy now
                    </span>
                  </div>

                  <div
                    className="mt-7 grid grid-cols-12 gap-1.5"
                    aria-label="Example sequence of healthy checks and one automatic recovery"
                  >
                    {Array.from({ length: 12 }, (_, index) => (
                      <span
                        key={index}
                        className={`h-10 rounded-md ${index === 7 ? "bg-warning/25" : "bg-brand"}`}
                        title={index === 7 ? "Recovered automatically" : "Healthy check"}
                      />
                    ))}
                  </div>
                  <div className="mt-4 flex items-center justify-between gap-4 text-xs text-muted-foreground">
                    <span>Example sequence</span>
                    <span>Automatic republish · same embed address</span>
                  </div>
                </article>
              </div>
            </div>
          </div>
        </section>
      </div>

      <MarketingFooter />
    </>
  );
}
