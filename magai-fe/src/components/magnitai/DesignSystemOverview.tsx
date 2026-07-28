import { ArrowRight, Check, CircleAlert, CircleCheck, Info } from "lucide-react";

import { MarketingFooter } from "./MarketingFooter";

const COLORS = [
  {
    name: "Paper",
    token: "--cream",
    role: "Public page ground and long-form reading",
  },
  {
    name: "Card",
    token: "--card",
    role: "Raised product surface",
  },
  {
    name: "Ink",
    token: "--ink",
    role: "Text, navigation and primary controls",
  },
  {
    name: "Lime",
    token: "--brand",
    role: "Forward action and generated-result surface",
  },
  {
    name: "Success",
    token: "--success",
    role: "Confirmed, connected and healthy",
  },
  {
    name: "Warning",
    token: "--warning",
    role: "Needs attention, but not failed",
  },
  {
    name: "Destructive",
    token: "--destructive",
    role: "Error or irreversible action",
  },
] as const;

const PRINCIPLES = [
  {
    number: "01",
    title: "Show the product",
    body: "A working control or real result is stronger evidence than a decorative feature card.",
  },
  {
    number: "02",
    title: "One next action",
    body: "Every page has one dominant forward action. Secondary actions stay visibly secondary.",
  },
  {
    number: "03",
    title: "Cards must earn their edge",
    body: "Use a card only for a selectable, movable or independently meaningful object.",
  },
  {
    number: "04",
    title: "Familiar where it matters",
    body: "Marketing may surprise. Pricing, forms, tables and navigation should behave as expected.",
  },
] as const;

