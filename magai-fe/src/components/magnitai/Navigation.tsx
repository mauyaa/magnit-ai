import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowUpRight, Menu, X } from "lucide-react";
import { MagnitaiLogo } from "@/components/magnitai/ui/MagnitaiLogo";

export type MagnitaiSection =
  | "landing"
  | "transparency"
  | "gallery"
  | "analytics"
  | "design-system"
  | "checkout"
  | "build-story"
  | "dashboard";

interface NavigationProps {
  activeSection: MagnitaiSection;
}

const navItems = [
  { id: "landing", label: "Product", to: "/" },
  { id: "transparency", label: "How it works", to: "/how-it-works" },
  { id: "gallery", label: "Examples", to: "/examples" },
  { id: "analytics", label: "Analytics", to: "/analytics" },
  { id: "design-system", label: "Design system", to: "/design-system" },
] as const;

export function Navigation({ activeSection }: NavigationProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="fixed inset-x-0 top-0 z-50 px-3 pt-3 sm:px-6 sm:pt-5">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between rounded-2xl border border-foreground/[0.06] bg-background/80 px-3 shadow-[0_14px_45px_-26px_oklch(0.16_0.02_40_/_0.35)] backdrop-blur-2xl sm:px-4">
        <Link
          to="/"
          className="group rounded-xl px-2 py-1.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary transition-transform duration-300 hover:scale-[1.02]"
          aria-label="Magnitai home"
        >
          <MagnitaiLogo />
        </Link>

        <nav className="hidden items-center gap-1 md:flex" aria-label="Main navigation">
          {navItems.map((item) => {
            const active = activeSection === item.id;
            return (
              <Link
                key={item.id}
                to={item.to}
                aria-current={active ? "page" : undefined}
                className={`relative rounded-lg px-3.5 py-2 text-[13px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${active ? "text-foreground" : "text-muted-foreground hover:text-foreground"}`}
              >
                {item.label}
                {active && (
                  <motion.span
                    layoutId="nav-indicator"
                    className="absolute inset-x-3 bottom-0 h-px bg-primary"
                    transition={{ type: "spring", stiffness: 500, damping: 42 }}
                  />
                )}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-2">
          <Link
            to="/dashboard"
            className="hidden h-10 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground shadow-sm transition-transform hover:-translate-y-0.5 active:scale-[0.97] active:translate-y-0 sm:flex"
          >
            Dashboard <ArrowUpRight className="size-4" />
          </Link>
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            className="grid size-10 place-items-center rounded-xl border border-border bg-card md:hidden"
            aria-label={menuOpen ? "Close navigation" : "Open navigation"}
            aria-expanded={menuOpen}
            aria-controls="mobile-navigation"
          >
            {menuOpen ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {menuOpen && (
          <motion.nav
            id="mobile-navigation"
            initial={{ opacity: 0, y: -6, scale: 0.99 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.99 }}
            transition={{ duration: 0.14 }}
            className="mx-auto mt-2 max-w-7xl bg-background border border-foreground/10 rounded-2xl p-2 md:hidden shadow-lg backdrop-blur-2xl"
            aria-label="Mobile navigation"
          >
            {navItems.map((item) => (
              <Link
                key={item.id}
                to={item.to}
                onClick={() => setMenuOpen(false)}
                aria-current={activeSection === item.id ? "page" : undefined}
                className={`flex w-full items-center justify-between rounded-xl px-4 py-3 text-left text-sm font-semibold ${activeSection === item.id ? "bg-secondary text-foreground" : "text-muted-foreground"}`}
              >
                {item.label}
                {activeSection === item.id && <span className="size-1.5 rounded-full bg-primary" />}
              </Link>
            ))}
            <Link
              to="/dashboard"
              onClick={() => setMenuOpen(false)}
              className="mt-2 flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-primary text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
            >
              Dashboard <ArrowUpRight className="size-4" />
            </Link>
          </motion.nav>
        )}
      </AnimatePresence>
    </header>
  );
}
