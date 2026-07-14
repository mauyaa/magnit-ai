import React, { useState, useEffect } from "react";
import {
  CheckCircle2,
  Loader2,
  Globe2,
  Palette,
  Sparkles,
  Shield,
  Rocket,
  Eye,
  Clock,
  TrendingUp,
  Cpu,
  Layers,
  Activity,
  ChevronRight,
  RefreshCw,
  Database,
  Code2,
  Heart,
  type LucideIcon,
} from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { MetricStat } from "@/components/magnitai/ui/MetricStat";

type StageStatus = "complete" | "active" | "pending";

interface Stage {
  id: string;
  icon: LucideIcon;
  title: string;
  subtitle: string;
  status: StageStatus;
  duration: string;
  model: string;
  details: { label: string; value: string; tone?: string }[];
  output?: string;
}

// Fix 6: Static data moved outside component — no re-creation on every render
const stages: Stage[] = [
    {
      id: "analysis",
      icon: Globe2,
      title: "Site Analysis",
      subtitle: "Understanding context, audience, and purpose",
      status: "complete",
      duration: "2.14s",
      model: "GPT-4o · Crawler v2.3",
      details: [
        { label: "Pages crawled", value: "47" },
        { label: "Industry", value: "B2B SaaS", tone: "primary" },
        { label: "Audience clarity", value: "92%", tone: "success" },
        { label: "Primary CTA", value: "Start trial" },
      ],
      output:
        "Site is a project management tool aimed at small marketing teams. Tone is friendly-professional.",
    },
    {
      id: "brand",
      icon: Palette,
      title: "Brand Extraction",
      subtitle: "Capturing voice, palette, and visual personality",
      status: "complete",
      duration: "4.72s",
      model: "DSPy + Gemini 2.5",
      details: [
        { label: "Primary", value: "#0F1E36" },
        { label: "Accent", value: "#E86141" },
        { label: "Heading", value: "Sora 700" },
        { label: "Voice", value: "Confident", tone: "primary" },
      ],
      output: "Extracted six tonal markers and twelve visual tokens. Voice prefers concrete verbs.",
    },
    {
      id: "widget-gen",
      icon: Sparkles,
      title: "Widget Generation",
      subtitle: "Composing the experience tailored to your brand",
      status: "active",
      duration: "in progress",
      model: "Antigravity v3.1",
      details: [
        { label: "Widget type", value: "ROI Calculator", tone: "primary" },
        { label: "Components", value: "9 / 12" },
        { label: "Validation", value: "31 passed", tone: "success" },
        { label: "Remaining", value: "~12s" },
      ],
    },
    {
      id: "heal",
      icon: Shield,
      title: "Self-Healing Layer",
      subtitle: "Adding the guardian that keeps it perfect",
      status: "pending",
      duration: "—",
      model: "Sentinel Watchdog",
      details: [],
    },
    {
      id: "deploy",
      icon: Rocket,
      title: "Deployment",
      subtitle: "Going live across the edge network",
      status: "pending",
      duration: "—",
      model: "Edge CDN",
      details: [],
    },
];

const liveLog = [
    { time: "00:11.4", text: "Composed pricing-slider component with brand-matched tokens" },
    { time: "00:10.9", text: "Validated ARIA labels — 100% compliant" },
    { time: "00:10.2", text: "Generated 'projected revenue' calculation formula" },
    { time: "00:09.7", text: "Selected Sora 700 for primary numeric display" },
    { time: "00:09.0", text: "Created warm secondary accent gradient" },
    { time: "00:08.5", text: "Initialized layout grid · 7/5 split confirmed" },
];

