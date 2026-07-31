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

/** One enclosure, whatever it has to say — see the note in DeltaBadge. */
const PILL = "inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium";

function DeltaBadge({ percent, higherIsBetter = true }: Delta) {
  if (percent === null || !Number.isFinite(percent)) {
    /*
     * Still a pill. "No prior period" as loose text meant the slot under the
     * number changed shape depending on whether a comparison happened to
     * exist, so a row of four cards had two different silhouettes for no
     * reason a customer could see. Same enclosure, quieter tone.
     */
    return <span className={`${PILL} bg-secondary text-muted-foreground`}>No prior period</span>;
  }

  const rounded = Math.round(percent * 10) / 10;
  const flat = Math.abs(rounded) < 0.1;
  const good = flat ? null : rounded > 0 === higherIsBetter;
  const Icon = flat ? Minus : rounded > 0 ? TrendingUp : TrendingDown;

  /*
   * A pill, not loose text beside a number.
   *
   * The change was previously an icon and a percentage sitting directly on the
   * card, which reads as another sentence — so the eye had to parse it to find
   * out it was the important part. Giving it an enclosure and a tint makes it a
   * single object the eye can take in without reading: green means up, red
   * means down, grey means there is nothing to compare against.
   */
  const tone =
    good === null
      ? "bg-secondary text-muted-foreground"
      : good
        ? "bg-success/10 text-success"
        : "bg-destructive/10 text-destructive";

  return (
    <span className={`${PILL} ${tone}`}>
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
    /*
     * The number is the card.
     *
     * It used to be 30px against a 14px label — barely twice its size — on a
     * card over 300px wide, so a screen of metrics read as a screen of
     * sentences with figures in them. Nothing led, and the eye had to work out
     * what to look at first every single time.
     *
     * The label steps back and the value steps forward until the ratio does
     * the ranking on its own. The extra padding is part of the same move: a
     * number this size needs room around it or the card feels crowded rather
     * than confident.
     */
    <article className="surface p-5 sm:p-6">
      <h3 className="text-xs font-medium text-muted-foreground">{label}</h3>
      <p className="tabular mt-2 text-4xl font-semibold leading-none tracking-[-0.045em] text-foreground">
        {value}
      </p>
      {/*
       * One rule for the line under the number: the first thing in it is a
       * pill, and anything after it is quiet text.
       *
       * With a comparison that reads as "+12%  vs last month" — the change is
       * the object, the period is the caption. Without one, the caption is all
       * there is, so it takes the pill's place rather than sitting where the
       * pill would have been as loose text. A row of four cards previously had
       * three different silhouettes here depending on which data happened to
       * exist, which is the kind of difference nobody chooses and everybody
       * feels.
       */}
      <div className="mt-3.5 flex flex-wrap items-center gap-2">
        {delta ? (
          <>
            <DeltaBadge {...delta} />
            {note ? <span className="text-xs text-muted-foreground">{note}</span> : null}
          </>
        ) : note ? (
          <span className={`${PILL} bg-secondary text-muted-foreground`}>{note}</span>
        ) : null}
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
