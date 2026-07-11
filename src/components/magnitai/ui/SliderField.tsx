import React from "react";

interface SliderFieldProps {
  id: string;
  label: string;
  /** Pre-formatted display string shown next to the label (e.g. "3,500" or "+3.8%") */
  displayValue: string;
  min: number;
  max: number;
  step: number;
  value: number;
  onChange: (value: number) => void;
}

/**
 * Labelled range-slider field.
 * Eliminates the triple copy-paste in InteractiveWidgetDemo (visitors, conversionBoost, avgOrder).
 */
export function SliderField({
  id,
  label,
  displayValue,
  min,
  max,
  step,
  value,
  onChange,
}: SliderFieldProps) {
  return (
    <div className="space-y-4">
      <div className="flex justify-between items-end">
        <label
          htmlFor={id}
          className="text-sm font-bold text-muted-foreground uppercase tracking-widest"
        >
          {label}
        </label>
        <span className="text-xl font-mono font-black text-foreground">{displayValue}</span>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-primary h-1.5 bg-foreground/10 rounded-full appearance-none outline-none cursor-pointer"
      />
    </div>
  );
}
