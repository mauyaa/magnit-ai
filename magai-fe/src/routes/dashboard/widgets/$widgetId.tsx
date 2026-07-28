import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, ExternalLink, Loader2, RefreshCw, Undo2, Users } from "lucide-react";

import { EmbedCodePanel } from "@/components/magnitai/EmbedCodePanel";
import { LaunchSettings } from "@/components/magnitai/LaunchSettings";
import { OutcomesEditor } from "@/components/magnitai/outcomes/OutcomesEditor";
import { QuestionEditor } from "@/components/magnitai/outcomes/QuestionEditor";
import { LiveConfirmation, PublishChecklist } from "@/components/magnitai/PublishChecklist";
import { RequireAuth } from "@/components/magnitai/RequireAuth";
import { PageHeader, StatusPill } from "@/components/magnitai/shell/PageHeader";
import { WidgetTabs, type TabDefinition, type WidgetTabId } from "@/components/magnitai/shell/Tabs";
import { WorkspaceShell } from "@/components/magnitai/shell/WorkspaceShell";
import {
  useDeployments,
  useDeployWidget,
  useHealEvents,
  useLeads,
  useRollbackWidget,
  useWidget,
  useWidgetFunnel,
  type HealEvent,
  type WidgetData,
} from "@/lib/api";

const TAB_IDS: WidgetTabId[] = [
  "overview",
  "questions",
  "outcomes",
  "embed",
  "leads",
  "activity",
  "settings",
];

export const Route = createFileRoute("/dashboard/widgets/$widgetId")({
  head: () => ({ meta: [{ title: "Your tool · Magnitai" }] }),
  /*
   * The open tab lives in the URL, so it can be linked to and survives a reload.
   * It is *optional* on purpose: declaring it required makes every <Link> to a
   * tool anywhere in the app — the overview cards, the leads table, the
   * analytics table — fail to compile until each one names a tab it has no
   * opinion about. Absent means "overview".
   */
  validateSearch: (search: Record<string, unknown>): { tab?: WidgetTabId } => {
    const requested = search.tab as WidgetTabId;
    return TAB_IDS.includes(requested) ? { tab: requested } : {};
  },
  component: () => (
    <RequireAuth>
      <WidgetDetail />
    </RequireAuth>
  ),
});

const HEAL_LABEL: Record<HealEvent["check_type"], string> = {
  brand_drift: "Their site changed",
  deploy_health: "The deployment went down",
};

function statusOf(widget: WidgetData) {
  if (widget.status === "failed") return { tone: "attention" as const, label: "Needs attention" };
  if (widget.status === "building") return { tone: "pending" as const, label: "Building" };
  if (widget.deployment_url && widget.status === "active")
    return { tone: "live" as const, label: "Live" };
  return { tone: "idle" as const, label: "Not published" };
}

/**
 * A heal event, described by what happened rather than by its status enum.
 * The old-vs-new swatches are the evidence — they show the drift, not claim it.
 */
