import { useState } from "react";
import { Calculator, ListChecks, Sliders, Compass, Sparkles, ArrowRight, Zap } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { PageShell } from "@/components/magnitai/ui/PageShell";
import { SectionIntro } from "@/components/magnitai/ui/SectionIntro";
import { itemAnimation } from "@/lib/motion";

export function WidgetGallery({ onSelectWidget }: { onSelectWidget: (id: string) => void }) {
  const [filter, setFilter] = useState("all");

  const widgets = [
    {
      id: "roi-calc",
      title: "ROI & Conversion Calculator",
      category: "calculator",
      desc: "Lets website visitors calculate their exact dollar returns by moving interactive sliders.",
      metrics: "+4.8x Lead Capture",
      icon: Calculator,
      color: "text-primary",
      bg: "bg-primary/10",
    },
    {
      id: "brand-quiz",
      title: "Personalized Product Recommender",
      category: "quiz",
      desc: "A 4-question interactive wizard that points visitors to the exact SKUs they need.",
      metrics: "68% Quiz Completion",
      icon: ListChecks,
      color: "text-foreground",
      bg: "bg-muted",
    },
    {
      id: "seo-audit",
      title: "Instant Website Health Auditor",
      category: "audit",
      desc: "Visitors enter their URL and receive an AI-scored report with tailored tips.",
      metrics: "3.2x Viral Shares",
      icon: Sparkles,
      color: "text-foreground",
      bg: "bg-muted",
    },
    {
      id: "pricing-quote",
      title: "Live Tier & Add-on Configurator",
      category: "calculator",
      desc: "Removes checkout friction by letting buyers customize their monthly contract live.",
      metrics: "-42% Sales Calls",
      icon: Sliders,
      color: "text-foreground",
      bg: "bg-muted",
    },
    {
      id: "onboard-flow",
      title: "Self-Healing Onboarding Companion",
      category: "wizard",
      desc: "Floating checklist that adapts automatically when your web app layout updates.",
      metrics: "99.4% Uptime",
      icon: Compass,
      color: "text-foreground",
      bg: "bg-muted",
    },
  ];

  const filtered = filter === "all" ? widgets : widgets.filter((w) => w.category === filter);

  return (
    <PageShell>
      <div className="max-w-3xl mb-20">
        <SectionIntro
          eyebrow="Interactive templates"
          heading={
            <>
              Engineered to perform.
              <br />
              <span className="hero-accent">Styled for your brand.</span>
            </>
          }
          headingClassName="font-heading text-5xl font-medium leading-[1.02] tracking-[-0.045em] text-foreground md:text-6xl"
          body="Every template is self-healing, incredibly tactile, and deploys with absolute precision."
        />

        {/* Filter Bar */}
        <div
          className="flex flex-wrap gap-2 mt-10"
          role="group"
          aria-label="Filter widgets by category"
        >
          {[
            { id: "all", label: "All Examples" },
            { id: "calculator", label: "Calculators" },
            { id: "quiz", label: "Quizzes" },
            { id: "audit", label: "AI Audits" },
            { id: "wizard", label: "Onboarding" },
          ].map((f) => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              aria-pressed={filter === f.id}
              className={`rounded-full border px-6 py-2.5 text-sm font-semibold transition-all active:scale-95 ${
                filter === f.id
                  ? "border-foreground bg-foreground text-background"
                  : "border-border bg-card text-foreground hover:border-foreground/40"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Empty state */}
      {filtered.length === 0 && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-12 flex flex-col items-center rounded-2xl border border-dashed border-border py-20 text-center"
        >
          <div className="grid size-12 place-items-center rounded-xl bg-secondary text-muted-foreground">
            <Compass className="size-5" />
          </div>
          <h3 className="mt-5 font-heading text-xl font-medium text-foreground">
            No templates in this category yet
          </h3>
          <p className="mt-2 max-w-xs text-sm font-medium text-muted-foreground">
            Try a different filter, or build the widget you have in mind from scratch.
          </p>
          <button
            type="button"
            onClick={() => setFilter("all")}
            className="mt-6 rounded-full border border-foreground bg-foreground px-5 py-2 text-sm font-semibold text-background transition-opacity hover:opacity-80"
          >
            View all examples
          </button>
        </motion.div>
      )}

      {/* Cards Grid */}
      <motion.div layout className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mt-12">
        <AnimatePresence mode="popLayout">
          {filtered.map((widget, i) => (
            <motion.div
              key={widget.id}
              variants={itemAnimation}
              initial="hidden"
              animate="show"
              exit="hidden"
              className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-border bg-card p-6 shadow-sm transition-all hover:-translate-y-1 hover:shadow-xl hover:border-foreground/20"
            >
              <div>
                <div className="flex items-center justify-between mb-8">
                  <div className={`p-3 rounded-2xl ${widget.bg} ${widget.color}`}>
                    <widget.icon className="size-6" />
                  </div>
                  <span className="font-mono text-[10px] font-bold tracking-widest text-primary uppercase bg-primary/10 px-3 py-1 rounded-full">
                    {widget.metrics}
                  </span>
                </div>

                <h3 className="mt-5 text-xl font-bold text-foreground group-hover:text-primary transition-colors">
                  {widget.title}
                </h3>
                <p className="mt-3 text-sm font-medium text-muted-foreground leading-relaxed">
                  {widget.desc}
                </p>
              </div>

              <div className="mt-10 pt-5 border-t border-border flex items-center justify-between">
                <span className="text-[10px] font-mono font-bold text-muted-foreground">
                  [+] Deploy in 45s
                </span>
                <button
                  type="button"
                  onClick={() => onSelectWidget(widget.id)}
                  className="flex items-center gap-1.5 rounded-full bg-foreground px-4 py-2 text-xs font-bold text-background transition-opacity hover:opacity-80"
                  aria-label={`Preview ${widget.title}`}
                >
                  Preview <ArrowRight className="size-3" />
                </button>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </motion.div>
    </PageShell>
  );
}
