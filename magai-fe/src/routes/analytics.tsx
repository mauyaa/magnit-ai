import { createFileRoute, Link } from "@tanstack/react-router";
import { Loader2 } from "lucide-react";
import { useState, type ReactNode } from "react";

import { RequireAuth } from "@/components/magnitai/RequireAuth";
import { ActivityChart } from "@/components/magnitai/shell/ActivityChart";
import { PageHeader } from "@/components/magnitai/shell/PageHeader";
import { percentChange, StatCard, StatRow } from "@/components/magnitai/shell/StatCard";
import { WorkspaceShell } from "@/components/magnitai/shell/WorkspaceShell";
import { usePortfolioAnalytics, type PortfolioAnalytics } from "@/lib/api";

export const Route = createFileRoute("/analytics")({
  head: () => ({ meta: [{ title: "Analytics · Magnitai" }] }),
  component: () => (
    <RequireAuth>
      <AnalyticsPage />
    </RequireAuth>
  ),
});

/**
 * The API accepts 7–90 days. Asking for double the selected window in one
 * request gives the previous period to compare against for free; at 90 there is
 * no room left under the cap, so that range honestly shows no deltas rather
 * than inventing a shorter comparison and calling it the same thing.
 */
const RANGES = [
  { days: 7, label: "7 days" },
  { days: 30, label: "30 days" },
  { days: 90, label: "90 days" },
] as const;

function rate(value: number | null | undefined) {
  return value == null ? "—" : `${value.toFixed(1)}%`;
}

