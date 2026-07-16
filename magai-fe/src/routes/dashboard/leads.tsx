import { createFileRoute, Link } from "@tanstack/react-router";
import { motion } from "framer-motion";
import {
  Users,
  Download,
  ArrowUpRight,
  Loader2,
} from "lucide-react";
import { AppShell } from "@/components/magnitai/AppShell";
import { PageShell } from "@/components/magnitai/ui/PageShell";
import { SectionIntro } from "@/components/magnitai/ui/SectionIntro";
import { useWidgets, useAllLeads } from "@/lib/api";
import { DashboardNav } from "@/components/magnitai/DashboardNav";

export const Route = createFileRoute("/dashboard/leads")({
  head: () => ({ meta: [{ title: "Leads · Magnitai" }] }),
  component: DashboardLeads,
});

function DashboardLeads() {
  const { data: widgetsData } = useWidgets();
  const widgetIds = (widgetsData?.widgets ?? []).map((w) => w.id);
  const { data: leads, isLoading } = useAllLeads(widgetIds);
  const widgetMap = new Map(
    (widgetsData?.widgets ?? []).map((w) => [w.id, w]),
  );
  const allLeads = leads ?? [];

  const exportCsv = () => {
    const header = "Email,Name,Score,Widget,Date";
    const rows = allLeads.map((l) => {
      const w = widgetMap.get(l.widget_id);
      return `${l.email},${l.name || ""},${l.score ?? ""},${w?.title || l.widget_id},${new Date(l.created_at).toISOString()}`;
    });
    const blob = new Blob([[header, ...rows].join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `magnitai-leads-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <AppShell activeSection="dashboard">
      <PageShell>
        <DashboardNav />
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-16">
          <SectionIntro
            eyebrow="Lead Management"
            heading={<>Captured <span className="hero-accent">leads</span></>}
            body="All leads collected across your Magnitai widgets."
            className="w-full"
          />
          <button
            type="button"
            onClick={exportCsv}
            disabled={allLeads.length === 0}
            className="h-10 px-5 rounded-full bg-card border border-border text-foreground font-bold text-sm hover:bg-secondary disabled:opacity-40 transition-colors flex items-center gap-2"
          >
            <Download className="size-4" /> Export CSV
          </button>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center py-32">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {!isLoading && allLeads.length === 0 && (
          <div className="flex flex-col items-center rounded-2xl border border-dashed border-border py-32 text-center">
            <Users className="size-10 text-muted-foreground/40 mb-4" />
            <h3 className="font-heading text-xl font-medium text-foreground">No leads yet</h3>
            <p className="mt-2 max-w-sm text-sm font-medium text-muted-foreground">
              Leads will appear here once your widgets start collecting them.
            </p>
          </div>
        )}

        {!isLoading && allLeads.length > 0 && (
          <div className="overflow-x-auto [mask-image:linear-gradient(to_right,black_calc(100%-2rem),transparent)] sm:[mask-image:none]">
            <table className="w-full min-w-[640px] text-left border-collapse sm:min-w-0">
              <thead>
                <tr className="border-b border-border text-[11px] uppercase tracking-widest text-muted-foreground font-bold">
                  <th className="pb-4 pr-6">Email</th>
                  <th className="pb-4 px-6">Name</th>
                  <th className="pb-4 px-6">Score</th>
                  <th className="pb-4 px-6">Widget</th>
                  <th className="pb-4 pl-6 text-right">Captured</th>
                </tr>
              </thead>
              <motion.tbody
                initial="hidden"
                animate="visible"
                variants={{ visible: { transition: { staggerChildren: 0.03 } } }}
                className="font-medium"
              >
                {allLeads.map((lead) => {
                  const w = widgetMap.get(lead.widget_id);
                  return (
                    <motion.tr
                      key={lead.id}
                      variants={{
                        hidden: { opacity: 0, y: 8 },
                        visible: { opacity: 1, y: 0, transition: { duration: 0.3 } },
                      }}
                      className="hover:bg-secondary/40 transition-colors group"
                    >
                      <td className="py-4 pr-6 rounded-l-2xl">
                        <div className="flex items-center gap-3">
                          <div className="size-8 rounded-full bg-primary/10 flex items-center justify-center text-xs font-bold text-primary">
                            {(lead.name || lead.email)[0].toUpperCase()}
                          </div>
                          <div>
                            <div className="font-semibold text-foreground text-sm">
                              {lead.email}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="py-4 px-6 text-sm text-foreground">
                        {lead.name || <span className="text-muted-foreground/60">—</span>}
                      </td>
                      <td className="py-4 px-6">
                        {lead.score != null ? (
                          <span className="font-mono font-bold text-sm">{lead.score}</span>
                        ) : (
                          <span className="text-muted-foreground/60">—</span>
                        )}
                      </td>
                      <td className="py-4 px-6">
                        <Link
                          to="/dashboard/widgets/$widgetId"
                          params={{ widgetId: lead.widget_id }}
                          className="flex items-center gap-1.5 text-sm font-semibold text-primary hover:underline"
                        >
                          {w?.title || lead.widget_id.slice(0, 8)}
                          <ArrowUpRight className="size-3" />
                        </Link>
                      </td>
                      <td className="py-4 pl-6 text-right text-sm text-muted-foreground rounded-r-2xl">
                        {new Date(lead.created_at).toLocaleDateString()}
                      </td>
                    </motion.tr>
                  );
                })}
              </motion.tbody>
            </table>
          </div>
        )}
      </PageShell>
    </AppShell>
  );
}
