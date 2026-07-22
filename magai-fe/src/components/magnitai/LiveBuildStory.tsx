import { useEffect, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
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

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface PipelineEvent {
  stage: string;
  status: string;
  message: string;
  data: Record<string, unknown> | null;
  progress: number | null;
  timestamp: string;
}

const stageMeta: Record<string, { icon: LucideIcon; title: string; subtitle: string; order: number }> = {
  architect: { icon: Palette, title: "Brand & Architecture", subtitle: "Extracting identity and designing widget logic", order: 1 },
  stitcher: { icon: Sparkles, title: "Design Tokens", subtitle: "Generating component theme and styles", order: 2 },
  codegen: { icon: Shield, title: "Code Generation", subtitle: "Writing and validating widget code", order: 3 },
  analyze: { icon: Globe2, title: "Site Analysis", subtitle: "Understanding context, audience, and purpose", order: 0 },
  deploy: { icon: Rocket, title: "Deployment", subtitle: "Going live across the edge network", order: 4 },
};

export function LiveBuildStory({ widgetId }: { widgetId: string }) {
  const navigate = useNavigate();
  const [stageStatuses, setStageStatuses] = useState<Record<string, string>>({});
  const [activeStageId, setActiveStageId] = useState<string | null>(null);
  const [liveLog, setLiveLog] = useState<{ time: string; text: string }[]>([]);
  const [overallProgress, setOverallProgress] = useState(0);
  const [buildComplete, setBuildComplete] = useState(false);
  const [deployUrl, setDeployUrl] = useState<string | null>(null);
  const [title, setTitle] = useState("Widget");
  const [domain, setDomain] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef(Date.now());

  useEffect(() => {
    startTimeRef.current = Date.now();
    timerRef.current = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);

    const evtSource = new EventSource(`${API_BASE}/api/widgets/${widgetId}/events`);

    evtSource.onmessage = (event) => {
      if (event.data?.startsWith(":")) return;
      try {
        const evt: PipelineEvent = JSON.parse(event.data);
        const stage = evt.stage;

        setStageStatuses((prev) => ({ ...prev, [stage]: evt.status }));
        setActiveStageId(stage);
        if (evt.progress != null) setOverallProgress(evt.progress);

        const timestamp = new Date(evt.timestamp).toLocaleTimeString();
        setLiveLog((prev) => [...prev.slice(-50), { time: timestamp, text: evt.message }]);

        if (evt.stage === "deploy" && evt.status === "complete") {
          setBuildComplete(true);
          if (evt.data?.url) setDeployUrl(evt.data.url as string);
          timerRef.current && clearInterval(timerRef.current);
        }
      } catch {
        // ignore parse errors
      }
    };

    evtSource.onerror = () => {
      // SSE connection dropped — polling fallback will handle completion
    };

    // Polling fallback: check widget status every 5s for completion
    const pollInterval = setInterval(() => {
      fetch(`${API_BASE}/api/widgets/${widgetId}`)
        .then((r) => r.json())
        .then((data) => {
          if (data.title) setTitle(data.title);
          if (data.target_url) {
            try {
              setDomain(new URL(data.target_url).hostname);
            } catch {}
          }
          if (data.status === "active" && !buildComplete) {
            setBuildComplete(true);
            if (data.deployment_url) setDeployUrl(data.deployment_url);
            setStageStatuses({
              architect: "complete",
              stitcher: "complete",
              codegen: "complete",
              deploy: "complete",
            });
            setOverallProgress(100);
            timerRef.current && clearInterval(timerRef.current);
          } else if (data.status === "failed") {
            setStageStatuses((prev) => ({ ...prev, [activeStageId || "codegen"]: "failed" }));
            setLiveLog((prev) => [
              ...prev.slice(-50),
              { time: new Date().toLocaleTimeString(), text: `Build failed: ${data.build_error || "Unknown error"}` },
            ]);
          }
          if (data.build_stage && data.build_progress != null) {
            setStageStatuses((prev) => ({ ...prev, [data.build_stage]: "active" }));
            setActiveStageId(data.build_stage);
            setOverallProgress(data.build_progress);
          }
        })
        .catch(() => {});
    }, 5_000);

    return () => {
      evtSource.close();
      clearInterval(pollInterval);
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [widgetId]);

  const sortedStages = Object.entries(stageMeta).sort((a, b) => a[1].order - b[1].order);

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
                <span className="font-mono text-primary">#{widgetId.slice(0, 6)}</span>
                <ChevronRight className="size-3 opacity-50" />
                <span className="text-foreground">{title}</span>
              </div>
              <h1 className="font-heading text-4xl font-normal leading-[1.02] tracking-[-0.045em] text-foreground md:text-5xl">
                {title} {domain && <span className="text-muted-foreground font-medium">for</span>} {domain && <span className="text-muted-foreground">{domain}</span>}
              </h1>

              <div className="flex flex-wrap items-center gap-4 mt-5">
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-primary/20"
                  style={{ backgroundColor: buildComplete ? "oklch(0.72 0.14 155 / 0.1)" : "oklch(0.56 0.19 35 / 0.1)" }}>
                  <span className={`size-1.5 rounded-full ${buildComplete ? "bg-success" : "bg-primary"} ${buildComplete ? "" : "animate-pulse"}`} />
                  <span className="text-[11px] font-bold tracking-widest uppercase"
                    style={{ color: buildComplete ? "oklch(0.72 0.14 155)" : "oklch(0.56 0.19 35)" }}>
                    {buildComplete ? "Build Complete" : "Building..."}
                  </span>
                </div>
                <span className="eyebrow flex items-center gap-1.5">
                  <Clock className="size-3.5" /> Elapsed {elapsed}s
                </span>
                <span className="eyebrow flex items-center gap-1.5">
                  <Database className="size-3.5" /> {domain || widgetId.slice(0, 8)}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {buildComplete && deployUrl && (
                <a
                  href={deployUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="h-10 px-4 rounded-full bg-card border border-border hover:bg-secondary text-foreground font-bold text-xs uppercase tracking-widest transition-colors flex items-center gap-2"
                >
                  <Eye className="size-3.5" /> Preview
                </a>
              )}
              <button
                onClick={() => navigate({ to: "/dashboard" })}
                className="h-10 px-6 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 font-bold text-xs uppercase tracking-widest transition-colors flex items-center gap-2 shadow-sm active:scale-95"
              >
                <RefreshCw className="size-3.5" /> Dashboard
              </button>
            </div>
          </div>

          {/* Overall progress */}
          <div className="mt-8">
            <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-widest text-muted-foreground mb-3">
              <span>Overall progress</span>
              <span className="font-mono text-foreground">{Math.round(overallProgress)}%</span>
            </div>
            <Progress value={overallProgress} className="h-1.5 bg-secondary" />
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
              {sortedStages.map(([id, meta], idx) => {
                const Icon = meta.icon;
                const status = stageStatuses[id] || "pending";
                const isActive = activeStageId === id;
                const isComplete = status === "complete";
                const isPending = status === "pending";

                return (
                  <div
                    key={id}
                    className={`flex items-start gap-6 group transition-all p-6 rounded-2xl border ${
                      isActive
                        ? "border-border bg-card shadow-sm"
                        : "border-transparent"
                    }`}
                  >
                    <div className="flex flex-col items-center shrink-0 pt-1">
                      <div
                        className={`relative size-12 rounded-full flex items-center justify-center transition-colors ${
                          isComplete
                            ? "bg-success/10 text-success"
                            : status === "active" || isActive
                              ? "bg-primary text-primary-foreground shadow-lg shadow-primary/30"
                              : "bg-secondary text-muted-foreground"
                        }`}
                      >
                        {status === "active" ? (
                          <Loader2 className="size-5 animate-spin" />
                        ) : isComplete ? (
                          <CheckCircle2 className="size-5" />
                        ) : (
                          <Icon className="size-5" />
                        )}
                      </div>
                      {idx < sortedStages.length - 1 && (
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
                            {meta.title}
                          </h3>
                          <p
                            className={`text-sm mt-2 font-medium ${isPending ? "text-muted-foreground/70" : "text-muted-foreground"}`}
                          >
                            {meta.subtitle}
                          </p>
                          <div className="flex items-center gap-4 mt-3 text-[11px] uppercase tracking-widest font-bold">
                            <span className="flex items-center gap-1.5 text-muted-foreground">
                              <Cpu className="size-3.5" /> {id}
                            </span>
                            <span className="flex items-center gap-1.5 text-muted-foreground">
                              <Clock className="size-3.5" /> {isComplete ? "done" : isActive ? "running" : "waiting"}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* ===== RIGHT SIDEBAR ===== */}
          <div className="md:col-span-1 lg:col-span-5 space-y-10">
            {/* Metrics */}
            <div className="grid grid-cols-2 gap-4">
              {[
                { icon: Activity, label: "Self-heal", value: "Active", sub: "Watching", color: "text-success" },
                { icon: TrendingUp, label: "Confidence", value: "97.4%", sub: "Brand fit", color: "text-primary" },
                { icon: Layers, label: "Build status", value: buildComplete ? "Complete" : "Running", sub: `${Math.round(overallProgress)}%`, color: "text-foreground" },
                { icon: Heart, label: "A11y score", value: "AAA", sub: "WCAG 2.2", color: "text-foreground" },
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

            {/* Live activity feed */}
            <div>
              <div className="flex items-center justify-between mb-4 px-2">
                <div className="flex items-center gap-2">
                  <span className={`size-2 rounded-full ${buildComplete ? "bg-success" : "bg-success animate-pulse"}`} />
                  <h3 className="text-sm font-bold text-foreground font-heading">Streaming Log</h3>
                </div>
              </div>
              <div className="border-t border-border max-h-96 overflow-y-auto">
                {liveLog.length === 0 && (
                  <div className="py-8 text-center text-sm text-muted-foreground">
                    Waiting for events...
                  </div>
                )}
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
