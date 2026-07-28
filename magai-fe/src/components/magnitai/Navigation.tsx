import { Link, useNavigate } from "@tanstack/react-router";
import { ArrowUpRight, LogOut, Menu, X } from "lucide-react";
import { useState } from "react";

import { MagnitaiLogo } from "@/components/magnitai/ui/MagnitaiLogo";
import { useAuth } from "@/lib/auth";

export type MagnitaiSection =
  | "landing"
  | "transparency"
  | "gallery"
  | "pricing"
  | "analytics"
  | "design-system"
  | "checkout"
  | "build-story"
  | "dashboard";

/**
 * The marketing bar.
 *
 * It used to change identity at the door: signed in, the same component swapped
 * its links for Tools / Leads / Settings and became the application's only
 * navigation. That is why the app had nowhere to put a create action, a plan,
 * or an account menu, and why its container (max-w-6xl) never lined up with the
 * page content beneath it (max-w-7xl).
 *
 * The signed-in application now has its own frame — `WorkspaceShell` — so this
 * is a marketing bar again and nothing else. It keeps a single "Go to workspace"
 * link for a signed-in visitor who lands back on the public site, which is the
 * only thing that branch ever needed to do.
 */

const MARKETING = [
  { id: "how-it-works", label: "How it works", to: "/how-it-works" },
  { id: "examples", label: "What we build", to: "/examples" },
  { id: "pricing", label: "Pricing", to: "/pricing" },
] as const;

export function Navigation({ activeSection }: { activeSection: MagnitaiSection }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const navigate = useNavigate();
  const { isAuthenticated, logout } = useAuth();
  void activeSection;

  const handleSignOut = async () => {
    setMenuOpen(false);
    await logout();
    navigate({ to: "/", replace: true });
  };

  return (
    <header className="pointer-events-none fixed inset-x-0 top-0 z-50 pt-3 font-['Inter_Variable',Inter,Arial,sans-serif]">
      <div className="mx-auto grid h-14 max-w-6xl grid-cols-[1fr_auto_1fr] items-center rounded-2xl border border-border/80 bg-background px-4 shadow-card sm:px-6 lg:px-8">
        <Link
          to="/"
          className="pointer-events-auto flex w-fit items-center rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label="Magnitai home"
        >
          <MagnitaiLogo
            size="md"
            showWordmark={false}
            variant="plain"
            className="isolate overflow-hidden rounded-[10px] bg-background [&_img]:mix-blend-multiply"
          />
        </Link>

        <nav
          className="pointer-events-auto hidden justify-self-center rounded-full border border-border/80 bg-card/90 p-1 shadow-raised md:flex"
          aria-label="Main"
        >
          {MARKETING.map((item) => (
            <Link
              key={item.id}
              to={item.to}
              className="group relative rounded-full px-4 py-2 text-[13px] font-medium tracking-[0.04em] text-n-600 transition-colors hover:text-foreground"
            >
              <span>{item.label}</span>
              <span
                aria-hidden="true"
                className="absolute inset-x-4 bottom-1.5 h-px origin-left scale-x-0 bg-foreground transition-transform duration-300 group-hover:scale-x-100"
              />
            </Link>
          ))}
        </nav>

        <div className="pointer-events-auto flex items-center gap-2 justify-self-end">
          {isAuthenticated ? (
            <>
              <Link
                to="/dashboard"
                className="group hidden h-10 items-center gap-2 rounded-full bg-foreground px-5 text-[13px] font-medium tracking-[0.04em] text-background shadow-raised transition-colors hover:bg-ink-soft sm:inline-flex"
              >
                Go to workspace
                <ArrowUpRight className="size-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
              </Link>
              <button
                type="button"
                onClick={handleSignOut}
                aria-label="Sign out"
                className="btn btn-ghost hidden h-10 px-3 sm:inline-flex"
              >
                <LogOut className="size-4" aria-hidden="true" />
              </button>
            </>
          ) : (
            <Link
              to="/login"
              className="group hidden h-10 items-center gap-2 rounded-full bg-foreground px-5 text-[13px] font-medium tracking-[0.04em] text-background shadow-raised transition-colors hover:bg-ink-soft sm:inline-flex"
            >
              Log in
              <ArrowUpRight className="size-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
            </Link>
          )}

          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            className="btn btn-ghost h-10 px-3 md:hidden"
            aria-label={menuOpen ? "Close navigation" : "Open navigation"}
            aria-expanded={menuOpen}
            aria-controls="mobile-navigation"
          >
            {menuOpen ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
      </div>

      {menuOpen && (
        <nav
          id="mobile-navigation"
          className="pointer-events-auto mx-4 mt-2 rounded-2xl border border-border bg-background/95 p-3 shadow-float backdrop-blur-xl md:hidden"
          aria-label="Mobile"
        >
          {MARKETING.map((item) => (
            <Link
              key={item.id}
              to={item.to}
              onClick={() => setMenuOpen(false)}
              className="block rounded-xl px-3 py-3 text-[13px] font-medium tracking-[0.04em] text-muted-foreground"
            >
              {item.label}
            </Link>
          ))}
          {isAuthenticated ? (
            <>
              <Link
                to="/dashboard"
                onClick={() => setMenuOpen(false)}
                className="btn btn-primary mt-3 w-full"
              >
                Go to workspace
              </Link>
              <button type="button" onClick={handleSignOut} className="btn btn-ghost mt-2 w-full">
                <LogOut className="size-4" /> Sign out
              </button>
            </>
          ) : (
            <Link
              to="/login"
              onClick={() => setMenuOpen(false)}
              className="btn btn-primary mt-3 w-full"
            >
              Log in
            </Link>
          )}
        </nav>
      )}
    </header>
  );
}
