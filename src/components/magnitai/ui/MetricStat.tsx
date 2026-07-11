import React from "react";
import { ArrowUpRight, type LucideIcon } from "lucide-react";

interface MetricStatProps {
  icon: LucideIcon;
  /** Tailwind color class for the icon, e.g. "text-primary" */
  iconColor?: string;
  /** Small eyebrow label above the value */
  subLabel: string;
  /** The big number/value to display */
  value: string;
  /** Description label below the value */
  label: string;
  /**
   * Optional badge text shown as a success pill below the value (e.g. "+14.2%").
   * When provided, an ArrowUpRight icon is prepended automatically.
   */
  badge?: string;
  /**
   * Controls value text size.
   * "sm" = text-3xl (compact sidebar use), "md" = text-4xl (dense grid cells),
   * "lg" = text-5xl (hero analytics cards). Defaults to "sm".
   */
  valueSize?: "sm" | "md" | "lg";
  /** "compact" wraps the cell in its own padded card. Defaults to "default" (no wrapper). */
  layout?: "default" | "compact";
  /** Extra classes on the wrapper — only applied when layout="compact". */
  className?: string;
}

const valueSizeClass: Record<NonNullable<MetricStatProps["valueSize"]>, string> = {
  sm: "text-3xl font-medium font-mono tracking-tighter text-foreground mb-1",
  md: "text-4xl font-medium font-mono tracking-tighter text-foreground mb-2",
  lg: "text-5xl font-medium font-mono tracking-tighter text-foreground mb-3",
};

/**
 * Icon + sub-label + large numeric value + footnote cell.
 * Replaces the near-identical metric renderers in TransparencyDashboard (sidebar)
 * and OwnerAnalyticsDashboard (top cards).
 */
export function MetricStat({
  icon: Icon,
  iconColor = "text-foreground",
  subLabel,
  value,
  label,
  badge,
  valueSize = "sm",
  layout = "default",
  className,
}: MetricStatProps) {
  const content = (
    <>
      <div className="flex items-center gap-2 mb-3">
        <Icon className={`size-4 ${iconColor}`} />
        <span className="eyebrow">{subLabel}</span>
      </div>
      <div className={valueSizeClass[valueSize]}>{value}</div>
      {badge ? (
        <div className="flex items-center gap-1.5 text-xs font-bold text-success bg-success/10 w-fit px-2.5 py-1 rounded-full">
          <ArrowUpRight className="size-3.5" />
          <span>{badge}</span>
        </div>
      ) : (
        <div className="text-xs font-bold text-muted-foreground">{label}</div>
      )}
    </>
  );

  if (layout === "compact") {
    return <div className={`flex flex-col rounded-2xl p-5 ${className ?? ""}`}>{content}</div>;
  }

  return <div className="flex flex-col">{content}</div>;
}
