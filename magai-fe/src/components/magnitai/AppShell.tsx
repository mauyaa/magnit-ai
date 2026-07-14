import type { ReactNode } from "react";
import { Navigation, type MagnitaiSection } from "./Navigation";

interface AppShellProps {
  activeSection: MagnitaiSection;
  children: ReactNode;
}

export function AppShell({ activeSection, children }: AppShellProps) {
  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-background font-sans text-foreground selection:bg-secondary/20 selection:text-secondary">
      <div className="surface-grid pointer-events-none fixed inset-0 z-0" />
      <div className="grain-overlay pointer-events-none fixed inset-0 z-0" />
      <div className="relative z-10 flex min-h-screen flex-col">
        <Navigation activeSection={activeSection} />
        <main className="flex-1">{children}</main>
      </div>
    </div>
  );
}
