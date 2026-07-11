import { Link } from "@tanstack/react-router";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Check,
  CheckCircle2,
  Code2,
  Gauge,
  MousePointer2,
  Palette,
  RefreshCw,
  ShieldCheck,
  WandSparkles,
  Zap,
} from "lucide-react";
import { InteractiveWidgetDemo } from "./InteractiveWidgetDemo";
import { reveal, staggerContainer } from "@/lib/motion";
import { MagnitaiLogo } from "@/components/magnitai/ui/MagnitaiLogo";
const steps = [
  {
    number: "01",
    icon: Palette,
    title: "Reads your brand",
    description: "Magnitai maps your colors, type, tone, and conversion goals from a single URL.",
  },
  {
    number: "02",
    icon: WandSparkles,
    title: "Builds the experience",
    description:
      "Describe the outcome. The engine composes a tailored calculator, quiz, audit, or flow.",
  },
  {
    number: "03",
    icon: RefreshCw,
    title: "Keeps it healthy",
    description:
      "Continuous checks catch layout drift and repair the widget when your site changes.",
  },
];
export function LandingPage() {
  return (
    <div className="overflow-hidden text-foreground">
      <section className="relative px-5 pt-32 pb-20 sm:px-8 sm:pt-40 lg:pb-32">
        <div className="mx-auto max-w-5xl text-center">
          <motion.div initial="hidden" animate="visible" variants={staggerContainer}>
            <motion.h1
              variants={reveal}
              className="font-heading text-[clamp(3.25rem,8vw,6.5rem)] font-normal leading-[0.98] tracking-[-0.03em] text-foreground"
            >
              Turn passive pages into <br className="hidden md:block" />
              <span className="hero-accent">moments</span> that convert.
            </motion.h1>
            <motion.p
              variants={reveal}
              className="mx-auto mt-8 max-w-2xl text-lg font-medium leading-relaxed text-muted-foreground sm:text-xl"
            >
              Magnitai creates on-brand calculators, quizzes, and AI tools—then monitors and repairs them as your website evolves.
            </motion.p>
            <motion.div
              variants={reveal}
              className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row"
            >
              <Link
                to="/build"
                className="group inline-flex h-14 items-center justify-center gap-3 rounded-xl bg-primary py-1.5 pl-8 pr-1.5 text-sm font-bold tracking-wide text-primary-foreground shadow-[0_16px_36px_-14px_oklch(0.55_0.24_28_/_0.6)] transition-transform hover:-translate-y-0.5 active:scale-[0.97] active:translate-y-0"
              >
                Start building
                <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-white/15 transition-transform duration-300 group-hover:translate-x-0.5">
                  <ArrowRight className="size-4" />
                </span>
              </Link>
            </motion.div>
          </motion.div>
        </div>

        {/* Safari Browser Mockup */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.3 }}
          className="mx-auto mt-20 max-w-5xl"
        >
          <div className="overflow-hidden rounded-[1.5rem] border border-foreground/10 bg-card shadow-2xl">
            {/* Browser Header */}
            <div className="flex items-center border-b border-foreground/5 bg-secondary/50 px-4 py-3">
              <div className="flex gap-2">
                <div className="size-3 rounded-full bg-[#ff5f56] border border-black/10" />
                <div className="size-3 rounded-full bg-[#ffbd2e] border border-black/10" />
                <div className="size-3 rounded-full bg-[#27c93f] border border-black/10" />
              </div>
              <div className="mx-auto flex h-6 w-64 items-center justify-center rounded-md bg-foreground/5 text-[10px] font-medium text-foreground/40">
                magnitai.com/preview
              </div>
              <div className="w-14" /> {/* Spacer for absolute centering */}
            </div>

            {/* Interactive Demo Content */}
            <div className="bg-secondary/20 p-8 sm:p-12 lg:p-20 flex items-center justify-center min-h-[600px] relative">
              <div className="absolute inset-0 bg-[linear-gradient(to_right,#8a736012_1px,transparent_1px),linear-gradient(to_bottom,#8a736012_1px,transparent_1px)] bg-[size:24px_24px]"></div>
              <div className="w-full max-w-md relative z-10">
                 <InteractiveWidgetDemo />
              </div>
            </div>
          </div>
        </motion.div>



      </section>

      <section className="border-y border-border px-5 py-14 sm:px-8">
        <div className="mx-auto grid max-w-5xl gap-10 sm:grid-cols-3 sm:divide-x sm:divide-border">
          {[
            { value: "3.1s", label: "Median time from prompt to a live preview" },
            { value: "99.97%", label: "Widgets still passing QA after their site's last redesign" },
            { value: "0", label: "Redeploys needed when Magnitai heals a layout" },
          ].map(({ value, label }, index) => (
            <motion.div
              key={label}
              initial={{ opacity: 0, filter: "blur(6px)" }}
              whileInView={{ opacity: 1, filter: "blur(0px)" }}
              viewport={{ once: true, amount: 0.6 }}
              transition={{ duration: 0.5, delay: index * 0.1, ease: [0.16, 1, 0.3, 1] }}
              className="text-center sm:px-8"
            >
              <div className="font-mono text-5xl font-medium tracking-tight text-foreground sm:text-6xl">
                {value}
              </div>
              <p className="mt-3 text-sm font-medium leading-6 text-muted-foreground">{label}</p>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="px-5 py-24 sm:px-8 lg:py-32">
        <div className="mx-auto max-w-7xl">
          <div className="max-w-3xl">
            <h2 className="font-heading text-4xl font-medium leading-[1.02] tracking-[-0.045em] sm:text-6xl">
              From idea to embedded experience, without the handoffs.
            </h2>
          </div>
          <div className="relative mt-20">
            <div className="absolute inset-x-6 top-7 hidden h-px bg-border lg:block" />
            <div className="grid gap-x-8 gap-y-12 lg:grid-cols-3">
              {steps.map(({ number, icon: Icon, title, description }, index) => (
                <motion.div
                  key={title}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.3 }}
                  transition={{ delay: index * 0.12, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                  className={`group relative ${index === 1 ? "lg:translate-y-8" : ""}`}
                >
                  <div className="flex flex-col gap-4">
                    <div className="font-mono text-4xl font-bold tracking-tighter text-primary">
                      [{number}]
                    </div>
                  </div>
                  <h3 className="mt-6 font-heading text-2xl font-semibold tracking-[-0.04em]">
                    {title}
                  </h3>
                  <p className="mt-3 max-w-sm text-sm font-medium leading-6 text-muted-foreground">
                    {description}
                  </p>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="px-5 pb-24 sm:px-8 lg:pb-32">
        <div className="mx-auto max-w-7xl">
          <div className="max-w-3xl">
            <h2 className="font-heading text-4xl font-medium leading-[1.02] tracking-[-0.045em] sm:text-6xl">
              Your site changes. The widget keeps up.
            </h2>
            <p className="mt-5 max-w-xl text-base font-medium leading-7 text-muted-foreground sm:text-lg">
              Every redesign breaks something, somewhere. Magnitai notices before your visitors do —
              seen and repaired, not just claimed.
            </p>
          </div>

          <div className="mt-14 grid gap-px overflow-hidden rounded-[2rem] border border-border bg-border shadow-sm md:grid-cols-2">
            <motion.div
              initial={{ opacity: 0, x: -16 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
              className="bg-card p-8 sm:p-10"
            >
              <span className="eyebrow flex items-center gap-1.5 text-destructive">
                <AlertTriangle className="size-3.5" /> Before · 04:12 am
              </span>
              <h3 className="mt-4 font-heading text-xl font-semibold tracking-[-0.03em]">
                A pricing update clips the CTA
              </h3>
              <div className="mt-6 overflow-hidden rounded-2xl border border-dashed border-destructive/30 bg-destructive/[0.03] p-5">
                <div className="flex items-center gap-3">
                  <div className="h-2.5 w-20 rounded-full bg-destructive/15" />
                  <div className="ml-auto h-2.5 w-10 rounded-full bg-destructive/15" />
                </div>
                <div className="relative mt-5 h-20 rounded-xl border border-destructive/20 bg-card">
                  <div className="absolute left-4 top-7 h-8 w-24 -rotate-2 rounded-md border border-destructive/25 bg-destructive/10" />
                  <div className="absolute -right-3 top-2 h-9 w-28 rotate-2 rounded-lg border border-destructive/30 bg-card shadow-sm" />
                </div>
              </div>
              <p className="mt-4 text-[11px] font-bold uppercase tracking-widest text-destructive/80">
                CTA overflow detected
              </p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 16 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: 0.6, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
              className="bg-card p-8 sm:p-10"
            >
              <span className="eyebrow flex items-center gap-1.5 text-success">
                <CheckCircle2 className="size-3.5" /> After · healed in 38s
              </span>
              <h3 className="mt-4 font-heading text-xl font-semibold tracking-[-0.03em]">
                Magnitai realigns it automatically
              </h3>
              <div className="mt-6 overflow-hidden rounded-2xl border border-success/20 bg-success/[0.03] p-5">
                <div className="flex items-center gap-3">
                  <div className="h-2.5 w-20 rounded-full bg-foreground/10" />
                  <div className="ml-auto h-2.5 w-10 rounded-full bg-foreground/10" />
                </div>
                <div className="mt-5 flex h-20 items-center justify-between rounded-xl border border-border bg-card px-4">
                  <div className="h-8 w-24 rounded-md bg-secondary" />
                  <div className="h-8 w-20 rounded-md bg-primary" />
                </div>
              </div>
              <p className="mt-4 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest text-success">
                <Check className="size-3" /> Layout restored, no redeploy needed
              </p>
            </motion.div>
          </div>
        </div>
      </section>

      <section className="px-5 pb-24 sm:px-8 lg:pb-32">
        <motion.div
          initial={{ opacity: 0, filter: "blur(10px)" }}
          whileInView={{ opacity: 1, filter: "blur(0px)" }}
          viewport={{ once: true, amount: 0.4 }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="mx-auto max-w-4xl text-center"
        >
          <p className="font-heading text-2xl font-normal leading-snug tracking-[-0.02em] text-foreground sm:text-4xl">
            "We stopped checking our own site every time we shipped a redesign. Magnitai flagged a
            clipped calculator four minutes after a theme update — before a single customer said
            anything."
          </p>
          <div className="mt-8 flex items-center justify-center gap-3">
            <div className="grid size-10 place-items-center rounded-full bg-secondary font-mono text-sm font-medium text-foreground">
              PN
            </div>
            <div className="text-left">
              <div className="text-sm font-bold text-foreground">Priya Nair</div>
              <div className="text-sm font-medium text-muted-foreground">
                Head of Growth, Northstar Studio
              </div>
            </div>
          </div>
        </motion.div>
      </section>

      <section className="px-5 pb-24 sm:px-8 lg:pb-32">
        <div className="relative mx-auto max-w-7xl overflow-hidden rounded-[2.25rem] bg-foreground px-6 py-16 text-background sm:px-12 lg:px-20 lg:py-24">
          <div className="cta-orb absolute -right-40 -top-48 size-[560px] rounded-full" />
          <div className="relative grid items-end gap-12 lg:grid-cols-[1fr_auto]">
            <div className="max-w-3xl">
              <h2 className="font-heading text-4xl font-medium leading-[1.02] tracking-[-0.045em] text-white sm:text-6xl">
                Your highest-converting page could be one widget away.
              </h2>
              <p className="mt-6 max-w-xl text-base font-medium leading-7 text-white/60">
                Share your URL and what you want it to do. Everything after that — brand match,
                build, and the ongoing repair — is on us.
              </p>
            </div>
            <Link
              to="/build"
              className="group flex h-14 w-full items-center justify-center gap-3 rounded-2xl bg-white py-1.5 pl-7 pr-1.5 text-sm font-bold text-foreground transition-transform hover:-translate-y-1 active:scale-[0.97] active:translate-y-0 lg:w-auto"
            >
              Start building
              <span className="grid size-8 shrink-0 place-items-center rounded-full bg-foreground/8 transition-transform duration-300 group-hover:translate-x-0.5">
                <ArrowRight className="size-4" />
              </span>
            </Link>
          </div>
        </div>
      </section>
      <footer className="border-t border-border px-5 py-12 sm:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="flex flex-col gap-8 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex flex-col gap-3">
              <MagnitaiLogo size="sm" className="text-foreground" />
              <p className="text-sm font-medium text-muted-foreground max-w-xs leading-relaxed">
                Adaptive experiences, built to keep working.
              </p>
            </div>
            <nav className="flex flex-col gap-2 sm:items-end" aria-label="Footer navigation">
              <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-1">
                Product
              </span>
              {[
                { label: "How it works", to: "/how-it-works" },
                { label: "Examples", to: "/examples" },
                { label: "Analytics", to: "/analytics" },
                { label: "Design system", to: "/design-system" },
              ].map(({ label, to }) => (
                <Link
                  key={to}
                  to={to}
                  className="text-sm font-semibold text-muted-foreground hover:text-foreground transition-colors text-left sm:text-right"
                >
                  {label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="mt-10 flex flex-col gap-2 border-t border-border pt-6 text-xs font-semibold text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
            <p>© 2026 Magnitai. All rights reserved.</p>
            <div className="flex items-center gap-4">
              <Link to="/privacy" className="hover:text-foreground transition-colors">
                Privacy
              </Link>
              <Link to="/terms" className="hover:text-foreground transition-colors">
                Terms
              </Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
