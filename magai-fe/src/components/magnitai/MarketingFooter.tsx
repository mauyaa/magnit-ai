import { Link } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";

import { MagnitaiLogo } from "./ui/MagnitaiLogo";

const FOOTER_LINKS = [
  { label: "How it works", to: "/how-it-works" },
  { label: "What we build", to: "/examples" },
  { label: "Pricing", to: "/pricing" },
  { label: "Privacy", to: "/privacy" },
  { label: "Terms", to: "/terms" },
] as const;

/**
 * The shared close for public pages.
 *
 * Public pages close with one clear next step, the dark gridded plane from the
 * approved showcase, and the same navigation everywhere.
 */
export function MarketingFooter() {
  return (
    <footer className="editorial-grid-dark relative overflow-hidden bg-inverse text-inverse-foreground">
      <div className="relative mx-auto max-w-6xl px-6 py-16 lg:px-8 lg:py-20">
        <div className="grid items-end gap-10 border-b border-inverse-border pb-14 lg:grid-cols-[1fr_auto]">
          <div>
            <span className="font-mono text-[10px] uppercase tracking-[0.17em] text-brand-on-inverse">
              Ready when you are
            </span>
            <h2 className="mt-5 max-w-[15ch] font-display text-[clamp(2.6rem,5vw,4.6rem)] font-normal leading-[0.94] tracking-[-0.05em]">
              Make your next page do something useful.
            </h2>
          </div>

          <Link
            to="/build"
            className="group inline-flex h-14 min-w-56 items-center justify-between gap-6 rounded-full bg-brand px-5 text-sm font-semibold text-foreground shadow-float transition-transform hover:-translate-y-1"
          >
            Start with your website
            <span className="grid size-10 place-items-center rounded-full bg-inverse text-inverse-foreground">
              <ArrowRight
                className="size-4 transition-transform group-hover:translate-x-0.5"
                aria-hidden="true"
              />
            </span>
          </Link>
        </div>

        <div className="flex flex-col gap-8 pt-8 sm:flex-row sm:items-center sm:justify-between">
          <Link
            to="/"
            className="w-fit rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-on-inverse"
            aria-label="Magnitai home"
          >
            <MagnitaiLogo
              size="sm"
              variant="tile"
              className="[&_span:last-child]:text-inverse-foreground"
            />
          </Link>

          <nav className="flex flex-wrap gap-x-6 gap-y-3" aria-label="Footer">
            {FOOTER_LINKS.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className="text-sm text-inverse-muted transition-colors hover:text-inverse-foreground"
              >
                {link.label}
              </Link>
            ))}
          </nav>

          <p className="text-sm text-inverse-subtle">© 2026 Magnitai</p>
        </div>
      </div>
    </footer>
  );
}