export function TransparencyDashboard() {
  const [activeStageId, setActiveStageId] = useState<string>("widget-gen");
  const [progress, setProgress] = useState<number>(67);

  useEffect(() => {
    const interval = setInterval(() => {
      setProgress((p) => (p < 90 ? p + 0.3 : p));
    }, 200);
    return () => clearInterval(interval);
  }, []);

  const activeStage = stages.find((s) => s.id === activeStageId) ?? stages[2];

  return (
    <div className="min-h-screen pb-24 pt-32 font-sans">
      {/* ===== HEADER ===== */}
      <div className="border-b border-border bg-background/80 backdrop-blur-md relative z-10">
        <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
            <div>
              <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-muted-foreground font-bold mb-4">
                <span>Builds</span>
                <ChevronRight className="size-3 opacity-50" />
                <span className="font-mono text-primary">#a4f9c2</span>
                <ChevronRight className="size-3 opacity-50" />
                <span className="text-foreground">ROI Calculator</span>
              </div>
              <h1 className="font-heading text-4xl font-normal leading-[1.02] tracking-[-0.045em] text-foreground md:text-5xl">
                ROI Calculator <span className="text-muted-foreground font-medium">for</span>{" "}
                StrideOS
              </h1>

              <div className="flex flex-wrap items-center gap-4 mt-5">
                <div className="inline-flex items-center gap-2 bg-primary/10 px-3 py-1.5 rounded-full border border-primary/20">
                  <span className="size-1.5 rounded-full bg-primary animate-pulse" />
                  <span className="text-[11px] font-bold tracking-widest uppercase text-primary">
                    Building Stage 3/5
                  </span>
                </div>
                <span className="eyebrow flex items-center gap-1.5">
                  <Clock className="size-3.5" /> Elapsed 11.4s
                </span>
                <span className="eyebrow flex items-center gap-1.5">
                  <Database className="size-3.5" /> strideos.com
                </span>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button className="h-10 px-4 rounded-full bg-card border border-border hover:bg-secondary text-foreground font-bold text-xs uppercase tracking-widest transition-colors flex items-center gap-2 active:scale-95">
                <Eye className="size-3.5" /> Preview
              </button>
              <button className="h-10 px-4 rounded-full bg-card border border-border hover:bg-secondary text-foreground font-bold text-xs uppercase tracking-widest transition-colors flex items-center gap-2 active:scale-95">
                <Code2 className="size-3.5" /> Prompts
              </button>
              <button className="h-10 px-6 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 font-bold text-xs uppercase tracking-widest transition-colors flex items-center gap-2 shadow-sm active:scale-95">
                <RefreshCw className="size-3.5" /> Rebuild
              </button>
            </div>
          </div>

          {/* Overall progress */}
          <div className="mt-8">
            <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-widest text-muted-foreground mb-3">
              <span>Overall progress</span>
              <span className="font-mono text-foreground">{Math.round(progress)}%</span>
            </div>
            <Progress value={progress} className="h-1.5 bg-secondary" />
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 lg:px-8 mt-12">
        <div className="grid md:grid-cols-2 lg:grid-cols-12 gap-12 lg:gap-20">
          {/* ===== TIMELINE COLUMN ===== */}
          <div className="md:col-span-1 lg:col-span-7 space-y-4">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-semibold font-heading text-foreground">Build Story</h2>
              <span className="text-[11px] font-bold uppercase tracking-widest text-primary">
                Live Stream
              </span>
            </div>

            <div className="space-y-4">
              {stages.map((stage, idx) => {
                const Icon = stage.icon;
                const isActive = activeStageId === stage.id;
                const isComplete = stage.status === "complete";
                const isPending = stage.status === "pending";

                return (
                  <button
                    key={stage.id}
                    onClick={() => setActiveStageId(stage.id)}
                    className={`w-full text-left flex items-start gap-6 group transition-all p-6 rounded-2xl border ${
                      isActive
                        ? "border-border bg-card shadow-sm"
                        : "border-transparent hover:border-border hover:bg-secondary/30"
                    }`}
                  >
                    <div className="flex flex-col items-center shrink-0 pt-1">
                      <div
                        className={`relative size-12 rounded-full flex items-center justify-center transition-colors ${
                          isComplete
                            ? "bg-success/10 text-success"
                            : stage.status === "active"
                              ? "bg-primary text-primary-foreground shadow-lg shadow-primary/30"
                              : "bg-secondary text-muted-foreground"
                        }`}
                      >
                        {stage.status === "active" ? (
                          <Loader2 className="size-5 animate-spin" />
                        ) : isComplete ? (
                          <CheckCircle2 className="size-5" />
                        ) : (
                          <Icon className="size-5" />
                        )}
                      </div>
                      {idx < stages.length - 1 && (
                        <div
                          className={`w-0.5 h-16 mt-4 rounded-full ${isComplete ? "bg-success/20" : "bg-secondary"}`}
                        />
                      )}
                    </div>

                    <div className="flex-1 min-w-0 pb-2">
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <h3
                            className={`text-xl font-semibold font-heading truncate ${
                              isPending ? "text-muted-foreground" : "text-foreground"
                            }`}
                          >
                            <span className="text-muted-foreground/70 font-mono text-sm mr-3">
                              0{idx + 1}
                            </span>
                            {stage.title}
                          </h3>
                          <p
                            className={`text-sm mt-2 font-medium ${isPending ? "text-muted-foreground/70" : "text-muted-foreground"}`}
                          >
                            {stage.subtitle}
                          </p>
                          <div className="flex items-center gap-4 mt-3 text-[11px] uppercase tracking-widest font-bold">
                            <span className="flex items-center gap-1.5 text-muted-foreground">
                              <Cpu className="size-3.5" /> {stage.model}
                            </span>
                            <span className="flex items-center gap-1.5 text-muted-foreground">
                              <Clock className="size-3.5" /> {stage.duration}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Expanded details */}
                      {isActive && stage.details.length > 0 && (
                        <div className="mt-8 pt-6 border-t border-border space-y-4">
                          <div className="grid grid-cols-2 gap-4">
                            {stage.details.map((d, i) => (
                              <div
                                key={i}
                                className="rounded-xl bg-secondary/50 p-4 border border-border/50"
                              >
                                <div className="text-[10px] uppercase tracking-widest text-muted-foreground font-bold mb-1.5">
                                  {d.label}
                                </div>
                                <div
                                  className={`text-base font-bold ${
                                    d.tone === "success" ? "text-success" : "text-foreground"
                                  }`}
                                >
                                  {d.value}
                                </div>
                              </div>
                            ))}
                          </div>
                          {stage.output && (
                            <div className="rounded-xl bg-primary/5 p-5 border border-primary/10">
                              <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-primary font-bold mb-2">
                                <Sparkles className="size-3.5" /> AI Insight
                              </div>
                              <p className="text-sm font-medium text-foreground leading-relaxed">
                                {stage.output}
                              </p>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* ===== RIGHT SIDEBAR ===== */}
          <div className="md:col-span-1 lg:col-span-5 space-y-10">
            {/* Metrics */}
            <div className="grid grid-cols-2 gap-4">
              {[
                {
                  icon: Activity,
                  label: "Self-heal",
                  value: "0",
                  sub: "Watching",
                  color: "text-success",
                },
                {
                  icon: TrendingUp,
                  label: "Confidence",
                  value: "97.4%",
                  sub: "Brand fit",
                  color: "text-primary",
                },
                {
                  icon: Layers,
                  label: "Components",
                  value: "9/12",
                  sub: "Composed",
                  color: "text-foreground",
                },
                {
                  icon: Heart,
                  label: "A11y score",
                  value: "AAA",
                  sub: "WCAG 2.2",
                  color: "text-foreground",
                },
              ].map((m, idx) => (
                <MetricStat
                  key={idx}
                  icon={m.icon}
                  iconColor={m.color}
                  label={m.label}
                  value={m.value}
                  subLabel={m.sub}
                  valueSize="md"
                  layout="compact"
                  className="bg-card shadow-sm border border-border"
                />
              ))}
            </div>

            {/* Brand preview */}
            <div className="rounded-2xl bg-foreground text-background p-8 relative overflow-hidden shadow-[0_20px_40px_rgba(0,0,0,0.1)]">
              <div className="absolute top-0 right-0 size-64 rounded-full bg-primary/30 blur-3xl pointer-events-none -translate-y-1/2 translate-x-1/4" />
              <div className="relative">
                <div className="eyebrow-on-dark mb-3">Brand Capsule</div>
                <h3 className="text-2xl font-semibold font-heading mb-1">StrideOS</h3>
                <p className="text-sm font-medium text-background/60">
                  "Confident · warm · direct"
                </p>

                <div className="flex gap-2 mt-8">
                  {[
                    { hex: "#0F1E36", label: "Primary" },
                    { hex: "#E86141", label: "Accent" },
                    { hex: "#F5F3EE", label: "Surface" },
                    { hex: "#1FB897", label: "Success" },
                    { hex: "#FFC857", label: "Warning" },
                  ].map(({ hex, label }) => (
                    <div key={hex} className="flex flex-col gap-2 flex-1">
                      <div
                        className="w-full aspect-square rounded-xl border border-white/10"
                        style={{ backgroundColor: hex }}
                        role="img"
                        aria-label={`${label} color: ${hex}`}
                      />
                      <span className="text-[9px] font-mono font-bold text-background/50 text-center">
                        {hex}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Live activity feed */}
            <div>
              <div className="flex items-center justify-between mb-4 px-2">
                <div className="flex items-center gap-2">
                  <span className="size-2 rounded-full bg-success animate-pulse" />
                  <h3 className="text-sm font-bold text-foreground font-heading">Streaming Log</h3>
                </div>
              </div>
              <div className="border-t border-border max-h-96 overflow-y-auto">
                {liveLog.map((entry, idx) => (
                  <div
                    key={idx}
                    className="py-4 border-b border-border/50 flex items-start gap-4 hover:bg-secondary/30 transition-colors px-2"
                  >
                    <span className="text-[11px] font-mono font-bold text-muted-foreground shrink-0 pt-0.5">
                      {entry.time}
                    </span>
                    <span className="text-sm font-medium text-foreground leading-relaxed">
                      {entry.text}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
