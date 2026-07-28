import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowUpDown, Download, Loader2, Search, Users } from "lucide-react";
import { useMemo, useState } from "react";

import { RequireAuth } from "@/components/magnitai/RequireAuth";
import { PageHeader } from "@/components/magnitai/shell/PageHeader";
import { WorkspaceShell } from "@/components/magnitai/shell/WorkspaceShell";
import { useAllLeads, useWidgets, type LeadData, type WidgetData } from "@/lib/api";
import { PlanGate } from "@/lib/plan";

export const Route = createFileRoute("/dashboard/leads")({
  head: () => ({ meta: [{ title: "Leads · Magnitai" }] }),
  component: () => (
    <RequireAuth>
      <DashboardLeads />
    </RequireAuth>
  ),
});

/** 25 rows is the researched default: enough to scan, short enough to render. */
const PAGE_SIZE = 25;

type SortKey = "created_at" | "score" | "email";

/**
 * Deliberately not sticky.
 *
 * A sticky header cannot work here and be honest about it: the table needs
 * `overflow-x-auto` so a 42rem-wide grid can scroll sideways on a phone, and a
 * container with `overflow-x: auto` becomes the sticky *scrollport* for
 * everything inside it. Its own box never scrolls vertically, so `top: 4rem`
 * offsets the header 64px down from the container's top edge and parks it on
 * top of the first two rows — which is exactly what it did.
 *
 * The alternatives are a nested vertically-scrolling region (a scrollbar inside
 * a scrolling page) or dropping horizontal scroll on small screens. Neither is
 * worth it when pagination already caps the page at 25 rows, which is short
 * enough that the header is rarely off screen.
 *
 * The rule under the header is an inset shadow rather than a border because the
 * table is `border-collapse: separate`.
 */
const HEAD_CELL = "bg-card px-4 py-0 font-normal shadow-[inset_0_-1px_0_var(--border)]";

