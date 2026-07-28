import type { ReactNode } from "react";

/**
 * One page header for every workspace screen.
 *
 * Before this, four screens had four ideas of what a header is: Overview used a
 * mono eyebrow above a 48px domain name, Analytics used a marketing headline
 * ("See what converts."), Leads had no heading element at all — just a sentence
 * counting the rows — and a tool's own page used a text back-link. Titles
 * landed at four different heights, and the primary action landed in four
 * different places, which is most of what reads as "put down at random".
 *
 * `actions` is the only slot on the right, and pages pass at most one primary
 * button into it. The create action itself is not passed here at all: it lives
 * in the rail, where it is reachable from every screen instead of being
 * restated in each header.
 */
export function PageHeader({
  title,
  description,
  meta,
  actions,
}: {
  title: string;
  description?: ReactNode;
  /** A status line under the title — live/paused, last updated, counts. */
  meta?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-4 pb-6 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
      <div className="min-w-0">
        <h1 className="truncate text-[1.75rem] font-medium leading-tight tracking-[-0.025em] text-foreground">
          {title}
        </h1>
        {description && (
          <p className="mt-1.5 max-w-2xl text-sm leading-6 text-muted-foreground">{description}</p>
        )}
        {meta && <div className="mt-2.5">{meta}</div>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  );
}

/** A status dot paired with a word, because colour alone is not a status. */
export function StatusPill({
  tone,
  children,
}: {
  tone: "live" | "pending" | "attention" | "idle";
  children: ReactNode;
}) {
  const dot = {
    live: "bg-success",
    pending: "bg-warning",
    attention: "bg-destructive",
    idle: "bg-n-400",
  }[tone];

  return (
    <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
      <span className={`size-2 shrink-0 rounded-full ${dot}`} aria-hidden="true" />
      {children}
    </span>
  );
}