function RangePicker({ value, onChange }: { value: number; onChange: (days: number) => void }) {
  return (
    <div
      role="group"
      aria-label="Date range"
      className="inline-flex rounded-lg border border-border bg-card p-0.5 shadow-raised"
    >
      {RANGES.map((range) => (
        <button
          key={range.days}
          type="button"
          onClick={() => onChange(range.days)}
          aria-pressed={value === range.days}
          className={`h-8 rounded-[6px] px-3 text-sm transition-colors ${
            value === range.days
              ? "bg-secondary font-medium text-foreground"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          {range.label}
        </button>
      ))}
    </div>
  );
}

/**
 * The funnel is all-time, and says so.
 *
 * Its first stage — how many people *saw* a tool — is only recorded as a
 * lifetime counter on the widget; there is no per-day impression row to slice.
 * Mixing that lifetime number with period-scoped starts is how this panel came
 * to report "1% of the step before": 915 all-time views against 8 starts in the
 * last 30 days. Two scopes in one funnel is always a wrong number, so the whole
 * panel stays on one scope and the period view is carried by the cards above.
 */
function Funnel({ data }: { data: PortfolioAnalytics }) {
  const stages = [
    { label: "Saw the tool", value: data.totals.visitors ?? 0 },
    { label: "Started it", value: data.totals.starts ?? 0 },
    { label: "Finished it", value: data.totals.completions ?? 0 },
    { label: "Left their details", value: data.totals.leads ?? 0 },
  ];
  const top = Math.max(...stages.map((stage) => stage.value), 1);

  return (
    <article className="surface flex flex-col p-5">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-base font-medium text-foreground">Visitor journey</h2>
        <span className="text-xs text-muted-foreground">All time</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">Where interest becomes intent</p>

      <div className="mt-6 space-y-4">
        {stages.map((stage, index) => {
          const previous = index === 0 ? null : stages[index - 1].value;
          const kept = previous && previous > 0 ? (stage.value / previous) * 100 : null;
          return (
            <div key={stage.label}>
              <div className="mb-1.5 flex items-end justify-between gap-3">
                <span className="text-xs text-muted-foreground">{stage.label}</span>
                <span className="tabular text-sm font-medium text-foreground">
                  {stage.value.toLocaleString()}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-n-100">
                <span
                  className={`block h-full rounded-full ${
                    index === stages.length - 1 ? "bg-chart-lead" : "bg-chart-rest"
                  }`}
                  style={{
                    width: `${Math.max(stage.value > 0 ? 2 : 0, (stage.value / top) * 100)}%`,
                  }}
                />
              </div>
              {/*
               * Step-to-step retention: the number that says *which* step leaks,
               * which totals alone never do. Suppressed above 100% — a lead can
               * be submitted on a visit that was never flagged complete, so the
               * last stage can legitimately exceed the one before it, and
               * "120% of the step before" reads as a bug rather than as that.
               */}
              {kept !== null && kept <= 100 && (
                <p className="mt-1 text-xs text-muted-foreground">
                  {kept.toFixed(0)}% of the step before
                </p>
              )}
            </div>
          );
        })}
      </div>
    </article>
  );
}

function AnalyticsPage() {
  const [days, setDays] = useState<number>(30);
  const requested = Math.min(90, days * 2);
  const { data, isLoading, error } = usePortfolioAnalytics(requested);
  const comparable = requested === days * 2;

  const shell = (children: ReactNode) => (
    <WorkspaceShell breadcrumb={[{ label: "Analytics" }]}>{children}</WorkspaceShell>
  );

  if (isLoading) {
    return shell(
      <div className="flex justify-center py-32">
        <Loader2 className="size-5 animate-spin text-muted-foreground" aria-label="Loading" />
      </div>,
    );
  }

  if (error || !data) {
    return shell(
      <div className="surface mx-auto max-w-md px-6 py-14 text-center">
        <p className="font-medium text-foreground">We couldn't load analytics.</p>
        <p className="mt-1.5 text-sm text-muted-foreground">{(error as Error)?.message}</p>
      </div>,
    );
  }

  // The request covers twice the window, so the tail is "now" and the head is
  // what it is being compared against.
  const daily = data.daily;
  const split = comparable ? daily.length - days : 0;
  const current = daily.slice(split);
  const previous = comparable ? daily.slice(0, split) : [];
  const sum = (rows: typeof daily, key: "starts" | "leads" | "completions") =>
    rows.reduce((total, row) => total + row[key], 0);

  const starts = sum(current, "starts");
  const leads = sum(current, "leads");
  const completions = sum(current, "completions");
  const priorStarts = sum(previous, "starts");
  const priorLeads = sum(previous, "leads");
  const priorCompletions = sum(previous, "completions");

  const conversion = starts > 0 ? (leads / starts) * 100 : null;
  const priorConversion = priorStarts > 0 ? (priorLeads / priorStarts) * 100 : null;
  const delta = (now: number, before: number) =>
    comparable ? { percent: percentChange(now, before) } : undefined;

  return shell(
    <>
      <PageHeader
        title="Analytics"
        description="Real visitor activity across every tool in this workspace."
        actions={<RangePicker value={days} onChange={setDays} />}
      />

      <StatRow>
        <StatCard
          label="Tools started"
          value={starts.toLocaleString()}
          delta={delta(starts, priorStarts)}
          note={comparable ? undefined : "No comparison at 90 days"}
        />
        <StatCard
          label="Finished"
          value={completions.toLocaleString()}
          delta={delta(completions, priorCompletions)}
          note={
            comparable
              ? undefined
              : starts > 0
                ? `${((completions / starts) * 100).toFixed(0)}% of starts`
                : undefined
          }
        />
        <StatCard
          label="Leads captured"
          value={leads.toLocaleString()}
          delta={delta(leads, priorLeads)}
        />
        <StatCard
          label="Start → lead"
          value={rate(conversion)}
          delta={
            comparable && conversion !== null && priorConversion !== null
              ? { percent: percentChange(conversion, priorConversion) }
              : // The absence of a comparison is itself worth stating, and it
                // is what the three cards beside this one say. Undefined left
                // this card alone with an empty line under its number.
                { percent: null }
          }
        />
      </StatRow>

      {/*
       * items-start, not the default stretch. The two cards used to be forced to
       * the tallest row height, which left the chart floating above ~120px of
       * empty card and the table above ~250px of it.
       */}
      <section className="mt-4 grid items-start gap-4 lg:grid-cols-[1.4fr_0.6fr]">
        <article className="surface flex flex-col p-5">
          <div className="flex items-start justify-between gap-4 pb-5">
            <div>
              <h2 className="text-base font-medium text-foreground">Activity</h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Bar height is everyone who started; the foot is who became a lead.
              </p>
            </div>
          </div>
          <ActivityChart daily={current} />
        </article>

        <Funnel data={data} />
      </section>

      <section className="mt-4 grid items-start gap-4 lg:grid-cols-[1.4fr_0.6fr]">
        <article className="surface overflow-hidden">
          <div className="flex items-center justify-between gap-4 border-b border-border px-5 py-4">
            <div>
              <h2 className="text-base font-medium text-foreground">Tools</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">All-time totals per tool</p>
            </div>
            <span className="text-xs text-muted-foreground">{data.totals.live ?? 0} live</span>
          </div>

          {data.experiences.length === 0 ? (
            <div className="px-5 py-12 text-center">
              <p className="text-sm font-medium text-foreground">Nothing to measure yet</p>
              <Link to="/build" className="mt-2 inline-block text-xs text-brand-solid underline">
                Build your first tool
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[32rem] text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-xs text-muted-foreground">
                    <th scope="col" className="px-5 py-2.5 font-normal">
                      Tool
                    </th>
                    <th scope="col" className="px-3 py-2.5 text-right font-normal">
                      Views
                    </th>
                    <th scope="col" className="px-3 py-2.5 text-right font-normal">
                      Leads
                    </th>
                    <th scope="col" className="px-5 py-2.5 text-right font-normal">
                      Lead rate
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {data.experiences.map((experience) => (
                    <tr key={experience.id}>
                      <td className="px-5 py-3">
                        <Link
                          to="/dashboard/widgets/$widgetId"
                          params={{ widgetId: experience.id }}
                          className="font-medium text-foreground hover:underline"
                        >
                          {experience.title}
                        </Link>
                        <span className="mt-0.5 block text-xs capitalize text-muted-foreground">
                          {experience.status}
                        </span>
                      </td>
                      <td className="tabular px-3 py-3 text-right text-muted-foreground">
                        {experience.views.toLocaleString()}
                      </td>
                      <td className="tabular px-3 py-3 text-right text-muted-foreground">
                        {experience.leads.toLocaleString()}
                      </td>
                      <td className="tabular px-5 py-3 text-right font-medium text-foreground">
                        {rate(experience.conversion_rate)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>

        <div className="grid gap-4">
          <article className="surface p-5">
            <h2 className="text-base font-medium text-foreground">Where visitors come from</h2>
            <div className="mt-4 space-y-3">
              {data.sources.length === 0 ? (
                <p className="text-xs leading-5 text-muted-foreground">
                  Source attribution appears once visitors engage.
                </p>
              ) : (
                data.sources.map((source) => {
                  const max = data.sources[0]?.engaged_visitors || 1;
                  return (
                    <div key={source.source}>
                      <div className="flex justify-between gap-3 text-xs">
                        <span className="truncate text-foreground">{source.source}</span>
                        <span className="tabular shrink-0 text-muted-foreground">
                          {source.engaged_visitors} · {source.leads} leads
                        </span>
                      </div>
                      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-n-100">
                        <span
                          className="block h-full rounded-full bg-chart-rest"
                          style={{ width: `${(source.engaged_visitors / max) * 100}%` }}
                        />
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </article>

          <article className="surface p-5">
            <h2 className="text-base font-medium text-foreground">Where people stop</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              The last step of journeys that were never finished
            </p>
            <div className="mt-4 space-y-2.5">
              {Object.keys(data.dropoff_by_step).length === 0 ? (
                <p className="text-xs leading-5 text-muted-foreground">
                  No unfinished journeys in this period.
                </p>
              ) : (
                Object.entries(data.dropoff_by_step)
                  .sort(([, a], [, b]) => b - a)
                  .slice(0, 5)
                  .map(([step, count]) => (
                    <div
                      key={step}
                      className="flex items-center justify-between gap-3 border-b border-border pb-2.5 text-xs last:border-0 last:pb-0"
                    >
                      <span className="truncate capitalize text-muted-foreground">
                        {step.replaceAll("_", " ")}
                      </span>
                      <span className="tabular font-medium text-foreground">{count}</span>
                    </div>
                  ))
              )}
            </div>
          </article>
        </div>
      </section>
    </>,
  );
}
