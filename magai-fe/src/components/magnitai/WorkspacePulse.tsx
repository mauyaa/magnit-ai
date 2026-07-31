import { Link } from "@tanstack/react-router";
import { ArrowRight, CircleDot, Loader2, ShieldCheck, TriangleAlert } from "lucide-react";

import type { WidgetData } from "@/lib/api";
import type { WorkspaceRecommendation } from "@/lib/workspace-recommendation";

function latestAutomaticCheck(widgets: WidgetData[]): Date | null {
  let latest: Date | null = null;

  for (const widget of widgets) {
    for (const value of [widget.last_heal_check_at, widget.last_brand_check_at]) {
      if (!value) continue;
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) continue;
      if (!latest || date > latest) latest = date;
    }
  }

  return latest;
}

function RecommendationLink({ recommendation }: { recommendation: WorkspaceRecommendation }) {
  const destination = recommendation.destination;

  if (destination.kind === "leads") {
    return (
      <Link to="/dashboard/leads" className="btn btn-primary h-10 shrink-0 text-sm">
        {recommendation.cta}
        <ArrowRight className="size-4" aria-hidden="true" />
      </Link>
    );
  }

  if (destination.kind === "build") {
    return (
      <Link
        to="/build-story/$widgetId"
        params={{ widgetId: destination.widgetId }}
        className="btn btn-primary h-10 shrink-0 text-sm"
      >
        {recommendation.cta}
        <ArrowRight className="size-4" aria-hidden="true" />
      </Link>
    );
  }

  return (
    <Link
      to="/dashboard/widgets/$widgetId"
      params={{ widgetId: destination.widgetId }}
      search={destination.tab ? { tab: destination.tab } : {}}
      className="btn btn-primary h-10 shrink-0 text-sm"
    >
      {recommendation.cta}
      <ArrowRight className="size-4" aria-hidden="true" />
    </Link>
  );
}

export function WorkspacePulse({
  widgets,
  recommendation,
  outcome,
}: {
  widgets: WidgetData[];
  recommendation: WorkspaceRecommendation;
  outcome: {
    title: string;
    detail: string;
  };
}) {
  const liveCount = widgets.filter(
    (widget) => widget.status === "active" && Boolean(widget.deployment_url),
  ).length;
  const latestCheck = latestAutomaticCheck(widgets);
  const RecommendationIcon =
    recommendation.tone === "attention"
      ? TriangleAlert
      : recommendation.tone === "pending"
        ? Loader2
        : CircleDot;

  return (
    <section className="surface mb-7 overflow-hidden" aria-labelledby="business-outcome-title">
      <div className="grid lg:grid-cols-[minmax(0,1.2fr)_minmax(19rem,0.8fr)]">
        <div className="p-5 sm:p-6">
          <span className="text-xs font-medium text-muted-foreground">
            Business outcome · last 30 days
          </span>
          <h2
            id="business-outcome-title"
            className="mt-2 text-xl font-medium tracking-[-0.025em] text-foreground"
          >
            {outcome.title}
          </h2>
          <p className="mt-1.5 max-w-3xl text-sm leading-6 text-muted-foreground">
            {outcome.detail}
          </p>
        </div>

        <aside className="border-t border-border bg-secondary/45 p-5 sm:p-6 lg:border-l lg:border-t-0">
          <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
            <RecommendationIcon
              className={`size-4 ${
                recommendation.tone === "attention"
                  ? "text-destructive"
                  : recommendation.tone === "pending"
                    ? "animate-spin text-foreground"
                    : "text-foreground"
              }`}
              aria-hidden="true"
            />
            Next best action
          </div>

          <div className="mt-3">
            <h3 className="text-base font-medium tracking-[-0.02em] text-foreground">
              {recommendation.title}
            </h3>
            <p className="mt-1.5 text-sm leading-6 text-muted-foreground">
              {recommendation.detail}
            </p>
            <div className="mt-5">
              <RecommendationLink recommendation={recommendation} />
            </div>
          </div>
        </aside>
      </div>

      <div className="flex flex-col gap-2 border-t border-border px-5 py-4 text-xs sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <span className="flex items-center gap-2 font-medium text-foreground">
          <ShieldCheck className="size-4" aria-hidden="true" />
          Automatic protection
        </span>
        <span className="leading-5 text-muted-foreground">
          {liveCount > 0
            ? `${liveCount} live ${liveCount === 1 ? "tool" : "tools"} watched`
            : "Starts after your first publish"}
          {latestCheck
            ? ` · Last check ${latestCheck.toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
              })}`
            : ""}
        </span>
      </div>
    </section>
  );
}
