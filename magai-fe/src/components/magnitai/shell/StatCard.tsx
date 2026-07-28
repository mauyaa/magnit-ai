import { Minus, TrendingDown, TrendingUp } from "lucide-react";
import type { ReactNode } from "react";

/**
 * One metric, one card, and — where a previous period exists — the change
 * against it.
 *
 * The old tiles carried a number and a sentence, which meant a visitor count
 * could double or halve and the screen looked identical either way. A KPI
 * without a comparison is a fact; with one it is information.
 *
 * They also arbitrarily painted the *first* card in the row ink-on-white while
 * the other three stayed white. Emphasis that does not track meaning is noise,
 * so the row is now uniform and the numbers do the ranking.
 */

export interface Delta {
  /** Change as a percentage. Null when the previous period was empty. */
  percent: number | null;
  /** True when a rise is good. Set false for metrics like drop-off. */
  higherIsBetter?: boolean;
}

function DeltaBadge({ percent, higherIsBetter = true }: Delta) {
  if (percent === null || !Number.isFinite(percent)) {
    return <span className="text-xs text-muted-foreground">No prior period</span>;
  }

  const rounded = Math.round(percent * 10) / 10;
  const flat = Math.abs(rounded) < 0.1;
  const good = flat ? null : rounded > 0 === higherIsBetter;
  const Icon = flat ? Minus : rounded > 0 ? TrendingUp : TrendingDown;

  return (
    <span
      className={`inline-flex items-center gap-1 text-xs font-medium ${
        good === null ? "text-muted-foreground" : good ? "text-success" : "text-destructive"
      }`}
    >
      <Icon className="size-3.5 shrink-0" aria-hidden="true" />
      <span className="tabular">{flat ? "0" : `${rounded > 0 ? "+" : ""}${rounded}`}%</span>
    </span>
  );
}

export function StatCard({
  label,
  value,
  delta,
  note,
}: {
  label: string;
  value: string;
  delta?: Delta;
  /** Shown when there is no delta to show — never both. */
  note?: string;
}) {
  return (
    <article className="surface p-4 sm:p-5">
      <h3 className="text-sm text-muted-foreground">{label}</h3>
      <p className="tabular mt-3 text-3xl font-medium tracking-[-0.03em] text-foreground">
        {value}
      </p>
      <div className="mt-2 flex items-center gap-2">
        {delta ? <DeltaBadge {...delta} /> : null}
        {delta && note ? <span className="text-xs text-muted-foreground">{note}</span> : null}
        {!delta && note ? <span className="text-xs text-muted-foreground">{note}</span> : null}
      </div>
    </article>
  );
}

/** Four across on desktop, two on tablet, one on phone — the KPI strip. */
export function StatRow({ children }: { children: ReactNode }) {
  return <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{children}</section>;
}

/**
 * Percentage change between two periods.
 *
 * Returns null rather than Infinity when the previous period was zero: "up
 * ∞%" from a standing start is not a fact anyone can act on, and rendering it
 * as a number implies a precision that isn't there.
 */
export function percentChange(current: number, previous: number): number | null {
  if (previous <= 0) return null;
  return ((current - previous) / previous) * 100;
}
