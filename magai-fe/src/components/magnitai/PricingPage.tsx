import { Link } from "@tanstack/react-router";
import { AlertCircle, ArrowRight, Check, Loader2, Minus, RefreshCw } from "lucide-react";

import { usePlans, type PlanData } from "@/lib/api";
import { formatPrice } from "@/lib/plan";
import { MarketingFooter } from "./MarketingFooter";

/**
 * Every number and bullet on this page comes from `/api/billing/plans`.
 *
 * It used to be a hardcoded array, and it had already drifted from what the
 * server enforces — the table promised "unlimited captured leads" against a real
 * per-tool cap. A pricing page that contradicts the product is worse than one
 * that is merely out of date, because a customer only discovers it after paying.
 */

/** Presentation per tier. Only the recommended plan receives brand emphasis. */
const CARD_STYLE: Record<string, { emphasis: "plain" | "brand"; cta: string }> = {
  free: { emphasis: "plain", cta: "See my directions" },
  studio: { emphasis: "brand", cta: "Start with Studio" },
  scale: { emphasis: "plain", cta: "Start with Scale" },
};

/**
 * The comparison rows, each reading a real field off the plan.
 *
 * A row is a function of the plan rather than a literal, so a limit can only
 * ever say what the server would enforce.
 */
const ROWS: Array<{
  label: string;
  note?: string;
  value: (plan: PlanData) => string | boolean;
}> = [
  {
    label: "Live tools",
    value: (plan) => (plan.live_tool_limit === 0 ? "Preview only" : `${plan.live_tool_limit}`),
  },
  {
    label: "Builds each month",
    note: "One build is a full generation: reading the site, designing the tool, and deploying it.",
    value: (plan) => `${plan.monthly_build_limit}`,
  },
  {
    label: "Leads per tool",
    value: (plan) =>
      plan.lead_limit_per_tool === 0 ? false : plan.lead_limit_per_tool.toLocaleString(),
  },
  {
    label: "Analytics history",
    value: (plan) => `${plan.analytics_window_days} days`,
  },
  {
    label: "Automatic brand repair",
    note: "Re-reads your site and rebuilds when your colours or type change.",
    value: (plan) => plan.features.includes("self_healing"),
  },
  {
    label: "Export and webhook delivery",
    value: (plan) => plan.features.includes("webhook_delivery"),
  },
  {
    label: "CRM and marketing integrations",
    value: (plan) => plan.features.includes("crm_integrations"),
  },
  {
    label: "Edit questions and results",
    value: (plan) => plan.features.includes("question_editor"),
  },
  {
    label: "Priority support",
    value: (plan) => plan.features.includes("priority_support"),
  },
];

/** The capacity line on a card, in the plan's own numbers. */
function capacityLine(plan: PlanData): { headline: string; detail: string } {
  if (plan.live_tool_limit === 0) {
    return { headline: "Preview only", detail: "Nothing publishes yet" };
  }
  return {
    headline: `${plan.live_tool_limit} live ${plan.live_tool_limit === 1 ? "tool" : "tools"}`,
    detail: `${plan.lead_limit_per_tool.toLocaleString()} leads per tool`,
  };
}

/** The objections a pricing page has to answer before anyone will read the table. */
const FAQ = [
  {
    question: "Can I see what Magnitai would build before I pay?",
    answer:
      "Yes. Magnitai reads your public website and presents two grounded directions without an account or a card. Payment starts only when you choose a direction to publish.",
  },
  {
    question: "What happens when I cancel?",
    answer:
      "Your plan stays active through the end of the billing period. You can export captured leads and tool data before hosted tools are taken offline.",
  },
  {
    question: "Do I own the leads and responses?",
    answer:
      "Yes. They belong to your business. Download them from the workspace, or send them straight to your CRM on a paid plan.",
  },
  {
    question: "Is hosting included?",
    answer:
      "Yes. Every published tool is hosted at its own stable address and embedded on your site with one snippet.",
  },
  {
    question: "What does automatic brand repair change?",
    answer:
      "Magnitai watches the website the tool was built from. If its core colours or type change, the tool is rebuilt against the new brand and the event is recorded on its timeline.",
  },
  {
    question: "Can I move between plans?",
    answer:
      "Yes, from workspace settings. Existing tools and captured data stay exactly where they are.",
  },
] as const;

function Cell({ value }: { value: string | boolean }) {
  if (typeof value === "string") {
    return <span className="text-sm text-foreground">{value}</span>;
  }
  return value ? (
    <span className="inline-flex size-6 items-center justify-center rounded-full bg-brand text-foreground">
      <Check className="size-3.5" aria-label="Included" />
    </span>
  ) : (
    <Minus className="size-4 text-n-400" aria-label="Not included" />
  );
}

