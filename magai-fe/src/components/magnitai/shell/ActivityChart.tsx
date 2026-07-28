import { useState } from "react";

import type { PortfolioAnalytics } from "@/lib/api";

/**
 * Daily activity, as a part-to-whole over time.
 *
 * The previous chart drew starts and leads as two independent bars in a group,
 * which misstates the relationship: a lead can only come from a start, so they
 * are not peers — leads are the converted share of the total. Stacking them
 * makes the bar height the number of people who began and the coloured foot the
 * number who finished, so the conversion rate is legible as a proportion
 * without anyone computing it.
 *
 * It also had no y-axis, no gridlines and no tooltip, so a bar's height could
 * be compared with its neighbour and with nothing else — you could see that
 * Tuesday was taller than Monday but never that it was four.
 */

interface Bucket {
  label: string;
  full: string;
  starts: number;
  leads: number;
}

/**
 * Above about a month, one bar per day is thinner than the gap between bars.
 * Weekly buckets keep the mark readable instead of shrinking the type to fit.
 */
function bucketize(daily: PortfolioAnalytics["daily"]): { buckets: Bucket[]; grain: string } {
  const format = (iso: string) =>
    new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" });

  if (daily.length <= 31) {
    return {
      grain: "day",
      buckets: daily.map((day) => ({
        label: format(day.date),
        full: format(day.date),
        starts: day.starts,
        leads: day.leads,
      })),
    };
  }

  const buckets: Bucket[] = [];
  for (let i = 0; i < daily.length; i += 7) {
    const week = daily.slice(i, i + 7);
    buckets.push({
      label: format(week[0].date),
      full: `${format(week[0].date)} – ${format(week[week.length - 1].date)}`,
      starts: week.reduce((total, day) => total + day.starts, 0),
      leads: week.reduce((total, day) => total + day.leads, 0),
    });
  }
  return { grain: "week", buckets };
}

/**
 * Round the axis top up to a number a person would have chosen.
 *
 * Two constraints, both learned from getting it wrong: the ceiling has to be
 * close to the peak (a fixed floor of 4 against a peak of 2 spends half the
 * plot on white space and makes real movement look flat), and the midpoint has
 * to be a whole number, because these are counts — an axis labelled 0 / 2.5 / 5
 * is offering to show you two and a half leads.
 */
function niceCeiling(value: number): number {
  // Small counts: the next even number, so the midpoint is an integer.
  if (value <= 10) return Math.max(2, Math.ceil(value / 2) * 2);

  const magnitude = 10 ** Math.floor(Math.log10(value));
  for (const step of [1, 2, 5, 10]) {
    const candidate = step * magnitude;
    if (candidate >= value) return candidate;
  }
  return 10 * magnitude;
}

export function ActivityChart({ daily }: { daily: PortfolioAnalytics["daily"] }) {
  const [hovered, setHovered] = useState<number | null>(null);
  const { buckets, grain } = bucketize(daily);

  const total = buckets.reduce((sum, b) => sum + b.starts + b.leads, 0);
  // A lead can be recorded on a day after the visit that produced it started,
  // so leads can exceed starts in a bucket. The bar has to be tall enough to
  // hold both rather than clipping the part that does not fit.
  const peak = Math.max(...buckets.map((b) => Math.max(b.starts, b.leads)), 1);
  const ceiling = niceCeiling(peak);
  const ticks = [0, ceiling / 2, ceiling];

  if (total === 0) {
    return (
      <div className="flex flex-1 items-center justify-center rounded-lg border border-dashed border-border bg-n-50 px-6 py-16 text-center">
        <div>
          <p className="text-sm font-medium text-foreground">No activity in this period</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Numbers appear here as soon as a visitor opens one of your tools.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex flex-1 gap-3">
        {/* Y axis. Three ticks: nobody reads more, and each one costs a gridline. */}
        <div className="flex w-8 shrink-0 flex-col justify-between py-px text-right">
          {[...ticks].reverse().map((tick) => (
            <span key={tick} className="tabular text-[11px] leading-none text-muted-foreground">
              {tick}
            </span>
          ))}
        </div>

        <div className="relative min-h-[13rem] flex-1">
          {/* Gridlines sit behind the marks and are deliberately faint. */}
          <div aria-hidden="true" className="absolute inset-0 flex flex-col justify-between">
            {ticks.map((tick) => (
              <span key={tick} className="block h-px w-full bg-border" />
            ))}
          </div>

          <div className="absolute inset-0 flex items-end gap-[2px]">
            {buckets.map((bucket, index) => {
              const leadHeight = (bucket.leads / ceiling) * 100;
              const restHeight = (Math.max(0, bucket.starts - bucket.leads) / ceiling) * 100;
              const active = hovered === index;

              return (
                <div
                  key={bucket.label + index}
                  className="group relative flex h-full min-w-0 flex-1 flex-col justify-end"
                  onMouseEnter={() => setHovered(index)}
                  onMouseLeave={() => setHovered(null)}
                >
                  {/* Hit target spans the full column height, not just the bar. */}
                  <span className="absolute inset-0" aria-hidden="true" />

                  {restHeight > 0 && (
                    <span
                      className="w-full rounded-t-[3px] bg-chart-rest transition-opacity"
                      style={{
                        height: `${restHeight}%`,
                        opacity: hovered === null || active ? 1 : 0.45,
                      }}
                    />
                  )}
                  {bucket.leads > 0 && (
                    <span
                      className={`w-full bg-chart-lead transition-opacity ${
                        restHeight > 0 ? "mt-[2px]" : "rounded-t-[3px]"
                      }`}
                      style={{
                        height: `${leadHeight}%`,
                        opacity: hovered === null || active ? 1 : 0.45,
                      }}
                    />
                  )}

                  {active && (
                    <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-2 w-max -translate-x-1/2 rounded-lg border border-border bg-card px-3 py-2 shadow-float">
                      <p className="text-xs font-medium text-foreground">{bucket.full}</p>
                      <dl className="mt-1.5 space-y-0.5">
                        <div className="flex items-center gap-2 text-xs">
                          <span className="size-2 shrink-0 rounded-[2px] bg-chart-rest" />
                          <dt className="text-muted-foreground">Started</dt>
                          <dd className="tabular ml-auto font-medium text-foreground">
                            {bucket.starts}
                          </dd>
                        </div>
                        <div className="flex items-center gap-2 text-xs">
                          <span className="size-2 shrink-0 rounded-[2px] bg-chart-lead" />
                          <dt className="text-muted-foreground">Leads</dt>
                          <dd className="tabular ml-auto font-medium text-foreground">
                            {bucket.leads}
                          </dd>
                        </div>
                      </dl>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="mt-2 flex items-center justify-between gap-4 pl-11">
        <span className="text-[11px] text-muted-foreground">{buckets[0]?.label}</span>
        <span className="text-[11px] text-muted-foreground">
          {buckets[buckets.length - 1]?.label}
        </span>
      </div>

      {/* Two series, so a legend is not optional. */}
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border pl-11 pt-3">
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="size-2 rounded-[2px] bg-chart-lead" aria-hidden="true" />
          Became a lead
        </span>
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="size-2 rounded-[2px] bg-chart-rest" aria-hidden="true" />
          Started, didn't convert
        </span>
        <span className="ml-auto text-xs text-muted-foreground">by {grain}</span>
      </div>
    </div>
  );
}
