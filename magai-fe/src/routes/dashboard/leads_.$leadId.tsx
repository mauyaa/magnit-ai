import { createFileRoute, Link } from "@tanstack/react-router";
import {
  AlertCircle,
  Check,
  Clock,
  Loader2,
  Mail,
  MousePointerClick,
  Plus,
  Send,
  Sparkles,
  StickyNote,
  Trash2,
  Trophy,
  X,
} from "lucide-react";
import { useState } from "react";

import { RequireAuth } from "@/components/magnitai/RequireAuth";
import { PageHeader } from "@/components/magnitai/shell/PageHeader";
import { WorkspaceShell } from "@/components/magnitai/shell/WorkspaceShell";
import {
  useAddLeadNote,
  useDeleteLeadNote,
  useLeadDetail,
  useUpdateLead,
  type LeadStatus,
  type TimelineEntry,
} from "@/lib/api";
import { PlanGate } from "@/lib/plan";

export const Route = createFileRoute("/dashboard/leads_/$leadId")({
  head: () => ({ meta: [{ title: "Lead · Magnitai" }] }),
  component: () => (
    <RequireAuth>
      <LeadDetailScreen />
    </RequireAuth>
  ),
});

const STATUSES: Array<{ id: LeadStatus; label: string }> = [
  { id: "new", label: "New" },
  { id: "contacted", label: "Contacted" },
  { id: "qualified", label: "Qualified" },
  { id: "won", label: "Won" },
  { id: "lost", label: "Lost" },
];

/** One icon per kind of event, so the column can be scanned without reading. */
const TIMELINE_ICONS: Record<string, typeof Mail> = {
  captured: Mail,
  scored: Trophy,
  started: Clock,
  result: Sparkles,
  cta: MousePointerClick,
  delivered: Send,
  contacted: Check,
  note: StickyNote,
};

/**
 * A visitor's answer, as they gave it.
 *
 * A yes/no question is stored as a boolean, and `String(true)` puts the word
 * "true" in front of someone reading their own lead's answers — which is the
 * database's vocabulary, not theirs.
 */
function answerText(value: unknown): string {
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) return value.map(answerText).join(", ");
  return String(value);
}

function TimelineRow({ entry }: { entry: TimelineEntry }) {
  const Icon = TIMELINE_ICONS[entry.kind] ?? Clock;
  const failed = entry.tone === "failed";

  return (
    <li className="relative flex gap-3 pb-5 last:pb-0">
      {/* The connecting rule, drawn behind the icons rather than as a border on
          each row, so it stops cleanly at the final entry. */}
      <span
        className="absolute left-[0.9375rem] top-8 bottom-0 w-px bg-border last:hidden"
        aria-hidden="true"
      />
      <span
        className={`relative z-10 grid size-8 shrink-0 place-items-center rounded-full ${
          failed ? "bg-destructive/10 text-destructive" : "bg-secondary text-foreground"
        }`}
      >
        <Icon className="size-4" aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1 pt-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5">
          <p className="text-sm font-medium text-foreground">{entry.title}</p>
          <time
            dateTime={entry.occurred_at}
            className="text-xs text-muted-foreground"
            title={new Date(entry.occurred_at).toLocaleString()}
          >
            {new Date(entry.occurred_at).toLocaleString(undefined, {
              month: "short",
              day: "numeric",
              hour: "numeric",
              minute: "2-digit",
            })}
          </time>
        </div>
        <p
          className={`mt-0.5 text-sm leading-6 ${
            failed ? "text-destructive" : "text-muted-foreground"
          }`}
        >
          {entry.detail}
        </p>
      </div>
    </li>
  );
}