export function DesignSystemOverview() {
  return (
    <>
      <div className="mx-auto max-w-6xl px-6 pb-24 pt-36 lg:px-8 lg:pb-32 lg:pt-44">
        <header className="grid items-end gap-12 border-b border-foreground pb-16 lg:grid-cols-[1.15fr_0.85fr]">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              Magnitai design system · v2
            </p>
            <h1 className="mt-5 max-w-[12ch] font-display text-[clamp(3.3rem,6.5vw,6.2rem)] font-normal leading-[0.9] tracking-[-0.055em]">
              Editorial utility. Personality without friction.
            </h1>
          </div>
          <p className="max-w-md text-base leading-7 text-muted-foreground">
            Marketing is expressive. Product screens are calm and conventional. Cream, ink and lime
            connect the two without making every screen look the same.
          </p>
        </header>

        <section className="py-20 lg:py-28">
          <div className="grid gap-10 lg:grid-cols-[0.65fr_1.35fr]">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                01 · Colour
              </p>
              <h2 className="mt-4 max-w-[10ch] text-3xl font-medium leading-[1.02] tracking-[-0.04em]">
                Three brand planes. Status stays semantic.
              </h2>
              <p className="mt-4 max-w-sm text-sm leading-6 text-muted-foreground">
                Blue can appear inside a customer widget preview. Hot red is reserved for the
                approved showcase wordmark and destructive states.
              </p>
            </div>

            <div className="overflow-hidden rounded-[1.5rem] border border-border bg-card">
              {COLORS.map((color) => (
                <div
                  key={color.token}
                  className="grid items-center gap-4 border-b border-border px-5 py-4 last:border-b-0 sm:grid-cols-[3.5rem_0.7fr_0.8fr_1.5fr]"
                >
                  <span
                    className="block size-11 rounded-xl border border-foreground/10 shadow-xs"
                    style={{ background: `var(${color.token})` }}
                    aria-hidden="true"
                  />
                  <strong className="text-sm">{color.name}</strong>
                  <code className="font-mono text-xs text-muted-foreground">{color.token}</code>
                  <span className="text-sm leading-6 text-muted-foreground">{color.role}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="border-y border-border bg-background py-20 lg:py-28">
          <div className="mx-auto grid max-w-6xl gap-12 px-0 lg:grid-cols-[0.8fr_1.2fr]">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                02 · Type
              </p>
              <p className="mt-5 max-w-[11ch] font-display text-[clamp(3rem,5vw,5rem)] leading-[0.92] tracking-[-0.05em]">
                Type should create pace before decoration does.
              </p>
              <p className="mt-6 max-w-md text-base leading-7 text-muted-foreground">
                Public-page headlines own the editorial serif. Geist carries supporting marketing
                and all product UI; Geist Mono handles indices, code and compact metadata.
              </p>
            </div>

            <div className="grid gap-px overflow-hidden rounded-[1.5rem] border border-border bg-border">
              <div className="bg-card p-6 sm:p-8">
                <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                  Display · Editorial serif
                </span>
                <p className="mt-8 text-5xl font-medium leading-[0.95] tracking-[-0.05em]">
                  A useful answer.
                </p>
                <p className="mt-8 text-sm leading-6 text-muted-foreground">
                  48–96px · 0.9–1.05 line height · −0.02 to −0.055em tracking
                </p>
              </div>
              <div className="bg-card p-6 sm:p-8">
                <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                  Body · Geist Variable
                </span>
                <p className="mt-8 max-w-[62ch] text-lg leading-8 text-muted-foreground">
                  Magnitai reads a website, finds the decision a visitor needs to make, and builds
                  the smallest useful interface for that decision.
                </p>
                <p className="mt-8 text-sm leading-6 text-muted-foreground">
                  16–18px · 1.55–1.7 line height · 65–75 character reading measure
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="py-20 lg:py-28">
          <div className="grid gap-12 lg:grid-cols-[0.65fr_1.35fr]">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                03 · Controls
              </p>
              <h2 className="mt-4 max-w-[11ch] text-3xl font-medium leading-[1.02] tracking-[-0.04em]">
                Clear hierarchy, generous targets.
              </h2>
              <p className="mt-4 max-w-sm text-sm leading-6 text-muted-foreground">
                Controls default to at least 44px tall. Lime is spent only on the action that moves
                the user forward.
              </p>
            </div>

            <div className="rounded-[1.5rem] border border-border bg-card p-6 sm:p-8">
              <div className="flex flex-wrap gap-3">
                <button type="button" className="btn btn-primary">
                  Primary action
                  <ArrowRight className="size-4" aria-hidden="true" />
                </button>
                <button type="button" className="btn btn-accent">
                  Forward action
                  <ArrowRight className="size-4" aria-hidden="true" />
                </button>
                <button type="button" className="btn btn-secondary">
                  Secondary
                </button>
                <button type="button" className="btn btn-ghost">
                  Quiet action
                </button>
              </div>

              <div className="mt-10 grid gap-3 sm:grid-cols-3">
                <div className="flex items-start gap-3 rounded-xl border border-border p-4">
                  <CircleCheck className="mt-0.5 size-4 shrink-0 text-success" />
                  <div>
                    <strong className="block text-sm">Published</strong>
                    <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                      State includes a word and an icon.
                    </span>
                  </div>
                </div>
                <div className="flex items-start gap-3 rounded-xl border border-border p-4">
                  <CircleAlert className="mt-0.5 size-4 shrink-0 text-warning" />
                  <div>
                    <strong className="block text-sm">Needs attention</strong>
                    <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                      Warning does not look like failure.
                    </span>
                  </div>
                </div>
                <div className="flex items-start gap-3 rounded-xl border border-border p-4">
                  <Info className="mt-0.5 size-4 shrink-0" />
                  <div>
                    <strong className="block text-sm">Helpful context</strong>
                    <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                      Guidance stays near the decision.
                    </span>
                  </div>
                </div>
              </div>

              <label className="mt-10 block max-w-md text-sm font-medium">
                Website address
                <input
                  className="mt-2 min-h-12 w-full rounded-xl border border-input bg-background px-4 text-sm outline-none transition-shadow placeholder:text-n-400 focus-visible:ring-2 focus-visible:ring-ring"
                  placeholder="https://yourbusiness.com"
                />
                <span className="mt-2 block text-xs font-normal leading-5 text-muted-foreground">
                  We read public pages only. You can review the brand signals before building.
                </span>
              </label>
            </div>
          </div>
        </section>

        <section className="editorial-grid-dark relative -mx-6 overflow-hidden bg-inverse px-6 py-20 text-inverse-foreground lg:-mx-8 lg:px-8 lg:py-24">
          <div className="relative mx-auto max-w-6xl">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-brand-on-inverse">
              04 · Composition
            </p>
            <div className="mt-8 grid border-t border-inverse-border lg:grid-cols-2">
              {PRINCIPLES.map((principle) => (
                <article
                  key={principle.number}
                  className="grid grid-cols-[2.5rem_1fr] gap-4 border-b border-inverse-border py-7 lg:odd:border-r lg:odd:pr-8 lg:even:pl-8"
                >
                  <span className="font-mono text-xs text-inverse-subtle">{principle.number}</span>
                  <div>
                    <h3 className="text-xl font-medium tracking-[-0.03em]">{principle.title}</h3>
                    <p className="mt-2 max-w-md text-sm leading-6 text-inverse-muted">
                      {principle.body}
                    </p>
                  </div>
                </article>
              ))}
            </div>

            <div className="mt-10 flex items-center gap-3 text-sm text-inverse-muted">
              <span className="grid size-6 place-items-center rounded-full bg-brand text-foreground">
                <Check className="size-3.5" aria-hidden="true" />
              </span>
              Inspect at 320, 768, 1280 and 1440 pixels before a screen is finished.
            </div>
          </div>
        </section>
      </div>

      <MarketingFooter />
    </>
  );
}
