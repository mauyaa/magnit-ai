import React from "react";
import { motion } from "framer-motion";

interface GaugeStatProps {
  /** 0-100 */
  value: number;
  /** Big label under the ring, e.g. "100%" or "12ms" */
  displayValue: string;
  label: string;
  /** Tailwind color class for the progress arc, e.g. "text-primary". Defaults to "text-primary". */
  color?: string;
}

/**
 * Circular progress gauge — the "operational dial" pattern common on AI
 * infra/ops dashboards (system load, uptime, throughput), used here instead
 * of another flat number card so the health metric reads as a live
 * instrument, not just a statistic.
 */
export function GaugeStat({ value, displayValue, label, color = "text-primary" }: GaugeStatProps) {
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - Math.min(100, Math.max(0, value)) / 100);

  return (
    <div className="flex flex-col items-center gap-4 rounded-2xl border border-border bg-card p-6 shadow-sm">
      <div className="relative size-28">
        <svg viewBox="0 0 100 100" className="size-full -rotate-90">
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            strokeWidth="7"
            className="stroke-border"
          />
          <motion.circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            strokeWidth="7"
            strokeLinecap="round"
            strokeDasharray={circumference}
            className={color}
            stroke="currentColor"
            initial={{ strokeDashoffset: circumference }}
            whileInView={{ strokeDashoffset: offset }}
            viewport={{ once: true }}
            transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1] }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center font-mono text-xl font-medium text-foreground">
          {displayValue}
        </div>
      </div>
      <span className="eyebrow text-center">{label}</span>
    </div>
  );
}
