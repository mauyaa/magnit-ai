import { createFileRoute, Link } from "@tanstack/react-router";
import { motion } from "framer-motion";
import {
  LayoutDashboard,
  Globe,
  Zap,
  TrendingUp,
  ArrowUpRight,
  ExternalLink,
  RefreshCw,
  Eye,
  Loader2,
} from "lucide-react";
import { AppShell } from "@/components/magnitai/AppShell";
import { PageShell } from "@/components/magnitai/ui/PageShell";
import { SectionIntro } from "@/components/magnitai/ui/SectionIntro";
import { MetricStat } from "@/components/magnitai/ui/MetricStat";
import { useWidgets, useDeployWidget } from "@/lib/api";
import { DashboardNav } from "@/components/magnitai/DashboardNav";

export const Route = createFileRoute("/dashboard/")({
  head: () => ({ meta: [{ title: "Dashboard · Magnitai" }] }),
  component: DashboardHome,
});

function DashboardHome() {
  const { data, isLoading, error } = useWidgets();
  const deploy = useDeployWidget();
  const widgets = data?.widgets ?? [];

  const totalLeads = widgets.reduce((s, w) => s + w.leads_count, 0);
  const activeWidgets = widgets.filter((w) => w.status === "active");
  const deployedWidgets = widgets.filter((w) => w.deployment_url);

  return (
    <AppShell activeSection="dashboard">
      <PageShell>
        <DashboardNav />
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-16">
          <SectionIntro
            dot="success"
            eyebrow="Dashboard"
            heading={<>Your <span className="hero-accent">widget fleet</span></>}
            body="Monitor, deploy, and manage all your Magnitai widgets from one place."
            className="w-full"
          />
          <Link
            to="/build"
            className="shrink-0 inline-flex h-12 items-center gap-2 rounded-xl bg-primary px-6 text-sm font-bold text-primary-foreground shadow-sm transition-transform hover:-translate-y-0.5 active:scale-[0.97]"
          >
            Create widget <ArrowUpRight className="size-4" />
          </Link>
        </div>

        {/* Metric cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8 mb-20">
          <MetricStat
            icon={LayoutDashboard}
            subLabel="Total widgets"
            value={String(widgets.length)}
            label={`${activeWidgets.length} active`}
            iconColor="text-primary"
            valueSize="lg"
          />
          <MetricStat
            icon={Zap}
            subLabel="Active"
            value={String(activeWidgets.length)}
            label={`${deployedWidgets.length} deployed`}
            iconColor="text-success"
            valueSize="lg"
          />
          <MetricStat
            icon={TrendingUp}
            subLabel="Leads captured"
            value={String(totalLeads)}
            label="Across all widgets"
            iconColor="text-foreground"
            valueSize="lg"
          />
          <MetricStat
            icon={Globe}
            subLabel="Deploy rate"
            value={widgets.length ? `${Math.round((deployedWidgets.length / widgets.length) * 100)}%` : "—"}
            label={`${deployedWidgets.length}/${widgets.length} live`}
            iconColor="text-info"
            valueSize="lg"
          />
        </div>

        {/* Widgets list */}
        <div className="flex items-center justify-between mb-8">
          <h2 className="font-heading text-2xl font-semibold text-foreground tracking-tight">
            All Widgets
          </h2>
          <span className="text-[11px] font-mono font-bold text-muted-foreground">
            {widgets.length} total
          </span>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {error && (
          <div className="rounded-2xl border border-destructive/20 bg-destructive/5 p-8 text-center">
            <p className="text-sm font-bold text-destructive">Failed to load widgets</p>
            <p className="mt-1 text-xs text-muted-foreground">{(error as Error).message}</p>
          </div>
        )}

        {!isLoading && !error && widgets.length === 0 && (
          <div className="flex flex-col items-center rounded-2xl border border-dashed border-border py-24 text-center">
            <LayoutDashboard className="size-10 text-muted-foreground/40 mb-4" />
            <h3 className="font-heading text-xl font-medium text-foreground">No widgets yet</h3>
            <p className="mt-2 max-w-sm text-sm font-medium text-muted-foreground">
              Build your first widget to see it here.
            </p>
            <Link
              to="/build"
              className="mt-6 inline-flex h-12 items-center gap-2 rounded-xl bg-primary px-6 text-sm font-bold text-primary-foreground shadow-sm transition-transform hover:-translate-y-0.5 active:scale-[0.97]"
            >
              Build a widget <ArrowUpRight className="size-4" />
            </Link>
          </div>
        )}

        {!isLoading && !error && widgets.length > 0 && (
          <div className="overflow-x-auto [mask-image:linear-gradient(to_right,black_calc(100%-2rem),transparent)] sm:[mask-image:none]">
            <table className="w-full min-w-[640px] text-left border-collapse sm:min-w-0">
              <thead>
                <tr className="border-b border-border text-[11px] uppercase tracking-widest text-muted-foreground font-bold">
                  <th className="pb-4 pr-6">Widget</th>
                  <th className="pb-4 px-6">Type</th>
                  <th className="pb-4 px-6">Status</th>
                  <th className="pb-4 px-6 text-right">Leads</th>
                  <th className="pb-4 px-6 text-right">Created</th>
                  <th className="pb-4 pl-6 text-right">Actions</th>
                </tr>
              </thead>
              <motion.tbody
                initial="hidden"
                animate="visible"
                variants={{ visible: { transition: { staggerChildren: 0.05 } } }}
                className="font-medium"
              >
                {widgets.map((w) => (
                  <motion.tr
                    key={w.id}
                    variants={{
                      hidden: { opacity: 0, y: 12 },
                      visible: { opacity: 1, y: 0, transition: { duration: 0.35 } },
                    }}
                    className="hover:bg-secondary/40 transition-colors group"
                  >
                    <td className="py-5 pr-6 rounded-l-2xl">
                      <div className="flex items-center gap-3">
                        <div className="size-2 rounded-full bg-primary" />
                        <div>
                          <div className="font-bold text-foreground group-hover:text-primary transition-colors">
                            {w.title}
                          </div>
                          <div className="text-xs text-muted-foreground font-mono mt-0.5">
                            {w.target_url}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="py-5 px-6">
                      <span className="text-sm text-foreground">{w.widget_type}</span>
                    </td>
                    <td className="py-5 px-6">
                      <span
                        className={`inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest px-3 py-1 rounded-full ${
                          w.status === "active"
                            ? "bg-success/10 text-success"
                            : w.status === "deployed"
                              ? "bg-info/10 text-info"
                              : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {w.deployment_url ? "Live" : w.status}
                      </span>
                    </td>
                    <td className="py-5 px-6 font-mono font-bold text-foreground text-right">
                      {w.leads_count}
                    </td>
                    <td className="py-5 px-6 text-right text-sm text-muted-foreground">
                      {new Date(w.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-5 pl-6 text-right rounded-r-2xl">
                      <div className="flex items-center justify-end gap-2">
                        {w.deployment_url && (
                          <a
                            href={w.deployment_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="grid size-8 place-items-center rounded-lg border border-border text-muted-foreground hover:text-foreground hover:border-foreground/40 transition-colors"
                            aria-label="Open widget"
                          >
                            <Eye className="size-4" />
                          </a>
                        )}
                        <button
                          type="button"
                          onClick={() => deploy.mutate(w.id)}
                          disabled={deploy.isPending}
                          className="grid size-8 place-items-center rounded-lg border border-border text-muted-foreground hover:text-foreground hover:border-foreground/40 transition-colors disabled:opacity-50"
                          aria-label="Redeploy"
                        >
                          <RefreshCw className={`size-4 ${deploy.isPending ? "animate-spin" : ""}`} />
                        </button>
                        <Link
                          to="/dashboard/widgets/$widgetId"
                          params={{ widgetId: w.id }}
                          className="grid size-8 place-items-center rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                          aria-label="View details"
                        >
                          <ArrowUpRight className="size-4" />
                        </Link>
                      </div>
                    </td>
                  </motion.tr>
                ))}
              </motion.tbody>
            </table>
          </div>
        )}
      </PageShell>
    </AppShell>
  );
}
