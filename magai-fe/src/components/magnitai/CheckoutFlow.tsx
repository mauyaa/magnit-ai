import React, { useState } from "react";
import { ArrowRight, ShieldCheck, Lock, Sparkles, AlertCircle, Loader2, CheckCircle2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { PageShell } from "@/components/magnitai/ui/PageShell";
import { SectionIntro } from "@/components/magnitai/ui/SectionIntro";
import { useAnalyzeUrl, useBuildWidget, type Blueprint } from "@/lib/api";

export function CheckoutFlow({
  onBuildStart,
  onBack,
}: {
  onBuildStart: (widgetId: string) => void;
  onBack: () => void;
}) {
  const [url, setUrl] = useState("https://strideos.com");
  const [urlError, setUrlError] = useState<string | null>(null);
  const [widgetId, setWidgetId] = useState<string | null>(null);
  const [blueprints, setBlueprints] = useState<Blueprint[] | null>(null);
  const [selectedBlueprint, setSelectedBlueprint] = useState<number | null>(null);
  const [buildStarted, setBuildStarted] = useState(false);

  const analyze = useAnalyzeUrl();
  const build = useBuildWidget();

  const validateUrl = (value: string): string | null => {
    if (!value.trim()) return "Enter your website URL to continue.";
    try {
      const parsed = new URL(value);
      if (!/^https?:$/.test(parsed.protocol)) {
        return "URL must start with http:// or https://.";
      }
      if (!parsed.hostname.includes(".")) {
        return "That doesn't look like a full domain — try including the .com/.io/etc.";
      }
    } catch {
      return "Enter a full URL, like https://yourcompany.com.";
    }
    return null;
  };

  const handleAnalyze = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const error = validateUrl(url);
    if (error) {
      setUrlError(error);
      return;
    }
    setUrlError(null);

    try {
      const result = await analyze.mutateAsync(url);
      setWidgetId(result.widget_id);
      setBlueprints(result.blueprints);
    } catch {
      setUrlError("Analysis failed. Check the URL and try again.");
    }
  };

  const [buildError, setBuildError] = useState<string | null>(null);

  const handleBuild = async (index: number) => {
    if (!widgetId) return;
    setSelectedBlueprint(index);
    setBuildError(null);
    try {
      await build.mutateAsync({ widgetId, blueprintIndex: index });
      setBuildStarted(true);
      onBuildStart(widgetId);
    } catch (err) {
      setSelectedBlueprint(null);
      setBuildError(err instanceof Error ? err.message : "Build failed");
    }
  };

  const step = blueprints ? "select" : "input";

  return (
    <PageShell maxWidth="3xl">
      <button
        onClick={onBack}
        className="mb-10 flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground transition-colors group"
        aria-label="Go back"
      >
        <span className="transition-transform group-hover:-translate-x-0.5">←</span> Back
      </button>
      <SectionIntro
        eyebrow="Zero Overwhelm"
        heading={
          <>
            Deploy your <span className="hero-accent">self-healing widget.</span>
          </>
        }
        body="No complex developer tokens required. Magnitai extracts your CSS tokens automatically."
        className="mb-16"
      />

      <AnimatePresence mode="wait">
        {step === "input" && (
          <motion.div
            key="input"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <div className="bg-card border border-border p-10 md:p-14 shadow-sm rounded-2xl">
              <form onSubmit={handleAnalyze} noValidate className="space-y-10">
                <div className="space-y-4">
                  <label
                    htmlFor="checkout-url"
                    className="text-sm font-bold text-foreground flex items-center gap-3 font-heading uppercase tracking-widest"
                  >
                    <span
                      aria-hidden="true"
                      className="flex size-6 items-center justify-center rounded-full bg-foreground text-background text-[11px]"
                    >
                      1
                    </span>
                    <span>Your Website URL</span>
                  </label>
                  <input
                    id="checkout-url"
                    name="url"
                    type="url"
                    value={url}
                    onChange={(e) => {
                      setUrl(e.target.value);
                      if (urlError) setUrlError(validateUrl(e.target.value));
                    }}
                    onBlur={() => setUrlError(validateUrl(url))}
                    placeholder="https://yourcompany.com"
                    required
                    aria-invalid={urlError ? true : undefined}
                    className={`w-full h-14 bg-transparent border-b transition-colors font-mono text-lg outline-none placeholder:text-muted-foreground/50 ${
                      urlError ? "border-destructive focus:border-destructive" : "border-border/50 focus:border-foreground"
                    }`}
                  />
                  {urlError ? (
                    <span role="alert" className="flex items-center gap-1.5 pt-2 text-xs font-bold text-destructive">
                      <AlertCircle className="size-3.5" /> {urlError}
                    </span>
                  ) : (
                    <span className="eyebrow flex items-center gap-1.5 pt-2">
                      <ShieldCheck className="size-3.5 text-success" /> Securely reads layout &amp; color styles
                    </span>
                  )}
                </div>

                <div className="rounded-xl bg-secondary/50 border border-border/50 p-6 flex items-start gap-4">
                  <Sparkles className="size-5 text-primary shrink-0 mt-0.5" />
                  <div className="space-y-1.5">
                    <h4 className="text-sm font-bold text-foreground font-heading">
                      Magnitai Pro Guard Included
                    </h4>
                    <p className="text-sm text-muted-foreground font-medium leading-relaxed">
                      Your widget includes real-time Antigravity DOM self-healing. If you redesign your
                      site tomorrow, Magnitai updates your widget automatically.
                    </p>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={analyze.isPending}
                  className="group flex h-16 w-full items-center justify-center gap-3 rounded-2xl text-lg font-bold bg-foreground text-background hover:bg-primary shadow-sm transition-all hover:-translate-y-0.5 disabled:opacity-80 disabled:pointer-events-none"
                >
                  {analyze.isPending ? (
                    <span className="flex items-center gap-2">
                      <Loader2 className="size-5 animate-spin" />
                      <span className="tracking-widest uppercase text-sm">Analyzing…</span>
                    </span>
                  ) : (
                    <>
                      <span>Analyze my site</span>
                      <ArrowRight className="size-5 transition-transform group-hover:translate-x-1" />
                    </>
                  )}
                </button>
              </form>

              <div className="flex flex-wrap justify-between items-center pt-8 mt-10 border-t border-border/50 text-[11px] font-bold uppercase tracking-widest text-muted-foreground gap-4">
                <div className="flex items-center gap-2">
                  <Lock className="size-3.5" />
                  <span>256-bit SSL encrypted</span>
                </div>
                <div className="flex items-center gap-4">
                  <span>14-day guarantee</span>
                  <span className="text-border" aria-hidden="true">|</span>
                  <span>Instant webhooks</span>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {step === "select" && blueprints && (
          <motion.div
            key="select"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-6"
          >
            <div className="bg-card border border-border p-10 md:p-14 shadow-sm rounded-2xl">
              <h3 className="font-heading text-2xl font-medium text-foreground mb-2">
                Choose your widget
              </h3>
              <p className="text-muted-foreground font-medium mb-10">
                Magnitai analyzed your site and recommends these 3 widgets. Pick one to build.
              </p>

              {buildError && (
                <div role="alert" className="flex items-center gap-2 px-4 py-3 rounded-xl bg-destructive/10 border border-destructive/30 text-sm font-semibold text-destructive mb-4">
                  <AlertCircle className="size-4 shrink-0" />
                  {buildError}
                </div>
              )}

              <div className="space-y-4">
                {blueprints.map((bp, i) => (
                  <motion.button
                    key={i}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0, transition: { delay: i * 0.1 } }}
                    onClick={() => handleBuild(i)}
                    disabled={build.isPending && selectedBlueprint === i}
                    className={`w-full text-left rounded-2xl border p-6 transition-all hover:-translate-y-0.5 active:scale-[0.99] ${
                      selectedBlueprint === i && build.isPending
                        ? "border-primary bg-primary/5"
                        : "border-border bg-card hover:border-primary/40 hover:shadow-sm"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <span className="size-7 rounded-full bg-foreground text-background text-xs font-bold flex items-center justify-center">
                            {i + 1}
                          </span>
                          <h4 className="font-heading text-lg font-semibold text-foreground">
                            {bp.title}
                          </h4>
                          <span className="text-[10px] uppercase tracking-widest font-bold px-2.5 py-1 rounded-full bg-primary/10 text-primary">
                            {bp.type.replace(/_/g, " ")}
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground font-medium leading-relaxed">
                          {bp.description}
                        </p>
                        <p className="text-xs text-muted-foreground/70 mt-2 italic">
                          {bp.rationale}
                        </p>
                      </div>
                      <div className="shrink-0">
                        {selectedBlueprint === i && build.isPending ? (
                          <Loader2 className="size-5 animate-spin text-primary" />
                        ) : (
                          <ArrowRight className="size-5 text-muted-foreground group-hover:text-primary transition-colors" />
                        )}
                      </div>
                    </div>
                  </motion.button>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </PageShell>
  );
}
