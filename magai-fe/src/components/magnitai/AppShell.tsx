import type { ReactNode } from "react";
import { Navigation, type MagnitaiSection } from "./Navigation";

interface AppShellProps {
  activeSection: MagnitaiSection;
  children: ReactNode;
}

export function AppShell({ activeSection, children }: AppShellProps) {
  return (
    /*
     * Cream, not the app's paper.
     *
     * The public pages and the workspace were the same ground, so crossing from
     * marketing into the product felt like nothing happened. Cream is a step
     * warmer and lighter: the public side reads as paper stock, the workspace as
     * a desk, and the sign-in between them is a real threshold.
     */
    <div className="flex min-h-screen flex-col bg-cream font-sans text-foreground">
      <Navigation activeSection={activeSection} />
      <main className="flex-1">{children}</main>
    </div>
  );
}
