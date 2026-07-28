import { Link } from "@tanstack/react-router";
import { ArrowRight, Check, MoveRight } from "lucide-react";
import { useMemo, useState } from "react";

function businessName(value: string) {
  const clean = value
    .trim()
    .replace(/^https?:\/\//i, "")
    .replace(/^www\./i, "");
  const first = clean.split(/[.\s-]/)[0];
  return first ? first.charAt(0).toUpperCase() + first.slice(1) : "Your business";
}

export function IntentSystem() {
  const [value, setValue] = useState("");
  const name = useMemo(() => businessName(value), [value]);
  const initial = name.charAt(0);

  return (
    <section className="border-b border-border bg-cream" id="features">
      <div className="mx-auto max-w-6xl px-6 py-20 lg:px-8 lg:py-28">
        <header className="grid items-end gap-10 lg:grid-cols-[1fr_0.72fr]">
          <div>
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              The source is already there
            </span>
            <h2 className="mt-5 max-w-[14ch] font-display text-[clamp(3rem,5.5vw,5.2rem)] font-normal leading-[0.92] tracking-[-0.05em]">
              Your website already contains the brief.
            </h2>
          </div>
          <p className="border-t border-foreground pt-5 text-base leading-7 text-muted-foreground">
            Magnitai looks for four things: what you sell, who it helps, how the brand behaves and
            what a visitor should understand next.
          </p>
        </header>

        <div className="mt-14 grid gap-4 lg:grid-cols-[1fr_3.5rem_1fr] lg:items-stretch">
          <article className="overflow-hidden rounded-[1.75rem] border border-border bg-card shadow-card">
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                Source page · Illustrative
              </span>
              <span className="flex gap-1.5" aria-hidden="true">
                <i className="size-2 rounded-full bg-n-300" />
                <i className="size-2 rounded-full bg-n-300" />
                <i className="size-2 rounded-full bg-n-300" />
              </span>
            </div>

            <div className="p-5 sm:p-7">
              <label htmlFor="cinema-company" className="text-sm font-semibold">
                Type any company name
              </label>
              <div className="mt-2 flex min-h-12 items-center gap-3 rounded-xl border border-input bg-background px-4 focus-within:ring-2 focus-within:ring-ring">
                <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-foreground text-xs font-semibold text-background">
                  {initial}
                </span>
                <input
                  id="cinema-company"
                  value={value}
                  onChange={(event) => setValue(event.target.value)}
                  placeholder="e.g. Northside Dental"
                  autoComplete="off"
                  aria-describedby="cinema-hint"
                  className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-n-400"
                />
              </div>
              <p id="cinema-hint" className="mt-2 text-xs leading-5 text-muted-foreground">
                This local specimen changes only the labels below. Nothing is sent anywhere.
              </p>

              <div className="mt-8 rounded-[1.4rem] bg-foreground p-5 text-background sm:p-6">
                <div className="flex items-center justify-between gap-4">
                  <span className="text-sm font-semibold">{name}</span>
                  <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-inverse-subtle">
                    Public website
                  </span>
                </div>
                <div className="mt-12 max-w-sm">
                  <span className="text-xs text-inverse-muted">
                    A clearer path for every visitor.
                  </span>
                  <h3 className="mt-2 text-3xl font-medium leading-[0.98] tracking-[-0.045em]">
                    Know what comes next before the first call.
                  </h3>
                  <span className="mt-7 inline-flex min-h-11 items-center rounded-full bg-brand px-5 text-sm font-semibold text-foreground">
                    Explore the service
                  </span>
                </div>
              </div>
            </div>
          </article>

          <div className="hidden items-center justify-center lg:flex" aria-hidden="true">
            <span className="grid size-11 place-items-center rounded-full border border-border bg-card shadow-raised">
              <MoveRight className="size-4" />
            </span>
          </div>

          <article className="overflow-hidden rounded-[1.75rem] border border-border bg-card shadow-card">
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                Magnitai brief · Example read
              </span>
              <span className="inline-flex items-center gap-2 text-xs font-medium text-success">
                <Check className="size-3.5" aria-hidden="true" />
                Ready to review
              </span>
            </div>

            <div className="p-5 sm:p-7">
              <dl className="divide-y divide-border border-y border-border">
                {[
                  ["Offer", `A guided service from ${name}`],
                  ["Audience", "A visitor who needs confidence before contact"],
                  ["Voice", "Direct, reassuring, low-pressure"],
                  ["Next decision", "Whether the service fits their situation"],
                ].map(([term, description]) => (
                  <div key={term} className="grid gap-2 py-4 sm:grid-cols-[7rem_1fr]">
                    <dt className="font-mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground">
                      {term}
                    </dt>
                    <dd className="text-sm leading-6 text-foreground">{description}</dd>
                  </div>
                ))}
              </dl>

              <div className="mt-7 rounded-[1.4rem] bg-brand p-5 text-foreground sm:p-6">
                <span className="font-mono text-[9px] uppercase tracking-[0.14em]">
                  Proposed useful question
                </span>
                <h3 className="mt-6 max-w-[14ch] text-3xl font-medium leading-[0.98] tracking-[-0.045em]">
                  What is the best next step for you?
                </h3>
                <p className="mt-3 max-w-sm text-sm leading-6 text-foreground/70">
                  A short assessment, followed by one clear recommendation.
                </p>
              </div>
            </div>
          </article>
        </div>

        <div className="mt-8 flex flex-col gap-4 border-t border-border pt-7 sm:flex-row sm:items-center sm:justify-between">
          <p className="max-w-xl text-sm leading-6 text-muted-foreground">
            The real builder reads a public website and lets you inspect its evidence before
            generation starts.
          </p>
          <Link to="/build" className="btn btn-primary shrink-0">
            Build this from my real website
            <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </div>
      </div>
    </section>
  );
}
