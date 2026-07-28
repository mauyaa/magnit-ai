import { Link } from "@tanstack/react-router";
import { Check, CircleDashed, ExternalLink, Loader2, PartyPopper } from "lucide-react";

import { useReadiness, useWidgetFunnel, type ReadinessCheck, type WidgetData } from "@/lib/api";

/**
 * Where a failing check sends someone to fix it.
 *
 * The server names the destination; this maps it onto a tab or a screen. Kept
 * here rather than in the API because "which tab" is a client concern that the
 * backend has no business knowing.
 */
const ACTION_TABS: Record<string, { tab?: string; to?: string; label: string }> = {
  build: { tab: "overview", label: "Go to the build" },
  questions: { tab: "questions", label: "Edit questions" },
  outcomes: { tab: "outcomes", label: "Edit results" },
  embed: { tab: "embed", label: "Get the snippet" },
  integrations: { to: "/dashboard/integrations", label: "Set up delivery" },
  billing: { to: "/dashboard/settings", label: "See plans" },
};

function CheckRow({ check, widgetId }: { check: ReadinessCheck; widgetId: string }) {
  const action = ACTION_TABS[check.action];

  return (
    <li className="flex items-start gap-3 py-3">
      <span
        className={`mt-0.5 grid size-5 shrink-0 place-items-center rounded-full ${
          check.done ? "bg-success text-white" : "bg-n-100 text-n-400"
        }`}
        aria-hidden="true"
      >
        {check.done ? <Check className="size-3" /> : <CircleDashed className="size-3" />}
      </span>

      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-foreground">
          {check.label}
          {!check.blocking && !check.done && (
            <span className="ml-2 text-xs font-normal text-muted-foreground">optional</span>
          )}
        </p>
        <p className="mt-0.5 text-sm leading-6 text-muted-foreground">{check.detail}</p>
      </div>

      {!check.done && action && (
        <div className="shrink-0">
          {action.to ? (
            <Link to={action.to} className="btn btn-ghost h-8 px-2.5 text-xs">
              {action.label}
            </Link>
          ) : (
            <Link
              to="/dashboard/widgets/$widgetId"
              params={{ widgetId }}
              search={{ tab: action.tab as never }}
              className="btn btn-ghost h-8 px-2.5 text-xs"
            >
              {action.label}
            </Link>
          )}
        </div>
      )}
    </li>
  );
}

/**
 * The "is this actually working" panel.
 *
 * Every item is answered from real state — a deployment row, an impression with
 * a referrer, a connected integration — so it cannot say a tool is ready when it
 * is sitting on nobody's website.
 */
export function PublishChecklist({ widget }: { widget: WidgetData }) {
  const { data, isLoading } = useReadiness(widget.id);

  if (isLoading || !data) {
    return (
      <div className="surface flex justify-center py-12">
        <Loader2 className="size-5 animate-spin text-muted-foreground" aria-label="Loading" />
      </div>
    );
  }

  return (
    <section className="surface overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div>
          <h2 className="text-base font-medium text-foreground">Launch checklist</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {data.ready
              ? "Everything essential is in place."
              : "A few things left before this is doing its job."}
          </p>
        </div>
        <span className="tabular shrink-0 rounded-full bg-secondary px-2.5 py-1 text-xs font-medium text-foreground">
          {data.completed} / {data.total}
        </span>
      </div>

      <ul className="divide-y divide-border px-4">
        {data.checks.map((check) => (
          <CheckRow key={check.id} check={check} widgetId={widget.id} />
        ))}
      </ul>
    </section>
  );
}

/**
 * The moment a tool goes live.
 *
 * Shown on a tool's overview once it is deployed and embedded — the point at
 * which the customer has actually got what they paid for, and the only place in
 * the product where a bit of celebration is earned rather than decorative.
 */
export function LiveConfirmation({ widget }: { widget: WidgetData }) {
  const { data: funnel } = useWidgetFunnel(widget.id);

  if (!widget.deployment_url || widget.status !== "active") return null;

  const stats: Array<[string, string]> = [
    ["Visitors", (funnel?.views ?? widget.impressions_count).toLocaleString()],
    ["Started", (funnel?.starts ?? widget.starts_count).toLocaleString()],
    ["Finished", (funnel?.completions ?? widget.completions_count).toLocaleString()],
    ["Leads", (funnel?.leads ?? widget.leads_count).toLocaleString()],
  ];

  return (
    <section className="surface overflow-hidden">
      <div className="border-b border-border px-5 py-6 text-center">
        <span className="mx-auto grid size-11 place-items-center rounded-full bg-success/12">
          <PartyPopper className="size-5 text-success" aria-hidden="true" />
        </span>
        <h2 className="mt-3 text-lg font-medium text-foreground">Your tool is live</h2>
        <p className="mx-auto mt-1 max-w-md text-sm leading-6 text-muted-foreground">
          {widget.title} is published and ready to capture leads.
        </p>

        <div className="mx-auto mt-4 flex max-w-lg flex-col items-center gap-2 sm:flex-row">
          <span className="w-full min-w-0 truncate rounded-lg border border-border bg-n-50 px-3 py-2 text-left font-mono text-xs text-muted-foreground">
            {widget.deployment_url.replace(/^https?:\/\//, "")}
          </span>
          <a
            href={widget.deployment_url}
            target="_blank"
            rel="noreferrer"
            className="btn btn-primary h-9 w-full shrink-0 text-sm sm:w-auto"
          >
            View live
            <ExternalLink className="size-4" aria-hidden="true" />
          </a>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-px bg-border sm:grid-cols-4">
        {stats.map(([label, value]) => (
          <div key={label} className="bg-card px-4 py-3.5">
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className="tabular mt-1 text-xl font-medium text-foreground">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
