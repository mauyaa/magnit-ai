import React, { useEffect, useRef, useState } from "react";
import { ArrowRight, ShieldCheck, Lock, Sparkles, AlertCircle } from "lucide-react";
import { motion } from "framer-motion";
import { PageShell } from "@/components/magnitai/ui/PageShell";
import { SectionIntro } from "@/components/magnitai/ui/SectionIntro";

export function CheckoutFlow({
  onComplete,
  onBack,
}: {
  onComplete: () => void;
  onBack: () => void;
}) {
  const [url, setUrl] = useState("https://strideos.com");
  const [prompt, setPrompt] = useState(
    "An interactive ROI calculator showing how much time teams save with StrideOS.",
  );
  const [urlError, setUrlError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const timers = useRef<number[]>([]);

  useEffect(
    () => () => {
      timers.current.forEach((timer) => window.clearTimeout(timer));
    },
    [],
  );

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

  const handleUrlChange = (value: string) => {
    setUrl(value);
    if (urlError) setUrlError(validateUrl(value));
  };

  const handleBuild = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const error = validateUrl(url);
    if (error) {
      setUrlError(error);
      return;
    }
    setUrlError(null);
    setIsSubmitting(true);
    timers.current.push(
      window.setTimeout(() => {
        setIsSubmitting(false);
        setIsSuccess(true);
        timers.current.push(
          window.setTimeout(() => {
            onComplete();
          }, 650),
        );
      }, 850),
    );
  };

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

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-card border border-border p-10 md:p-14 shadow-sm rounded-2xl"
      >
        <form onSubmit={handleBuild} noValidate className="space-y-10">
          {/* Step 1 */}
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
              <span>Host Website URL</span>
            </label>
            <input
              id="checkout-url"
              name="url"
              type="url"
              value={url}
              onChange={(e) => handleUrlChange(e.target.value)}
              onBlur={() => setUrlError(validateUrl(url))}
              placeholder="https://yourcompany.com"
              required
              aria-invalid={urlError ? true : undefined}
              aria-describedby={urlError ? "checkout-url-error" : "checkout-url-hint"}
              className={`w-full h-14 bg-transparent border-b transition-colors font-mono text-lg outline-none placeholder:text-muted-foreground/50 ${
                urlError ? "border-destructive focus:border-destructive" : "border-border/50 focus:border-foreground"
              }`}
            />
            {urlError ? (
              <span
                id="checkout-url-error"
                role="alert"
                className="flex items-center gap-1.5 pt-2 text-xs font-bold text-destructive"
              >
                <AlertCircle className="size-3.5" /> {urlError}
              </span>
            ) : (
              <span id="checkout-url-hint" className="eyebrow flex items-center gap-1.5 pt-2">
                <ShieldCheck className="size-3.5 text-success" /> Securely reads layout &amp; color
                styles
              </span>
            )}
          </div>

          {/* Step 2 */}
          <div className="space-y-4">
            <label
              htmlFor="checkout-prompt"
              className="text-sm font-bold text-foreground flex items-center gap-3 font-heading uppercase tracking-widest"
            >
              <span
                aria-hidden="true"
                className="flex size-6 items-center justify-center rounded-full bg-foreground text-background text-[11px]"
              >
                2
              </span>
              <span>Widget Idea (Plain English)</span>
            </label>
            <textarea
              id="checkout-prompt"
              name="prompt"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={3}
              required
              className="w-full bg-transparent border-b border-border/50 focus:border-foreground transition-colors text-lg outline-none font-medium resize-none placeholder:text-muted-foreground/50 pt-2"
              placeholder="E.g., A 4-question onboarding quiz..."
            />
          </div>

          {/* Plan Guarantee Banner */}
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
            disabled={isSubmitting || isSuccess}
            aria-busy={isSubmitting}
            className={`group flex h-16 w-full items-center justify-center gap-3 rounded-2xl text-lg font-bold shadow-[0_14px_34px_-16px_rgba(24,68,118,.5)] transition-all hover:-translate-y-0.5 disabled:pointer-events-none ${
              isSuccess
                ? "bg-success text-white"
                : "bg-foreground text-background hover:bg-primary disabled:opacity-80"
            }`}
          >
            {isSuccess ? (
              <span className="flex items-center gap-2">
                <span>✓</span>
                <span className="tracking-widest uppercase text-sm">
                  Tokens extracted — launching build
                </span>
              </span>
            ) : isSubmitting ? (
              <span className="animate-pulse tracking-widest uppercase text-sm">
                Extracting tokens…
              </span>
            ) : (
              <>
                <span>Start live AI build</span>
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
            <span className="text-border" aria-hidden="true">
              |
            </span>
            <span>Instant webhooks</span>
          </div>
        </div>
      </motion.div>
    </PageShell>
  );
}
