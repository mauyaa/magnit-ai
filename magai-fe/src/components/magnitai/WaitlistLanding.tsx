import { Link } from "@tanstack/react-router";
import { ArrowRight, Play, Mail } from "lucide-react";
import { MagnitaiLogo } from "@/components/magnitai/ui/MagnitaiLogo";

export function WaitlistLanding() {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-background px-4 font-sans text-foreground">
      <div className="surface-grid pointer-events-none fixed inset-0 z-0" />
      <div className="grain-overlay pointer-events-none fixed inset-0 z-0" />

      <div className="relative z-10 flex flex-col items-center text-center max-w-2xl mx-auto">
        <MagnitaiLogo className="mb-8" />

        <h1 className="font-heading text-5xl font-medium leading-[1.02] tracking-[-0.055em] text-foreground sm:text-6xl md:text-7xl">
          Self-healing AI widgets
          <br />
          <span className="hero-accent">for small business.</span>
        </h1>

        <p className="mt-6 max-w-lg text-lg font-medium text-muted-foreground leading-relaxed">
          Magnitai builds, deploys, and maintains on-brand interactive widgets — calculators, quizzes, and AI tools — so your site keeps converting even as it evolves.
        </p>

        <div className="mt-10 flex flex-col sm:flex-row items-center gap-4">
          <a
            href="#waitlist"
            className="inline-flex h-14 items-center gap-3 rounded-xl bg-primary px-8 text-base font-bold text-primary-foreground shadow-sm transition-transform hover:-translate-y-0.5 active:scale-[0.97]"
          >
            <Mail className="size-5" /> Join the waitlist
          </a>
          <a
            href="#"
            className="inline-flex h-14 items-center gap-3 rounded-xl border border-border bg-card px-8 text-base font-bold text-foreground shadow-sm transition-transform hover:-translate-y-0.5 active:scale-[0.97]"
          >
            <Play className="size-5" /> View demo
          </a>
        </div>

        <div className="mt-16 w-full max-w-md" id="waitlist">
          <div className="rounded-2xl border border-border bg-card p-8 shadow-sm">
            <h2 className="font-heading text-xl font-semibold text-foreground mb-2">
              Get early access
            </h2>
            <p className="text-sm text-muted-foreground font-medium mb-6">
              Be the first to know when Magnitai launches.
            </p>
            <form
              onSubmit={(e) => e.preventDefault()}
              className="flex flex-col sm:flex-row gap-3"
            >
              <input
                type="email"
                placeholder="you@company.com"
                required
                className="flex-1 h-12 rounded-xl border border-border bg-background px-4 text-sm font-medium text-foreground outline-none focus:border-primary transition-colors placeholder:text-muted-foreground/50"
              />
              <button
                type="submit"
                className="h-12 rounded-xl bg-primary px-6 text-sm font-bold text-primary-foreground shadow-sm transition-transform hover:-translate-y-0.5 active:scale-[0.97] flex items-center gap-2"
              >
                Notify me <ArrowRight className="size-4" />
              </button>
            </form>
          </div>
        </div>

        <div className="mt-16 flex items-center gap-8 text-xs text-muted-foreground">
          <Link to="/privacy" className="hover:text-foreground transition-colors font-medium">
            Privacy
          </Link>
          <Link to="/terms" className="hover:text-foreground transition-colors font-medium">
            Terms
          </Link>
        </div>
      </div>
    </div>
  );
}
