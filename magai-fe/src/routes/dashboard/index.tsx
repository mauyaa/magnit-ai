import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { ArrowRight, ExternalLink, Globe2, Loader2, Plus, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";

import { RequireAuth } from "@/components/magnitai/RequireAuth";
import { PageHeader, StatusPill } from "@/components/magnitai/shell/PageHeader";
import { percentChange, StatCard, StatRow } from "@/components/magnitai/shell/StatCard";
import { WorkspaceShell } from "@/components/magnitai/shell/WorkspaceShell";
import { usePortfolioAnalytics, useWidgets, type WidgetData } from "@/lib/api";
import { journeyDomain, loadSavedJourney, type SavedJourney } from "@/lib/journey-storage";

export const Route = createFileRoute("/dashboard/")({
  head: () => ({ meta: [{ title: "Overview · Magnitai" }] }),
  component: () => (
    <RequireAuth>
      <DashboardHome />
    </RequireAuth>
  ),
});

/** A widget's status, expressed once, so every screen agrees on the words. */
function statusOf(widget: WidgetData) {
  if (widget.status === "failed") return { tone: "attention" as const, label: "Needs attention" };
  if (widget.status === "building") return { tone: "pending" as const, label: "Building" };
  if (widget.deployment_url && widget.status === "active")
    return { tone: "live" as const, label: "Live" };
  return { tone: "idle" as const, label: "Draft" };
}

function brandColors(widget: WidgetData) {
  const read = (key: string, fallback: string) =>
    typeof widget.brand_tokens?.[key] === "string"
      ? (widget.brand_tokens[key] as string)
      : fallback;
  return {
    primary: read("primary_color", "#1f2430"),
    accent: read("accent_color", "#1f2430"),
    background: read("background_color", "#f2f1ed"),
  };
}

/**
 * The card's upper half.
 *
 * Every status now renders something. Previously only a live tool drew a
 * preview; everything else fell through to a 16rem grey rectangle containing
 * the words "Ready to build" — a third of the card's area spent saying nothing,
 * on exactly the tools that most needed the owner to act.
 */
function ToolCanvas({ widget }: { widget: WidgetData }) {
  const { primary, accent, background } = brandColors(widget);
  const status = statusOf(widget);

  if (status.tone === "attention") {
    return (
      <div className="flex h-44 flex-col items-center justify-center gap-2 bg-n-100 px-6 text-center">
        <TriangleAlert className="size-5 text-destructive" aria-hidden="true" />
        <p className="text-sm font-medium text-foreground">This tool stopped responding</p>
        <p className="text-xs text-muted-foreground">The last healthy version is still serving.</p>
      </div>
    );
  }

  if (status.tone === "pending") {
    const progress = widget.build_progress ?? 0;
    return (
      <div className="flex h-44 flex-col justify-center gap-3 bg-n-100 px-6">
        <div className="flex items-center gap-2 text-sm font-medium text-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          Building
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-n-200">
          <span
            className="block h-full rounded-full bg-foreground transition-[width] duration-500"
            style={{ width: `${Math.max(4, progress)}%` }}
          />
        </div>
        <p className="text-xs capitalize text-muted-foreground">
          {widget.build_stage?.replaceAll("_", " ") ?? "Preparing"} · {progress}%
        </p>
      </div>
    );
  }

  // Live and draft both show the brand, because the brand is what the owner
  // approved and what they recognise their own tool by.
  return (
    <div
      className="relative h-44 overflow-hidden px-5 py-4"
      style={{ color: primary, backgroundColor: background }}
    >
      <span className="text-[10px] font-semibold uppercase tracking-[0.14em] opacity-50">
        {widget.widget_type.replaceAll("_", " ")}
      </span>
      <h3 className="mt-2 line-clamp-2 max-w-[18ch] text-xl font-semibold leading-[1.1] tracking-[-0.03em]">
        {widget.title}
      </h3>
      <div className="absolute inset-x-5 bottom-4">
        <div className="h-1 overflow-hidden rounded-full bg-current/12">
          <span className="block h-full w-[62%] rounded-full" style={{ backgroundColor: accent }} />
        </div>
        <div
          className="mt-3 flex h-8 items-center justify-between rounded-md px-2.5 text-[11px] font-semibold"
          style={{ backgroundColor: accent, color: background }}
        >
          <span>{status.tone === "live" ? "See your result" : "Not published yet"}</span>
          <ArrowRight className="size-3.5" aria-hidden="true" />
        </div>
      </div>
    </div>
  );
}

function ToolCard({ widget }: { widget: WidgetData }) {
  const status = statusOf(widget);
  // The server's own definition: leads ÷ views. Recomputing it here is how the
  // dashboard and the analytics table used to print different numbers for the
  // same tool.
  const leadRate = widget.conversion_rate === null ? "—" : `${widget.conversion_rate.toFixed(1)}%`;

  return (
    <Link
      to="/dashboard/widgets/$widgetId"
      params={{ widgetId: widget.id }}
      className="group surface block overflow-hidden transition-[transform,box-shadow] hover:-translate-y-0.5 hover:shadow-float focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      <ToolCanvas widget={widget} />

      <div className="border-t border-border px-4 py-3.5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-foreground">{widget.title}</p>
            <p className="mt-0.5 truncate text-xs text-muted-foreground">
              {journeyDomain(widget.target_url)}
            </p>
          </div>
          <ExternalLink
            className="mt-0.5 size-3.5 shrink-0 text-n-400 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
            aria-hidden="true"
          />
        </div>

        {/*
         * Three numbers in fixed positions, so cards can be compared by eye —
         * and labelled "all time", because the KPI strip above them is a
         * 30-day window. Two scopes on one screen is fine; two scopes both
         * called "conversion" is what made the old screen contradict itself.
         */}
        <div className="mt-3.5 border-t border-border pt-3">
          <p className="text-[10px] font-medium uppercase tracking-[0.1em] text-n-400">All time</p>
        </div>
        <dl className="mt-2 grid grid-cols-3 gap-2">
          {[
            ["Views", widget.impressions_count.toLocaleString()],
            ["Leads", widget.leads_count.toLocaleString()],
            ["Lead rate", leadRate],
          ].map(([label, value]) => (
            <div key={label}>
              <dt className="text-[11px] text-muted-foreground">{label}</dt>
              <dd className="tabular mt-0.5 text-sm font-medium text-foreground">{value}</dd>
            </div>
          ))}
        </dl>

        <div className="mt-3 border-t border-border pt-2.5">
          <StatusPill tone={status.tone}>{status.label}</StatusPill>
        </div>
      </div>
    </Link>
  );
}

/** Someone chose a direction but never finished — offer the thread back. */
function ResumeBanner({ journey }: { journey: SavedJourney }) {
  if (journey.selectedIndex === null) return null;
  const selected = journey.concepts[journey.selectedIndex];
  const autopilot = journey.brief.mode === "autopilot";

  return (
    <div className="surface mb-6 flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
      <div className="min-w-0">
        <p className="text-sm font-medium text-foreground">
          {autopilot
            ? "Your AI-built direction is ready"
            : `You left off partway through ${journeyDomain(journey.target_url)}`}
        </p>
        <p className="mt-0.5 truncate text-sm text-muted-foreground">
          {autopilot
            ? `${selected.blueprint.title} is saved in your workspace for ${journeyDomain(journey.target_url)}.`
            : `${selected.blueprint.title} is ready for you to continue.`}
        </p>
      </div>
      <Link to="/build" className="btn btn-primary h-9 shrink-0 text-sm">
        {autopilot ? "Review and continue" : "Resume"}
        <ArrowRight className="size-4" aria-hidden="true" />
      </Link>
    </div>
  );
}

/** Nothing built yet: one field, one action, nothing else on the screen. */
function EmptyWorkspace() {
  const navigate = useNavigate();
  const [value, setValue] = useState("");

  return (
    <div className="surface mx-auto max-w-xl px-6 py-12 text-center sm:px-10 sm:py-16">
      <span className="mx-auto grid size-11 place-items-center rounded-xl bg-secondary">
        <Globe2 className="size-5 text-foreground" aria-hidden="true" />
      </span>
      <h2 className="mt-5 text-xl font-medium tracking-[-0.02em] text-foreground">
        Start with your website
      </h2>
      <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-muted-foreground">
        Magnitai reads your site, then proposes two tools built from what it finds. It takes about
        two minutes.
      </p>

      <form
        className="mx-auto mt-7 max-w-sm text-left"
        onSubmit={(event) => {
          event.preventDefault();
          navigate({ to: "/build", search: value ? { site: value } : {} });
        }}
      >
        <label htmlFor="first-site" className="mb-1.5 block text-sm font-medium text-foreground">
          Your website
        </label>
        <div className="flex items-center gap-1.5 rounded-lg border border-border-strong bg-card py-1.5 pl-3 pr-1.5 shadow-raised focus-within:border-foreground/40">
          <span className="shrink-0 text-sm text-n-400">https://</span>
          <input
            id="first-site"
            spellCheck={false}
            placeholder="northsidedental.com"
            value={value}
            onChange={(event) => setValue(event.target.value.replace(/^https?:\/\//i, ""))}
            className="h-8 min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-n-400"
          />
          <button type="submit" className="btn btn-primary h-8 shrink-0 px-3 text-sm">
            Start
          </button>
        </div>
      </form>
    </div>
  );
}

function DashboardHome() {
  const { data, isLoading, error } = useWidgets();
  // 60 days, split in half: the second half is "now", the first is what it is
  // being compared against. One request, a real previous period.
  const { data: analytics } = usePortfolioAnalytics(60);
  const [pending, setPending] = useState<SavedJourney | null>(null);

  useEffect(() => {
    setPending(loadSavedJourney());
  }, []);

  const widgets = data?.widgets ?? [];
  const live = widgets.filter((w) => w.status === "active").length;

  const daily = analytics?.daily ?? [];
  const half = Math.floor(daily.length / 2);
  const sum = (rows: typeof daily, key: "starts" | "leads") =>
    rows.reduce((total, row) => total + row[key], 0);

  const currentStarts = sum(daily.slice(half), "starts");
  const previousStarts = sum(daily.slice(0, half), "starts");
  const currentLeads = sum(daily.slice(half), "leads");
  const previousLeads = sum(daily.slice(0, half), "leads");

  const currentRate = currentStarts > 0 ? (currentLeads / currentStarts) * 100 : null;
  const previousRate = previousStarts > 0 ? (previousLeads / previousStarts) * 100 : null;

  if (isLoading) {
    return (
      <WorkspaceShell breadcrumb={[{ label: "Overview" }]}>
        <div className="flex justify-center py-32">
          <Loader2 className="size-5 animate-spin text-muted-foreground" aria-label="Loading" />
        </div>
      </WorkspaceShell>
    );
  }

  if (error) {
    return (
      <WorkspaceShell breadcrumb={[{ label: "Overview" }]}>
        <div className="surface mx-auto max-w-md px-6 py-14 text-center">
          <p className="font-medium text-foreground">We couldn't open your workspace.</p>
          <p className="mt-1.5 text-sm text-muted-foreground">{(error as Error).message}</p>
        </div>
      </WorkspaceShell>
    );
  }

  return (
    <WorkspaceShell breadcrumb={[{ label: "Overview" }]}>
      <PageHeader
        title="Overview"
        description="Every tool Magnitai is running for you, and what they brought in."
        meta={
          widgets.length > 0 ? (
            <StatusPill tone={live > 0 ? "live" : "idle"}>
              {live > 0
                ? `${live} of ${widgets.length} ${widgets.length === 1 ? "tool" : "tools"} live`
                : "Nothing live yet"}
            </StatusPill>
          ) : undefined
        }
      />

      {pending && <ResumeBanner journey={pending} />}

      {widgets.length === 0 ? (
        <EmptyWorkspace />
      ) : (
        <>
          <div className="flex items-baseline justify-between gap-4 pb-3">
            <h2 className="text-base font-medium text-foreground">Last 30 days</h2>
            <span className="text-xs text-muted-foreground">compared with the 30 days before</span>
          </div>
          <StatRow>
            <StatCard label="Live tools" value={String(live)} note={`${widgets.length} in total`} />
            <StatCard
              label="Tools started"
              value={currentStarts.toLocaleString()}
              delta={{ percent: percentChange(currentStarts, previousStarts) }}
            />
            <StatCard
              label="Leads captured"
              value={currentLeads.toLocaleString()}
              delta={{ percent: percentChange(currentLeads, previousLeads) }}
            />
            <StatCard
              label="Start → lead"
              value={currentRate === null ? "—" : `${currentRate.toFixed(1)}%`}
              delta={
                currentRate !== null && previousRate !== null
                  ? { percent: percentChange(currentRate, previousRate) }
                  : undefined
              }
              note={currentRate === null ? "Starts after your first visitor" : undefined}
            />
          </StatRow>

          <section className="mt-8">
            <div className="flex items-center justify-between gap-4 pb-4">
              <h2 className="text-base font-medium text-foreground">Your tools</h2>
              {/*
               * Only below lg, where the rail is behind a hamburger. Above it the
               * rail's own button is already on screen, and two identical primary
               * actions on one page is the duplication this rebuild set out to
               * remove — the old header carried one while the nav carried another.
               */}
              <Link to="/build" className="btn btn-secondary h-8 px-3 text-sm lg:hidden">
                <Plus className="size-4" aria-hidden="true" />
                New tool
              </Link>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {widgets.map((widget) => (
                <ToolCard key={widget.id} widget={widget} />
              ))}
            </div>
          </section>
        </>
      )}
    </WorkspaceShell>
  );
}
