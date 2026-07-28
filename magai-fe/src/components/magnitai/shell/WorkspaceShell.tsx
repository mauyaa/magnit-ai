import { Link } from "@tanstack/react-router";
import { Menu } from "lucide-react";
import { useState, type ReactNode } from "react";

import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { AccountMenu } from "./AccountMenu";
import { WorkspaceSidebar } from "./WorkspaceSidebar";

export interface Crumb {
  label: string;
  /** Omitted on the final crumb, which is the page you are already on. */
  to?: string;
}

/**
 * The signed-in application frame.
 *
 * Deliberately separate from `AppShell`, which dresses the marketing pages.
 * One component serving both is what produced the previous chrome: a header
 * that changed identity at the door, advertised the product to customers who
 * had already bought it, and left every app screen to invent its own title,
 * its own top padding, and its own copy of the primary action.
 *
 * Everything positional lives here so no page can drift: the rail, the bar,
 * the content gutter, and the one max-width they all share.
 */
export function WorkspaceShell({
  children,
  breadcrumb = [],
  contentWidth = "standard",
}: {
  children: ReactNode;
  breadcrumb?: Crumb[];
  /**
   * Most workspace screens benefit from a restrained measure. Canvas-like
   * tools (the brand studio, for example) need the available viewport so an
   * editor and a truthful preview can sit side-by-side without either becoming
   * a narrow card.
   */
  contentWidth?: "standard" | "wide";
}) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background font-sans text-foreground">
      {/* The rail: fixed, so content scrolls under a navigation that never moves. */}
      <div className="fixed inset-y-0 left-0 z-40 hidden w-64 border-r border-inverse-border lg:block">
        <WorkspaceSidebar />
      </div>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border bg-background/85 px-4 backdrop-blur-xl sm:px-6 lg:px-8">
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger
              className="btn btn-ghost -ml-2 size-9 shrink-0 px-0 lg:hidden"
              aria-label="Open navigation"
            >
              <Menu className="size-5" aria-hidden="true" />
            </SheetTrigger>
            <SheetContent side="left" className="w-72 p-0">
              <WorkspaceSidebar onNavigate={() => setMobileOpen(false)} />
            </SheetContent>
          </Sheet>

          {/*
           * Breadcrumb, not a back link. Every detail screen had rolled its own
           * ("← Your tools" as body text), which told you where you could go but
           * never where you were.
           */}
          <nav aria-label="Breadcrumb" className="min-w-0 flex-1">
            <ol className="flex items-center gap-1.5 text-sm">
              {breadcrumb.map((crumb, index) => {
                const last = index === breadcrumb.length - 1;
                return (
                  <li key={`${crumb.label}-${index}`} className="flex min-w-0 items-center gap-1.5">
                    {index > 0 && (
                      <span aria-hidden="true" className="text-n-400">
                        /
                      </span>
                    )}
                    {crumb.to && !last ? (
                      <Link
                        to={crumb.to}
                        className="shrink-0 text-muted-foreground transition-colors hover:text-foreground"
                      >
                        {crumb.label}
                      </Link>
                    ) : (
                      <span
                        aria-current={last ? "page" : undefined}
                        className="truncate font-medium text-foreground"
                      >
                        {crumb.label}
                      </span>
                    )}
                  </li>
                );
              })}
            </ol>
          </nav>

          <AccountMenu />
        </header>

        <main
          className={`mx-auto w-full px-4 py-8 sm:px-6 lg:px-8 ${
            contentWidth === "wide" ? "max-w-[96rem]" : "max-w-[76rem]"
          }`}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