export function PricingPage() {
  const { data, isLoading, isError, isFetching, refetch } = usePlans();
  const plans = data?.plans ?? [];

  if (isLoading) {
    return (
      <div
        className="mx-auto flex min-h-[60vh] max-w-6xl items-center px-6 pt-28 lg:px-8"
        role="status"
      >
        <div className="w-full border-y border-border py-12">
          <Loader2 className="size-5 animate-spin text-muted-foreground" aria-hidden="true" />
          <p className="mt-5 text-sm font-medium text-foreground">Loading current plans</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Prices and limits are being checked against billing.
          </p>
        </div>
      </div>
    );
  }

  if (isError || plans.length === 0) {
    return (
      <>
        <section className="mx-auto grid min-h-[72vh] max-w-6xl items-center gap-12 px-6 pb-20 pt-36 lg:grid-cols-[1.05fr_0.95fr] lg:px-8 lg:pt-44">
          <div>
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              Pricing · Live catalogue unavailable
            </span>
            <h1 className="mt-5 max-w-[13ch] font-display text-[clamp(3.2rem,6.3vw,5.8rem)] font-normal leading-[0.9] tracking-[-0.055em]">
              We cannot verify the plans right now.
            </h1>
          </div>

          <div className="rounded-[1.75rem] border border-border bg-card p-6 shadow-card sm:p-8">
            <span className="grid size-11 place-items-center rounded-full bg-warning/15 text-warning">
              <AlertCircle className="size-5" aria-hidden="true" />
            </span>
            <h2 className="mt-6 text-xl font-medium tracking-[-0.025em]">
              Nothing has been guessed
            </h2>
            <p className="mt-3 max-w-md text-sm leading-6 text-muted-foreground">
              Magnitai could not reach the billing catalogue, so this page is not showing cached or
              made-up prices. You can retry, or preview what we would build for free.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => void refetch()}
                disabled={isFetching}
              >
                <RefreshCw
                  className={`size-4 ${isFetching ? "animate-spin" : ""}`}
                  aria-hidden="true"
                />
                {isFetching ? "Checking…" : "Check again"}
              </button>
              <Link to="/build" className="btn btn-primary">
                Preview for free
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </div>
          </div>
        </section>

        <MarketingFooter />
      </>
    );
  }

  return (
    <>
      <div>
        <section className="mx-auto max-w-6xl px-6 pb-16 pt-36 lg:px-8 lg:pb-24 lg:pt-44">
          <div className="grid items-end gap-12 lg:grid-cols-[1.15fr_0.85fr]">
            <div>
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Pricing · No account to preview
              </span>
              <h1 className="mt-5 max-w-[14ch] text-balance font-display text-[clamp(3.2rem,6.3vw,6rem)] font-normal leading-[0.9] tracking-[-0.055em]">
                Look for free. Pay when it goes live.
              </h1>
            </div>
            <div className="border-t border-foreground pt-5 lg:mb-2">
              <p className="max-w-md text-base leading-7 text-muted-foreground">
                Reading your website and proposing directions costs nothing. You pay when a tool is
                ready to live on your site and collect real leads.
              </p>
              <div className="mt-7 grid grid-cols-2 gap-5 text-sm">
                <div>
                  <strong className="block text-foreground">Monthly</strong>
                  <span className="mt-1 block text-muted-foreground">Cancel any time</span>
                </div>
                <div>
                  <strong className="block text-foreground">No setup fee</strong>
                  <span className="mt-1 block text-muted-foreground">Hosting included</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="border-y border-border bg-background">
          <div className="mx-auto grid max-w-6xl gap-4 px-6 py-8 lg:grid-cols-3 lg:px-8">
            {plans.map((plan, index) => {
              const style = CARD_STYLE[plan.id] ?? CARD_STYLE.free;
              const brand = style.emphasis === "brand";
              const capacity = capacityLine(plan);

              return (
                <article
                  key={plan.id}
                  className={`flex min-h-[32rem] flex-col rounded-[1.75rem] border p-6 sm:p-7 ${
                    brand
                      ? "border-foreground/25 bg-brand shadow-float"
                      : "border-border bg-card shadow-card"
                  }`}
                >
                  <div className="flex h-full flex-col">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                        0{index + 1} / 0{plans.length}
                      </span>
                      {brand ? (
                        <span className="rounded-full bg-foreground px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-background">
                          Most popular
                        </span>
                      ) : null}
                    </div>

                    <h2 className="mt-8 text-2xl font-medium tracking-[-0.035em]">{plan.name}</h2>
                    <div className="mt-3 flex items-baseline gap-2">
                      <strong className="font-display text-6xl font-normal tracking-[-0.055em]">
                        {formatPrice(plan.monthly_price, plan.currency)}
                      </strong>
                      <span className="text-sm text-muted-foreground">
                        {plan.monthly_price === 0 ? "to look" : "per month"}
                      </span>
                    </div>

                    <p className="mt-5 min-h-[4.5rem] text-sm leading-6 text-foreground/70">
                      {plan.tagline}
                    </p>

                    <div className="mt-7 border-y border-foreground/15 py-5">
                      <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground">
                        Capacity
                      </span>
                      <strong className="mt-2 block text-lg font-medium">
                        {capacity.headline}
                      </strong>
                      <span className="mt-1 block text-xs text-muted-foreground">
                        {capacity.detail}
                      </span>
                    </div>

                    <ul className="mt-5 space-y-2">
                      {plan.highlights.map((highlight) => (
                        <li
                          key={highlight}
                          className="flex items-start gap-2 text-sm leading-6 text-foreground/75"
                        >
                          <Check
                            className="mt-1 size-3.5 shrink-0 text-foreground"
                            aria-hidden="true"
                          />
                          {highlight}
                        </li>
                      ))}
                    </ul>

                    <Link
                      to="/build"
                      className={`group mt-auto flex h-12 items-center justify-between rounded-full px-4 text-sm font-semibold ${
                        brand
                          ? "bg-foreground text-background"
                          : "border border-border-strong bg-card text-foreground"
                      }`}
                    >
                      {style.cta}
                      <span className="grid size-8 place-items-center rounded-full bg-inverse text-inverse-foreground">
                        <ArrowRight
                          className="size-3.5 transition-transform group-hover:translate-x-0.5"
                          aria-hidden="true"
                        />
                      </span>
                    </Link>
                  </div>
                </article>
              );
            })}
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-6 py-20 lg:px-8 lg:py-28">
          <div className="grid gap-10 lg:grid-cols-[0.7fr_1.3fr]">
            <div>
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Compare plans
              </span>
              <h2 className="mt-4 max-w-[11ch] text-3xl font-medium leading-[1.02] tracking-[-0.04em]">
                The differences, without the marketing fog.
              </h2>
            </div>

            <div className="surface overflow-x-auto">
              <table className="w-full min-w-[38rem] border-collapse text-left">
                <thead>
                  <tr>
                    <th scope="col" className="w-[42%] px-5 py-4" />
                    {plans.map((plan) => (
                      <th
                        key={plan.id}
                        scope="col"
                        className="px-4 py-4 text-sm font-medium text-foreground"
                      >
                        {plan.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {ROWS.map((row) => (
                    <tr key={row.label} className="border-t border-border">
                      <th scope="row" className="px-5 py-4 align-top font-normal">
                        <span className="block text-sm text-foreground">{row.label}</span>
                        {row.note ? (
                          <span className="mt-1 block max-w-sm text-xs leading-5 text-muted-foreground">
                            {row.note}
                          </span>
                        ) : null}
                      </th>
                      {plans.map((plan) => (
                        <td key={plan.id} className="px-4 py-4 align-top">
                          <Cell value={row.value(plan)} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section className="editorial-grid-dark relative overflow-hidden bg-inverse text-inverse-foreground">
          <div className="relative mx-auto max-w-6xl px-6 py-20 lg:px-8 lg:py-24">
            <div className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr] lg:items-end">
              <div>
                <span className="font-mono text-[10px] uppercase tracking-[0.17em] text-brand-on-inverse">
                  What the subscription pays for
                </span>
                <h2 className="mt-5 max-w-[13ch] font-display text-[clamp(2.7rem,5vw,4.7rem)] font-normal leading-[0.94] tracking-[-0.05em]">
                  Generation is the start. Staying useful is the service.
                </h2>
              </div>

              <div className="grid gap-px overflow-hidden rounded-[1.5rem] border border-inverse-border bg-inverse-border sm:grid-cols-3">
                {[
                  {
                    title: "Watch",
                    body: "We re-read your website and check the live address every few hours.",
                  },
                  {
                    title: "Repair",
                    body: "Brand drift triggers a rebuild. A failed address triggers a republish.",
                  },
                  {
                    title: "Record",
                    body: "Every meaningful check becomes a plain-language timeline entry.",
                  },
                ].map((item, index) => (
                  <article key={item.title} className="bg-inverse-raised p-5">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[10px] text-inverse-subtle">
                        0{index + 1}
                      </span>
                      {index === 1 ? (
                        <RefreshCw className="size-4 text-brand-on-inverse" aria-hidden="true" />
                      ) : null}
                    </div>
                    <h3 className="mt-10 text-lg font-medium">{item.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-inverse-muted">{item.body}</p>
                  </article>
                ))}
              </div>
            </div>

            <p className="mt-10 border-t border-inverse-border pt-6 text-xs leading-5 text-inverse-subtle">
              Tools run inside a sandboxed iframe. Magnitai repairs the tool’s own brand and
              deployment health; it does not rewrite the layout of your host page.
            </p>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-6 py-20 lg:px-8 lg:py-28">
          <div className="grid gap-12 lg:grid-cols-[0.65fr_1.35fr]">
            <div>
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Before you choose
              </span>
              <h2 className="mt-4 max-w-[11ch] text-3xl font-medium leading-[1.02] tracking-[-0.04em]">
                The questions a pricing page should answer.
              </h2>
            </div>

            <dl className="border-t border-foreground">
              {FAQ.map((item) => (
                <div
                  key={item.question}
                  className="grid gap-3 border-b border-border py-6 sm:grid-cols-[0.8fr_1.2fr] sm:gap-8"
                >
                  <dt className="text-sm font-semibold leading-6 text-foreground">
                    {item.question}
                  </dt>
                  <dd className="text-sm leading-6 text-muted-foreground">{item.answer}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>
      </div>

      <MarketingFooter />
    </>
  );
}