function HealRow({ event }: { event: HealEvent }) {
  const changes = Object.entries(event.diff_summary ?? {}).filter(([key]) => key !== "error");
  const healed = event.status === "healed";

  return (
    <li className="border-b border-border py-5 last:border-b-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span
            className={`size-2 rounded-full ${
              healed ? "bg-success" : event.status === "failed" ? "bg-destructive" : "bg-warning"
            }`}
            aria-hidden="true"
          />
          <span className="text-sm font-medium text-foreground">
            {HEAL_LABEL[event.check_type] ?? event.check_type}
          </span>
        </div>
        <span className="text-xs font-mono text-muted-foreground">
          {new Date(event.detected_at).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
          })}
          {healed && event.healed_at
            ? " · Auto-repaired"
            : event.status === "failed"
              ? " · Manual review"
              : ""}
        </span>
      </div>

      {changes.length > 0 && (
        <div className="mt-4 grid gap-2 border-t border-border pt-4 font-mono text-xs">
          {changes.map(([key, change]) => {
            const isColor = /^#[0-9a-f]{3,8}$/i.test(String(change.new));
            return (
              <div
                key={key}
                className="grid items-center gap-2 rounded-lg bg-background px-3 py-2.5 sm:grid-cols-[8rem_1fr_auto_1fr]"
              >
                <span className="font-sans text-xs font-medium capitalize text-muted-foreground">
                  {key.replace(/_/g, " ")}
                </span>
                <div className="flex min-w-0 items-center gap-1.5 rounded bg-secondary px-2 py-1">
                  {isColor && (
                    <span
                      className="size-3.5 shrink-0 rounded-full border border-foreground/20 shadow-xs"
                      style={{ background: String(change.old) }}
                      aria-hidden="true"
                    />
                  )}
                  <span className="truncate text-muted-foreground line-through">
                    {String(change.old)}
                  </span>
                </div>
                <ArrowRight className="size-3.5 text-muted-foreground" aria-hidden="true" />
                <div className="flex min-w-0 items-center gap-1.5 rounded border border-brand-solid/20 bg-brand-wash px-2 py-1 text-foreground">
                  {isColor && (
                    <span
                      className="size-3.5 shrink-0 rounded-full border border-foreground/20 shadow-xs"
                      style={{ background: String(change.new) }}
                      aria-hidden="true"
                    />
                  )}
                  <span className="truncate font-semibold">{String(change.new)}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </li>
  );
}

function LivePreview({ widget }: { widget: WidgetData }) {
  if (widget.deployment_url) {
    return (
      <div className="surface overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-2.5">
          <span className="truncate font-mono text-xs text-muted-foreground">
            {widget.deployment_url.replace(/^https?:\/\//, "")}
          </span>
          <a
            href={widget.deployment_url}
            target="_blank"
            rel="noreferrer"
            className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          >
            Open
            <ExternalLink className="size-3.5" aria-hidden="true" />
          </a>
        </div>
        <iframe
          src={widget.deployment_url}
          title={`${widget.title} — live preview`}
          className="h-[30rem] w-full border-0 bg-white"
          sandbox="allow-scripts allow-same-origin allow-forms"
        />
      </div>
    );
  }

  return (
    <div className="surface px-6 py-16 text-center">
      {widget.status === "building" ? (
        <>
          <Loader2
            className="mx-auto size-5 animate-spin text-muted-foreground"
            aria-hidden="true"
          />
          <p className="mt-3 text-sm font-medium text-foreground">Still building</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {widget.build_stage?.replaceAll("_", " ") ?? "Preparing"} · {widget.build_progress ?? 0}
            %
          </p>
        </>
      ) : (
        <>
          <p className="text-sm font-medium text-foreground">Not published yet</p>
          <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">
            Finish this tool to publish it to its own address and get an embed snippet.
          </p>
          <Link to="/build" className="btn btn-primary mt-5 h-9 text-sm">
            Continue building
            <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </>
      )}
    </div>
  );
}

function WidgetDetail() {
  const { widgetId } = Route.useParams();
  const { tab = "overview" } = Route.useSearch();
  const { data: widget, isLoading, error } = useWidget(widgetId);
  const { data: leads } = useLeads(widgetId);
  const { data: healEvents } = useHealEvents(widgetId);
  const { data: deployments } = useDeployments(widgetId);
  const { data: funnel } = useWidgetFunnel(widgetId);
  const deploy = useDeployWidget();
  const rollback = useRollbackWidget();

  if (isLoading) {
    return (
      <WorkspaceShell breadcrumb={[{ label: "Overview", to: "/dashboard" }, { label: "Tool" }]}>
        <div className="flex justify-center py-32">
          <Loader2 className="size-5 animate-spin text-muted-foreground" aria-label="Loading" />
        </div>
      </WorkspaceShell>
    );
  }

  if (error || !widget) {
    return (
      <WorkspaceShell breadcrumb={[{ label: "Overview", to: "/dashboard" }, { label: "Tool" }]}>
        <div className="surface mx-auto max-w-md px-6 py-14 text-center">
          <p className="font-medium text-foreground">We couldn't find that tool.</p>
          <Link to="/dashboard" className="btn btn-secondary mt-5 h-9 text-sm">
            Back to your tools
          </Link>
        </div>
      </WorkspaceShell>
    );
  }

  const leadData = leads ?? [];
  const heals = (healEvents ?? []).filter((event) => event.status !== "no_drift");
  const canRollback = (deployments ?? []).some((record) => !record.is_current);
  const status = statusOf(widget);

  const tabs: TabDefinition[] = [
    { id: "overview", label: "Overview" },
    // Between Overview and Embed on purpose: this is the order the work happens
    // in — see how it is doing, change what it asks, change what it says back,
    // then put it on the page.
    { id: "questions", label: "Questions" },
    { id: "outcomes", label: "Results" },
    { id: "embed", label: "Embed" },
    { id: "leads", label: "Leads", badge: leadData.length },
    { id: "activity", label: "Activity", badge: heals.length },
    { id: "settings", label: "Settings" },
  ];

  return (
    <WorkspaceShell breadcrumb={[{ label: "Overview", to: "/dashboard" }, { label: widget.title }]}>
      <PageHeader
        title={widget.title}
        meta={
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <StatusPill tone={status.tone}>{status.label}</StatusPill>
            <span className="font-mono text-sm text-muted-foreground">
              {widget.target_url.replace(/^https?:\/\//, "")}
            </span>
          </div>
        }
        actions={
          widget.deployment_url ? (
            <a
              href={widget.deployment_url}
              target="_blank"
              rel="noreferrer"
              className="btn btn-secondary h-9 text-sm"
            >
              View live
              <ExternalLink className="size-4" aria-hidden="true" />
            </a>
          ) : undefined
        }
      />

      <WidgetTabs tabs={tabs} active={tab} widgetId={widget.id} />

      <div className="pt-6">
        {tab === "overview" && (
          <div className="space-y-4">
            {/*
             * A live tool leads with the fact that it is live and what it has
             * brought in; anything not yet live leads with what is stopping it.
             * Both answer the same question — "is this working" — which is the
             * only question this page exists for.
             */}
            {status.tone === "live" ? (
              <LiveConfirmation widget={widget} />
            ) : (
              <PublishChecklist widget={widget} />
            )}

            {funnel && (
              <section className="grid grid-cols-2 gap-px overflow-hidden rounded-[--radius-surface] border border-border bg-border sm:grid-cols-5">
                {(
                  [
                    ["Viewed", funnel.views],
                    ["Started", funnel.starts],
                    ["Finished", funnel.completions],
                    ["Leads", funnel.leads],
                    ["CTA clicks", funnel.cta_clicks],
                  ] as const
                ).map(([label, value]) => (
                  <div key={label} className="bg-card px-4 py-3.5">
                    <span className="block text-xs text-muted-foreground">{label}</span>
                    <strong className="tabular mt-1 block text-xl font-medium text-foreground">
                      {Number(value).toLocaleString()}
                    </strong>
                  </div>
                ))}
              </section>
            )}
            <LivePreview widget={widget} />

            {/* The checklist stays reachable once live: an embed that gets
                removed from the host page is exactly the kind of quiet failure
                it exists to catch. */}
            {status.tone === "live" && <PublishChecklist widget={widget} />}
          </div>
        )}

        {tab === "questions" && <QuestionEditor widget={widget} />}

        {tab === "outcomes" && <OutcomesEditor widget={widget} />}

        {tab === "embed" && (
          <EmbedCodePanel embedCode={widget.embed_code} deploymentUrl={widget.deployment_url} />
        )}

        {tab === "leads" && (
          <div className="surface overflow-hidden">
            <div className="border-b border-border px-5 py-4">
              <h2 className="text-base font-medium text-foreground">Leads from this tool</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Open a lead to see its answers, result and delivery history.
              </p>
            </div>
            {leadData.length === 0 ? (
              <div className="px-5 py-14 text-center">
                <span className="mx-auto grid size-10 place-items-center rounded-xl bg-secondary">
                  <Users className="size-4 text-foreground" aria-hidden="true" />
                </span>
                <p className="mt-4 text-sm font-medium text-foreground">No leads yet</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  A lead will appear here after a visitor completes the capture step.
                </p>
              </div>
            ) : (
              <ul className="divide-y divide-border">
                {leadData.map((lead) => (
                  <li key={lead.id} className="px-5 py-3.5">
                    <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
                      <Link
                        to="/dashboard/leads/$leadId"
                        params={{ leadId: lead.id }}
                        className="text-sm font-medium text-foreground hover:underline"
                      >
                        {lead.email}
                      </Link>
                      <span className="text-xs text-muted-foreground">
                        {lead.name ? `${lead.name} · ` : ""}
                        {new Date(lead.created_at).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                        })}
                      </span>
                    </div>
                    {lead.answers && Object.keys(lead.answers).length > 0 && (
                      <details className="pt-1.5 text-sm text-muted-foreground">
                        <summary className="cursor-pointer select-none text-xs">
                          View answers
                        </summary>
                        <dl className="mt-2 grid gap-1 rounded-lg bg-n-50 p-3 text-xs">
                          {Object.entries(lead.answers).map(([key, value]) => (
                            <div key={key} className="flex justify-between gap-4">
                              <dt className="capitalize">{key.replace(/_/g, " ")}</dt>
                              <dd className="font-medium text-foreground">{String(value)}</dd>
                            </div>
                          ))}
                        </dl>
                      </details>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {tab === "activity" && (
          <div className="surface p-5">
            <h2 className="text-base font-medium text-foreground">What we fixed for you</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Every automatic check that found something and what it did about it.
            </p>
            {heals.length === 0 ? (
              <p className="mt-6 rounded-lg border border-dashed border-border bg-n-50 px-4 py-10 text-center text-sm text-muted-foreground">
                Nothing has needed repairing. Checks run every few hours.
              </p>
            ) : (
              <ul className="mt-4">
                {heals.map((event) => (
                  <HealRow key={event.id} event={event} />
                ))}
              </ul>
            )}
          </div>
        )}

        {tab === "settings" && (
          <div className="space-y-4">
            <LaunchSettings widget={widget} />

            {/* Maintenance: rarely needed, never the point, so it sits last. */}
            <section className="surface p-5">
              <h2 className="text-base font-medium text-foreground">Maintenance</h2>
              <p className="mt-1 max-w-prose text-sm text-muted-foreground">
                Republishing sends the last build out again — use it if the live address stops
                answering. It does not regenerate anything.
              </p>
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => deploy.mutate(widget.id)}
                  disabled={deploy.isPending}
                  className="btn btn-secondary h-9 text-sm"
                >
                  <RefreshCw
                    className={`size-4 ${deploy.isPending ? "animate-spin" : ""}`}
                    aria-hidden="true"
                  />
                  {deploy.isPending ? "Republishing" : "Republish"}
                </button>
                {canRollback && (
                  <button
                    type="button"
                    onClick={() => rollback.mutate(widget.id)}
                    disabled={rollback.isPending}
                    className="btn btn-ghost h-9 text-sm"
                  >
                    <Undo2 className="size-4" aria-hidden="true" />
                    {rollback.isPending ? "Reverting" : "Revert to the last version"}
                  </button>
                )}
              </div>
              {(deploy.error || rollback.error) && (
                <p role="alert" className="mt-3 text-sm text-destructive">
                  {((deploy.error || rollback.error) as Error).message}
                </p>
              )}
            </section>
          </div>
        )}
      </div>
    </WorkspaceShell>
  );
}
