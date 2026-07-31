import { Link } from "@tanstack/react-router";
import {
  ArrowRight,
  ChartNoAxesCombined,
  Code2,
  Download,
  Eye,
  Globe2,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";

import { MarketingFooter } from "./MarketingFooter";

const JOURNEY = [
  {
    icon: Globe2,
    title: "Start with the page that already sells your offer",
    detail:
      "Paste a service, product or landing page. Magnitai reads the offer, audience, brand and decision a serious visitor is trying to make.",
    action: "You provide one public website page.",
    result: "You get a clear conversion brief, not a blank template.",
  },
  {
    icon: Eye,
    title: "Compare two complete lead magnets",
    detail:
      "Magnitai recommends the calculator, quiz or audit that best fits that decision, then makes both options playable.",
    action: "You try the visitor experience before signing up.",
    result: "You choose from working outcomes, not descriptions.",
  },
  {
    icon: Code2,
    title: "Review it, then publish with one embed",
    detail:
      "Edit the questions, result and next action if needed. When it is right, copy one embed into the page you started with.",
    action: "You approve the final value exchange.",
    result: "Your site stays intact and the lead magnet goes live inside it.",
  },
  {
    icon: ChartNoAxesCombined,
    title: "See what visitors need and where they stop",
    detail:
      "The workspace turns views, starts, results, leads and final actions into one business outcome and one recommended next step.",
    action: "You return to leads and a clear action—not a wall of charts.",
    result: "Every response improves follow-up and the next version.",
  },
] as const;

const TRUST = [
  {
    icon: ShieldCheck,
    title: "Your website stays yours",
    detail:
      "Magnitai runs inside a contained embed. Publishing does not replace or rewrite your site.",
  },
  {
    icon: Download,
    title: "Your leads stay portable",
    detail: "Review the answers that qualified each lead and export them whenever you need them.",
  },
  {
    icon: RefreshCw,
    title: "The live tool stays watched",
    detail:
      "Magnitai checks deployment health and brand drift while keeping the same embed address.",
  },
] as const;

export function TransparencyDashboard() {
  return (
    <>
      <main>
        <section className="mx-auto max-w-6xl px-6 pb-16 pt-36 lg:px-8 lg:pb-24 lg:pt-44">
          <div className="grid items-end gap-10 lg:grid-cols-[1.1fr_0.9fr]">
            <div>
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                How Magnitai works
              </span>
              <h1 className="mt-5 max-w-[12ch] text-balance font-display text-[clamp(3.2rem,6.3vw,6rem)] font-normal leading-[0.9] tracking-[-0.055em]">
                From website page to working lead magnet.
              </h1>
            </div>
            <div className="border-t border-foreground pt-5 lg:mb-2">
              <p className="max-w-md text-base leading-7 text-muted-foreground">
                Start with what visitors already see. Leave with a useful result for them, qualified
                context for your business and one embed for your site.
              </p>
              <Link to="/build" className="btn btn-primary mt-7">
                Build from my website
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </div>
          </div>
        </section>

        <section className="editorial-grid-dark bg-inverse text-inverse-foreground">
          <div className="mx-auto max-w-6xl px-6 py-16 lg:px-8 lg:py-24">
            <div className="flex flex-col gap-4 border-b border-inverse-border pb-7 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <span className="font-mono text-[10px] uppercase tracking-[0.17em] text-brand-on-inverse">
                  One clear journey
                </span>
                <h2 className="mt-3 text-3xl font-medium tracking-[-0.04em]">
                  Four steps. A working outcome at each one.
                </h2>
              </div>
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-inverse-subtle">
                Nothing publishes without approval
              </span>
            </div>

            <ol className="divide-y divide-inverse-border">
              {JOURNEY.map((step, index) => {
                const Icon = step.icon;
                return (
                  <li
                    key={step.title}
                    className="grid gap-6 py-8 md:grid-cols-[3rem_minmax(0,0.8fr)_minmax(0,1.2fr)] md:items-start"
                  >
                    <span className="font-mono text-sm text-inverse-subtle">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <div>
                      <span className="grid size-10 place-items-center rounded-full border border-inverse-border bg-inverse-raised text-brand-on-inverse">
                        <Icon className="size-4" aria-hidden="true" />
                      </span>
                      <h3 className="mt-4 max-w-sm text-xl font-medium tracking-[-0.03em]">
                        {step.title}
                      </h3>
                      <p className="mt-3 max-w-md text-sm leading-6 text-inverse-muted">
                        {step.detail}
                      </p>
                    </div>
                    <dl className="grid overflow-hidden rounded-2xl border border-inverse-border sm:grid-cols-2">
                      <div className="p-5">
                        <dt className="font-mono text-[9px] uppercase tracking-[0.14em] text-inverse-subtle">
                          Your part
                        </dt>
                        <dd className="mt-2 text-sm leading-6 text-inverse-muted">{step.action}</dd>
                      </div>
                      <div className="border-t border-inverse-border bg-inverse-raised p-5 sm:border-l sm:border-t-0">
                        <dt className="font-mono text-[9px] uppercase tracking-[0.14em] text-brand-on-inverse">
                          What you get
                        </dt>
                        <dd className="mt-2 text-sm leading-6 text-inverse-foreground">
                          {step.result}
                        </dd>
                      </div>
                    </dl>
                  </li>
                );
              })}
            </ol>
          </div>
        </section>

        <section className="bg-cream">
          <div className="mx-auto max-w-6xl px-6 py-20 lg:px-8 lg:py-28">
            <div className="max-w-2xl">
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Built for business trust
              </span>
              <h2 className="mt-5 font-display text-[clamp(2.7rem,5vw,4.6rem)] font-normal leading-[0.92] tracking-[-0.05em]">
                Easy to start. Safe to rely on.
              </h2>
            </div>

            <div className="mt-10 grid gap-px overflow-hidden rounded-[1.75rem] border border-border bg-border md:grid-cols-3">
              {TRUST.map((item) => {
                const Icon = item.icon;
                return (
                  <article key={item.title} className="bg-card p-6 sm:p-7">
                    <Icon className="size-5 text-brand-solid" aria-hidden="true" />
                    <h3 className="mt-7 text-lg font-medium tracking-[-0.025em]">{item.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.detail}</p>
                  </article>
                );
              })}
            </div>
          </div>
        </section>
      </main>

      <MarketingFooter />
    </>
  );
}