function LeadDetailScreen() {
  const { leadId } = Route.useParams();
  const { data, isLoading, error } = useLeadDetail(leadId);
  const update = useUpdateLead();
  const addNote = useAddLeadNote();
  const deleteNote = useDeleteLeadNote();
  const [noteBody, setNoteBody] = useState("");
  const [tagDraft, setTagDraft] = useState("");

  if (isLoading) {
    return (
      <WorkspaceShell breadcrumb={[{ label: "Leads", to: "/dashboard/leads" }, { label: "Lead" }]}>
        <div className="flex justify-center py-32">
          <Loader2 className="size-5 animate-spin text-muted-foreground" aria-label="Loading" />
        </div>
      </WorkspaceShell>
    );
  }

  if (error || !data) {
    return (
      <WorkspaceShell breadcrumb={[{ label: "Leads", to: "/dashboard/leads" }, { label: "Lead" }]}>
        <div className="surface mx-auto max-w-md px-6 py-14 text-center">
          <p className="font-medium text-foreground">We couldn't find that lead.</p>
          <Link to="/dashboard/leads" className="btn btn-secondary mt-5 h-9 text-sm">
            Back to leads
          </Link>
        </div>
      </WorkspaceShell>
    );
  }

  const { lead } = data;
  const tags = lead.tags ?? [];

  const addTag = () => {
    const value = tagDraft.trim();
    if (!value || tags.length >= 12) return;
    update.mutate({ leadId, tags: [...tags, value] });
    setTagDraft("");
  };

  return (
    <WorkspaceShell
      breadcrumb={[
        { label: "Leads", to: "/dashboard/leads" },
        { label: lead.name || "Lead details" },
      ]}
    >
      <PageHeader
        title={lead.name || lead.email}
        meta={
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
            <a href={`mailto:${lead.email}`} className="text-foreground hover:underline">
              {lead.email}
            </a>
            <span>
              from{" "}
              <Link
                to="/dashboard/widgets/$widgetId"
                params={{ widgetId: data.widget_id }}
                className="hover:text-foreground hover:underline"
              >
                {data.widget_title}
              </Link>
            </span>
          </div>
        }
        actions={
          <a href={`mailto:${lead.email}`} className="btn btn-primary h-9 text-sm">
            <Mail className="size-4" aria-hidden="true" />
            Email them
          </a>
        }
      />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-4">
          <section className="surface p-5">
            <h2 className="text-base font-medium text-foreground">Activity</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Everything that happened, newest first.
            </p>
            <ul className="mt-5">
              {data.timeline.map((entry, index) => (
                <TimelineRow key={`${entry.kind}-${entry.occurred_at}-${index}`} entry={entry} />
              ))}
            </ul>
          </section>

          {lead.answers && Object.keys(lead.answers).length > 0 && (
            <section className="surface p-5">
              <h2 className="text-base font-medium text-foreground">What they answered</h2>
              <dl className="mt-4 divide-y divide-border">
                {Object.entries(lead.answers).map(([key, value]) => (
                  <div
                    key={key}
                    className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 py-2.5"
                  >
                    <dt className="text-sm capitalize text-muted-foreground">
                      {key.replace(/_/g, " ")}
                    </dt>
                    <dd className="text-sm font-medium text-foreground">{answerText(value)}</dd>
                  </div>
                ))}
              </dl>
            </section>
          )}

          <PlanGate feature="lead_pipeline" compact>
            <section className="surface p-5">
              <h2 className="text-base font-medium text-foreground">Notes</h2>

              <form
                className="mt-3 flex flex-col gap-2 sm:flex-row"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (!noteBody.trim()) return;
                  addNote.mutate({ leadId, body: noteBody }, { onSuccess: () => setNoteBody("") });
                }}
              >
                <input
                  value={noteBody}
                  maxLength={4000}
                  aria-label="Add a note"
                  placeholder="What did you discuss?"
                  onChange={(event) => setNoteBody(event.target.value)}
                  className="h-10 flex-1 rounded-lg border border-border bg-card px-3 text-sm text-foreground outline-none placeholder:text-n-400 focus:border-foreground/40"
                />
                <button
                  type="submit"
                  disabled={addNote.isPending || !noteBody.trim()}
                  className="btn btn-secondary h-10 shrink-0 text-sm"
                >
                  {addNote.isPending ? (
                    <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Plus className="size-4" aria-hidden="true" />
                  )}
                  Add note
                </button>
              </form>

              {data.notes.length === 0 ? (
                <p className="mt-4 text-sm text-muted-foreground">No notes yet.</p>
              ) : (
                <ul className="mt-4 divide-y divide-border">
                  {data.notes.map((note) => (
                    <li key={note.id} className="flex items-start gap-3 py-3">
                      <p className="min-w-0 flex-1 text-sm leading-6 text-foreground">
                        {note.body}
                      </p>
                      <time
                        dateTime={note.created_at}
                        className="shrink-0 pt-0.5 text-xs text-muted-foreground"
                      >
                        {new Date(note.created_at).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                        })}
                      </time>
                      <button
                        type="button"
                        onClick={() => deleteNote.mutate({ leadId, noteId: note.id })}
                        className="btn btn-ghost size-7 shrink-0 px-0"
                        aria-label="Delete note"
                      >
                        <Trash2 className="size-3.5" aria-hidden="true" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </PlanGate>
        </div>

        <aside className="space-y-4 lg:sticky lg:top-24">
          <section className="surface p-5">
            <h2 className="text-sm font-medium text-foreground">Score</h2>
            {lead.score === null ? (
              <p className="mt-2 text-sm text-muted-foreground">This tool doesn't score.</p>
            ) : (
              <>
                <p className="tabular mt-1 text-3xl font-medium tracking-[-0.03em] text-foreground">
                  {lead.score}
                  <span className="text-lg text-muted-foreground"> / 100</span>
                </p>
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-n-100">
                  <span
                    className="block h-full rounded-full bg-chart-lead"
                    style={{ width: `${Math.max(3, Math.min(100, lead.score))}%` }}
                  />
                </div>
                {lead.result_key && (
                  <p className="mt-2.5 text-sm text-muted-foreground">
                    Result: <span className="text-foreground">{lead.result_key}</span>
                  </p>
                )}
              </>
            )}
          </section>

          <PlanGate feature="lead_pipeline" compact>
            <section className="surface p-5">
              <h2 className="text-sm font-medium text-foreground">Status</h2>
              <div className="mt-3 grid gap-1.5">
                {STATUSES.map((status) => {
                  const active = lead.status === status.id;
                  return (
                    <button
                      key={status.id}
                      type="button"
                      aria-pressed={active}
                      disabled={update.isPending}
                      onClick={() => update.mutate({ leadId, status: status.id })}
                      className={`flex h-9 items-center justify-between rounded-lg border px-3 text-sm transition-colors ${
                        active
                          ? "border-foreground bg-foreground text-background"
                          : "border-border text-foreground hover:border-foreground/30"
                      }`}
                    >
                      {status.label}
                      {active && <Check className="size-3.5" aria-hidden="true" />}
                    </button>
                  );
                })}
              </div>
              {update.isError && (
                <p role="alert" className="mt-2 flex items-start gap-1.5 text-xs text-destructive">
                  <AlertCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                  {(update.error as Error).message}
                </p>
              )}
            </section>

            <section className="surface p-5">
              <h2 className="text-sm font-medium text-foreground">Tags</h2>
              {tags.length > 0 && (
                <ul className="mt-3 flex flex-wrap gap-1.5">
                  {tags.map((tag) => (
                    <li
                      key={tag}
                      className="flex items-center gap-1 rounded-full bg-secondary py-1 pl-2.5 pr-1 text-xs text-foreground"
                    >
                      {tag}
                      <button
                        type="button"
                        onClick={() =>
                          update.mutate({ leadId, tags: tags.filter((item) => item !== tag) })
                        }
                        className="grid size-4 place-items-center rounded-full hover:bg-n-200"
                        aria-label={`Remove tag ${tag}`}
                      >
                        <X className="size-3" aria-hidden="true" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <form
                className="mt-3 flex gap-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  addTag();
                }}
              >
                <input
                  value={tagDraft}
                  maxLength={40}
                  aria-label="Add a tag"
                  placeholder="high intent"
                  onChange={(event) => setTagDraft(event.target.value)}
                  className="h-9 min-w-0 flex-1 rounded-lg border border-border bg-card px-2.5 text-sm text-foreground outline-none placeholder:text-n-400 focus:border-foreground/40"
                />
                <button
                  type="submit"
                  disabled={!tagDraft.trim() || tags.length >= 12}
                  className="btn btn-secondary h-9 shrink-0 px-3 text-sm"
                >
                  Add
                </button>
              </form>
            </section>
          </PlanGate>
        </aside>
      </div>
    </WorkspaceShell>
  );
}
