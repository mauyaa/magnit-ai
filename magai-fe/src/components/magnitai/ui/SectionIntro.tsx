import React from "react";

interface SectionIntroProps {
  /** Pulsing indicator dot color */
  dot?: "primary" | "success";
  /** Small all-caps eyebrow label above the heading */
  eyebrow: string;
  /** Main heading — accepts JSX so callers can embed hero-accent spans */
  heading: React.ReactNode;
  /** Optional body paragraph below the heading */
  body?: React.ReactNode;
  /** Tailwind class overrides for the heading element (size, color, etc.) */
  headingClassName?: string;
  /** Wrapper className */
  className?: string;
}

/**
 * Pulsing-dot + eyebrow label + heading + optional body paragraph.
 * Eliminates the identical block repeated in CheckoutFlow, OwnerAnalyticsDashboard,
 * WidgetGallery, LandingPage, and TransparencyDashboard.
 */
export function SectionIntro({
  dot = "primary",
  eyebrow,
  heading,
  body,
  headingClassName = "font-heading text-5xl font-medium leading-[1.02] tracking-[-0.045em] text-foreground",
  className,
}: SectionIntroProps) {
  return (
    <div className={className}>
      <div className="inline-flex items-center gap-2 mb-6">
        <span
          className={`size-2 rounded-full animate-pulse ${
            dot === "success" ? "bg-success" : "bg-primary"
          }`}
        />
        <span className="eyebrow">{eyebrow}</span>
      </div>
      <h2 className={headingClassName}>{heading}</h2>
      {body && (
        <p className="mt-4 text-muted-foreground text-lg font-medium leading-relaxed">{body}</p>
      )}
    </div>
  );
}
