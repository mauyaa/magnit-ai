import { createFileRoute, Link } from "@tanstack/react-router";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  ExternalLink,
  RefreshCw,
  Globe,
  Users,
  Sparkles,
  Palette,
  Code2,
  Loader2,
} from "lucide-react";
import { AppShell } from "@/components/magnitai/AppShell";
import { PageShell } from "@/components/magnitai/ui/PageShell";
import { MetricStat } from "@/components/magnitai/ui/MetricStat";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { useWidget, useLeads, useDeployWidget } from "@/lib/api";

export const Route = createFileRoute("/dashboard/widgets/$widgetId")({
  head: () => ({ meta: [{ title: "Widget Details · Magnitai" }] }),
  component: WidgetDetail,
});

function WidgetDetail() {
  const { widgetId } = Route.useParams();
  const { data: widget, isLoading, error } = useWidget(widgetId);
  const { data: leads } = useLeads(widgetId);
  const deploy = useDeployWidget();

  if (isLoading) {
    return (
      <AppShell activeSection="dashboard">
        <PageShell>
          <div className="flex items-center justify-center py-32">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>
        </PageShell>
      </AppShell>
    );
  }

  if (error || !widget) {
    return (
      <AppShell activeSection="dashboard">
        <PageShell>
          <div className="rounded-2xl border border-destructive/20 bg-destructive/5 p-12 text-center">
            <p className="text-sm font-bold text-destructive">Widget not found</p>
            <Link
              to="/dashboard"
              className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-primary hover:underline"
            >
              <ArrowLeft className="size-4" /> Back to dashboard
            </Link>
          </div>
        </PageShell>
      </AppShell>
    );
  }

  const leadData = leads ?? [];

  return (
    <AppShell activeSection="dashboard">
      <PageShell>
        {/* Back + Header */}
        <Link
          to="/dashboard"
          className="mb-8 inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="size-4" /> Dashboard
        </Link>

        <div className="flex flex-col md:flex-row md:items-start justify-between gap-6 mb-12">
          <div>
            <div className="flex items-center gap-3 mb-3">
              <h1 className="font-heading text-4xl font-medium tracking-[-0.045em] text-foreground">
                {widget.title}
              </h1>
              <Badge
                variant={widget.deployment_url ? "default" : "secondary"}
                className="rounded-full text-[11px] uppercase tracking-widest"
              >
                {widget.deployment_url ? "Live" : widget.status}
              </Badge>
            </div>
            <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <Globe className="size-4" /> {widget.target_url}
              </span>
              <span className="flex items-center gap-1.5">
                <Code2 className="size-4" /> {widget.widget_type}
              </span>
              <span>Created {new Date(widget.created_at).toLocaleDateString()}</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {widget.deployment_url && (
              <a
                href={widget.deployment_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-10 items-center gap-2 rounded-xl border border-border bg-card px-5 text-sm font-bold text-foreground hover:bg-secondary transition-colors"
              >
                <ExternalLink className="size-4" /> Open
              </a>
            )}
            <button
              type="button"
              onClick={() => deploy.mutate(widget.id)}
              disabled={deploy.isPending}
              className="inline-flex h-10 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-bold text-primary-foreground shadow-sm hover:bg-primary/90 transition-colors disabled:opacity-60"
            >
              <RefreshCw className={`size-4 ${deploy.isPending ? "animate-spin" : ""}`} />
              {deploy.isPending ? "Deploying..." : "Redeploy"}
            </button>
          </div>
        </div>

        {/* Metric row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-16">
          <MetricStat icon={Users} subLabel="Leads" value={String(leadData.length)} label="Captured" iconColor="text-primary" valueSize="md" />
          <MetricStat icon={Sparkles} subLabel="Lead cap" value={`${widget.leads_count}/${widget.lead_cap}`} label={widget.plan_tier} iconColor="text-foreground" valueSize="md" />
          <MetricStat icon={Palette} subLabel="Design" value={widget.design_tokens ? "Applied" : "None"} label="Brand tokens" iconColor="text-foreground" valueSize="md" />
          <div className="flex flex-col rounded-2xl border border-border bg-card p-5 shadow-sm">
            <div className="eyebrow mb-3">Deployed</div>
            <div className="text-4xl font-medium font-mono tracking-tighter text-foreground mb-2">
              {widget.deployed_at ? "Yes" : "No"}
            </div>
            <div className="text-xs font-bold text-muted-foreground">
              {widget.deployed_at
                ? new Date(widget.deployed_at).toLocaleDateString()
                : "Not yet deployed"}
            </div>
          </div>
        </div>

        {/* Two-column: Preview + Leads */}
        <div className="grid lg:grid-cols-5 gap-10">
          {/* Embed Preview */}
          <div className="lg:col-span-3">
            <h2 className="font-heading text-lg font-semibold text-foreground mb-4">Preview</h2>
            {widget.deployment_url ? (
              <div className="rounded-2xl border border-border overflow-hidden bg-card">
                <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border bg-muted/30">
                  <span className="size-2.5 rounded-full bg-destructive/60" />
                  <span className="size-2.5 rounded-full bg-warning/60" />
                  <span className="size-2.5 rounded-full bg-success/60" />
                  <span className="ml-2 text-[11px] font-mono text-muted-foreground truncate">
                    {widget.deployment_url}
                  </span>
                </div>
                <iframe
                  src={widget.deployment_url}
                  title="Widget preview"
                  className="w-full h-[480px] bg-white"
                  sandbox="allow-scripts allow-same-origin"
                />
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border py-24 text-center">
                <Globe className="size-10 text-muted-foreground/40 mb-4" />
                <p className="text-sm font-medium text-muted-foreground">
                  Deploy this widget to see a preview
                </p>
              </div>
            )}
          </div>

          {/* Leads table */}
          <div className="lg:col-span-2">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-heading text-lg font-semibold text-foreground">Leads</h2>
              <span className="text-[11px] font-mono font-bold text-muted-foreground">
                {leadData.length} total
              </span>
            </div>

            {leadData.length === 0 ? (
              <div className="flex flex-col items-center rounded-2xl border border-dashed border-border py-16 text-center">
                <Users className="size-8 text-muted-foreground/40 mb-3" />
                <p className="text-sm font-medium text-muted-foreground">No leads yet</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-[520px] overflow-y-auto">
                {leadData.map((lead) => (
                  <div
                    key={lead.id}
                    className="rounded-xl border border-border bg-card p-4 hover:bg-secondary/40 transition-colors"
                  >
                    <div className="font-semibold text-foreground text-sm truncate">
                      {lead.name || "Anonymous"}
                    </div>
                    <div className="text-xs text-muted-foreground font-mono mt-0.5 truncate">
                      {lead.email}
                    </div>
                    <div className="flex items-center justify-between mt-2 text-[11px] text-muted-foreground">
                      {lead.score != null && <span>Score: {lead.score}</span>}
                      <span>{new Date(lead.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Brand tokens section */}
        {widget.brand_tokens && (
          <div className="mt-16">
            <h2 className="font-heading text-lg font-semibold text-foreground mb-4">Brand Tokens</h2>
            <div className="rounded-2xl border border-border bg-card p-6">
              <pre className="text-xs font-mono text-muted-foreground overflow-x-auto whitespace-pre-wrap">
                {JSON.stringify(widget.brand_tokens, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </PageShell>
    </AppShell>
  );
}
