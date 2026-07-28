import React from "react";

interface PageShellProps {
  children: React.ReactNode;
  /** Max-width variant. Defaults to "7xl". */
  maxWidth?: "3xl" | "7xl";
  /** Extra classes appended to the wrapper (e.g. "space-y-16") */
  className?: string;
}

/**
 * Standard full-page content wrapper.
 * Replaces the copy-pasted `mx-auto max-w-7xl px-6 lg:px-8 py-24 min-h-screen`
 * across WidgetGallery, OwnerAnalyticsDashboard, DesignSystemOverview, and CheckoutFlow.
 */
export function PageShell({ children, maxWidth = "7xl", className }: PageShellProps) {
  const maxWClass = maxWidth === "3xl" ? "max-w-3xl" : "max-w-7xl";
  return (
    <div
      className={`mx-auto ${maxWClass} px-6 lg:px-8 py-24 min-h-screen ${className ?? ""}`.trim()}
    >
      {children}
    </div>
  );
}