/** "3 days ago" beats "22/07/2026" when the question is really "is this warm?". */
function relativeDay(iso: string): string {
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days} days ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function csvCell(value: string): string {
  return /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

/**
 * A score is a number between 0 and 100, so it can be shown as one.
 *
 * It was rendered as bare digits in a column of bare digits, which makes
 * "82" and "55" cost the same amount of attention. A bar plus the figure lets
 * the column be skimmed for the warm ones without reading any of it.
 */
function ScoreCell({ score }: { score: number | null }) {
  if (score === null) return <span className="text-n-400">—</span>;
  return (
    <div className="flex items-center gap-2">
      <span className="h-1.5 w-12 shrink-0 overflow-hidden rounded-full bg-n-100">
        <span
          className="block h-full rounded-full bg-chart-rest"
          style={{ width: `${Math.max(4, Math.min(100, score))}%` }}
        />
      </span>
      <span className="tabular text-sm text-foreground">{score}</span>
    </div>
  );
}

/**
 * Where a lead has got to, as a word and a colour rather than a colour alone.
 *
 * "New" is deliberately the quietest: a table where every untouched row shouts
 * is a table nobody can triage.
 */
function StatusChip({ status }: { status: LeadData["status"] }) {
  const style = {
    new: "bg-n-100 text-n-600",
    contacted: "bg-info/12 text-info",
    qualified: "bg-brand-wash text-brand-solid",
    won: "bg-success/12 text-success",
    lost: "bg-n-100 text-n-500 line-through",
  }[status];

  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${style}`}>
      {status}
    </span>
  );
}

function SortableHeader({
  label,
  sortKey,
  active,
  direction,
  onSort,
  align = "left",
}: {
  label: string;
  sortKey: SortKey;
  active: boolean;
  direction: "asc" | "desc";
  onSort: (key: SortKey) => void;
  align?: "left" | "right";
}) {
  return (
    <th
      scope="col"
      className={`${HEAD_CELL} ${align === "right" ? "text-right" : "text-left"}`}
      aria-sort={active ? (direction === "asc" ? "ascending" : "descending") : "none"}
    >
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className={`inline-flex h-9 items-center gap-1.5 text-xs transition-colors hover:text-foreground ${
          active ? "font-medium text-foreground" : "text-muted-foreground"
        }`}
      >
        {label}
        <ArrowUpDown className="size-3" aria-hidden="true" />
      </button>
    </th>
  );
}

/** Stable empty array, so `?? []` cannot hand out a fresh identity per render. */
const NO_WIDGETS: WidgetData[] = [];

function DashboardLeads() {
  const { data: widgetsData } = useWidgets();
  // Memoised because it is a dependency of `widgetMap` below; `?? []` allocates
  // a new array every render, which defeats every memo downstream of it.
  const widgets = useMemo(() => widgetsData?.widgets ?? NO_WIDGETS, [widgetsData]);
  const { data: leads, isLoading } = useAllLeads(widgets.map((w) => w.id));

  const [query, setQuery] = useState("");
  const [toolFilter, setToolFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [direction, setDirection] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(0);

  const widgetMap = useMemo(() => new Map(widgets.map((w) => [w.id, w])), [widgets]);
  const allLeads = useMemo(() => leads ?? [], [leads]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = allLeads.filter((lead) => {
      if (toolFilter !== "all" && lead.widget_id !== toolFilter) return false;
      if (!needle) return true;
      return (
        lead.email.toLowerCase().includes(needle) ||
        (lead.name ?? "").toLowerCase().includes(needle)
      );
    });

    const compare = (a: LeadData, b: LeadData) => {
      if (sortKey === "score") return (a.score ?? -1) - (b.score ?? -1);
      if (sortKey === "email") return a.email.localeCompare(b.email);
      return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
    };

    return [...filtered].sort((a, b) => (direction === "asc" ? compare(a, b) : compare(b, a)));
  }, [allLeads, query, toolFilter, sortKey, direction]);

  const pageCount = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const rows = visible.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setDirection((current) => (current === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      // Text reads naturally A–Z; dates and scores are most useful biggest-first.
      setDirection(key === "email" ? "asc" : "desc");
    }
    setPage(0);
  };

  // Exports what is on screen, not the whole table: a filter you can see but
  // that the download silently ignores is a trap.
  const exportCsv = () => {
    const rowsOut = visible.map((lead) =>
      [
        lead.email,
        lead.name || "",
        lead.score ?? "",
        widgetMap.get(lead.widget_id)?.title || lead.widget_id,
        new Date(lead.created_at).toISOString(),
      ]
        .map((value) => csvCell(String(value)))
        .join(","),
    );
    const blob = new Blob([["Email,Name,Score,Tool,Captured", ...rowsOut].join("\n")], {
      type: "text/csv",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `magnitai-leads-${new Date().toISOString().slice(0, 10)}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading) {
    return (
      <WorkspaceShell breadcrumb={[{ label: "Leads" }]}>
        <div className="flex justify-center py-32">
          <Loader2 className="size-5 animate-spin text-muted-foreground" aria-label="Loading" />
        </div>
      </WorkspaceShell>
    );
  }

  return (
    <WorkspaceShell breadcrumb={[{ label: "Leads" }]}>
      <PageHeader
        title="Leads"
        description={
          allLeads.length === 0
            ? "People who leave their details in one of your tools land here."
            : `${allLeads.length} ${allLeads.length === 1 ? "person has" : "people have"} left their details.`
        }
        actions={
          allLeads.length > 0 ? (
            <PlanGate
              feature="csv_export"
              fallback={
                <span className="text-xs text-muted-foreground">
                  Exporting is available from Studio
                </span>
              }
            >
              <button type="button" onClick={exportCsv} className="btn btn-secondary h-9 text-sm">
                <Download className="size-4" aria-hidden="true" />
                Export CSV
              </button>
            </PlanGate>
          ) : undefined
        }
      />

      {allLeads.length === 0 ? (
        <div className="surface mx-auto max-w-md px-6 py-14 text-center">
          <span className="mx-auto grid size-11 place-items-center rounded-xl bg-secondary">
            <Users className="size-5 text-foreground" aria-hidden="true" />
          </span>
          <h2 className="mt-4 text-lg font-medium text-foreground">No leads yet</h2>
          <p className="mx-auto mt-1.5 max-w-xs text-sm leading-6 text-muted-foreground">
            Once a tool is embedded and someone completes it, their details appear here.
          </p>
          <Link to="/dashboard" className="btn btn-secondary mt-6 h-9 text-sm">
            Back to your tools
          </Link>
        </div>
      ) : (
        <div className="surface overflow-hidden">
          {/* Toolbar: search, filter, and the result count, above the data it acts on. */}
          <div className="flex flex-col gap-3 border-b border-border p-3 sm:flex-row sm:items-center">
            <div className="relative flex-1 sm:max-w-xs">
              <Search
                className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-n-400"
                aria-hidden="true"
              />
              <input
                type="search"
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setPage(0);
                }}
                placeholder="Search name or email"
                aria-label="Search leads"
                className="h-9 w-full rounded-lg border border-border bg-card pl-8 pr-3 text-sm text-foreground outline-none placeholder:text-n-400 focus:border-foreground/40"
              />
            </div>

            <select
              value={toolFilter}
              onChange={(event) => {
                setToolFilter(event.target.value);
                setPage(0);
              }}
              aria-label="Filter by tool"
              className="h-9 rounded-lg border border-border bg-card px-2.5 text-sm text-foreground outline-none focus:border-foreground/40"
            >
              <option value="all">All tools</option>
              {widgets.map((widget) => (
                <option key={widget.id} value={widget.id}>
                  {widget.title}
                </option>
              ))}
            </select>

            <span className="text-xs text-muted-foreground sm:ml-auto">
              {visible.length === allLeads.length
                ? `${allLeads.length} leads`
                : `${visible.length} of ${allLeads.length}`}
            </span>
          </div>

          {visible.length === 0 ? (
            <p className="px-4 py-14 text-center text-sm text-muted-foreground">
              No leads match that search.
            </p>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[48rem] text-left">
                  <thead>
                    <tr>
                      <SortableHeader
                        label="Email"
                        sortKey="email"
                        active={sortKey === "email"}
                        direction={direction}
                        onSort={handleSort}
                      />
                      <th scope="col" className={`${HEAD_CELL} text-left text-xs`}>
                        <span className="inline-flex h-9 items-center text-muted-foreground">
                          Name
                        </span>
                      </th>
                      <th scope="col" className={`${HEAD_CELL} text-left text-xs`}>
                        <span className="inline-flex h-9 items-center text-muted-foreground">
                          Status
                        </span>
                      </th>
                      <SortableHeader
                        label="Score"
                        sortKey="score"
                        active={sortKey === "score"}
                        direction={direction}
                        onSort={handleSort}
                      />
                      <th scope="col" className={`${HEAD_CELL} text-left text-xs`}>
                        <span className="inline-flex h-9 items-center text-muted-foreground">
                          Tool
                        </span>
                      </th>
                      <SortableHeader
                        label="Captured"
                        sortKey="created_at"
                        active={sortKey === "created_at"}
                        direction={direction}
                        onSort={handleSort}
                        align="right"
                      />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {rows.map((lead) => (
                      <tr key={lead.id} className="transition-colors hover:bg-secondary/60">
                        <td className="px-4 py-3">
                          {/* The row's own link, not a mailto: opening the lead
                              is the common action; emailing them is one click
                              further in, from a screen that has their history. */}
                          <Link
                            to="/dashboard/leads/$leadId"
                            params={{ leadId: lead.id }}
                            className="text-sm font-medium text-foreground hover:underline"
                          >
                            {lead.email}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-sm text-foreground">
                          {lead.name || <span className="text-n-400">—</span>}
                        </td>
                        <td className="px-4 py-3">
                          <StatusChip status={lead.status} />
                        </td>
                        <td className="px-4 py-3">
                          <ScoreCell score={lead.score} />
                        </td>
                        <td className="px-4 py-3 text-sm">
                          <Link
                            to="/dashboard/widgets/$widgetId"
                            params={{ widgetId: lead.widget_id }}
                            className="text-muted-foreground hover:text-foreground hover:underline"
                          >
                            {widgetMap.get(lead.widget_id)?.title || lead.widget_id.slice(0, 8)}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-right text-sm text-muted-foreground">
                          {relativeDay(lead.created_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {pageCount > 1 && (
                <div className="flex items-center justify-between gap-4 border-t border-border px-4 py-3">
                  <span className="text-xs text-muted-foreground">
                    {safePage * PAGE_SIZE + 1}–
                    {Math.min((safePage + 1) * PAGE_SIZE, visible.length)} of {visible.length}
                  </span>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setPage((current) => Math.max(0, current - 1))}
                      disabled={safePage === 0}
                      className="btn btn-secondary h-8 px-3 text-sm"
                    >
                      Previous
                    </button>
                    <button
                      type="button"
                      onClick={() => setPage((current) => Math.min(pageCount - 1, current + 1))}
                      disabled={safePage >= pageCount - 1}
                      className="btn btn-secondary h-8 px-3 text-sm"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </WorkspaceShell>
  );
}
