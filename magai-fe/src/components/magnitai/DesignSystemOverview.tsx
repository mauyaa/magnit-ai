import React from "react";
import { Sparkles, Layers, Type, Palette, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";

import { PageShell } from "@/components/magnitai/ui/PageShell";

const colorTokens = [
  { name: "Primary", token: "--primary", desc: "Committed coral · primary actions and links" },
  {
    name: "Foreground",
    token: "--foreground",
    desc: "Deep warm ink · headlines and high-emphasis text",
  },
  {
    name: "Background",
    token: "--background",
    desc: "Warm cream canvas · page surface",
  },
  { name: "Secondary", token: "--secondary", desc: "Warm peach surface · chips, alternating sections" },
  { name: "Muted", token: "--muted", desc: "Quiet surface · low-emphasis panels" },
  {
    name: "Accent (violet)",
    token: "--accent-violet",
    desc: "Reserved for the logo mark only · never a dominant surface",
  },
  { name: "Success", token: "--success", desc: "Teal · self-heal confirmations" },
  { name: "Warning", token: "--warning", desc: "Amber · attention states, distinct hue from primary" },
  { name: "Destructive", token: "--destructive", desc: "Errors and irreversible actions" },
];

export function DesignSystemOverview() {
  return (
    <PageShell className="space-y-16">
      <div className="max-w-3xl">
        <Badge className="bg-secondary text-secondary-foreground border border-border mb-3 px-3 py-1 text-xs font-bold uppercase tracking-wider font-mono">
          Magnitai Design System
        </Badge>
        <h2 className="font-heading text-4xl font-medium leading-[1.02] tracking-[-0.045em] text-foreground sm:text-5xl">
          Warm cream canvas. One committed coral accent.
        </h2>
        <p className="mt-4 text-base text-muted-foreground leading-relaxed">
          Every color below is read live from the CSS custom properties in{" "}
          <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[13px] text-foreground">
            styles.css
          </code>{" "}
          — this page can never drift out of sync with the app, because it doesn&apos;t hardcode a
          single hex value.
        </p>
      </div>

      {/* Color tokens */}
      <div className="space-y-6">
        <div className="flex items-center gap-2 border-b border-border pb-3 text-sm font-bold uppercase tracking-widest text-muted-foreground">
          <Palette className="size-4 text-primary" />
          <span>Semantic OKLCH palette</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {colorTokens.map((c) => (
            <div
              key={c.token}
              className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm transition-all hover:shadow-lg hover:-translate-y-1"
            >
              <div
                className="h-24 w-full border-b border-border"
                style={{ backgroundColor: `var(${c.token})` }}
              />
              <div className="p-5 space-y-2">
                <div className="flex justify-between items-center gap-3">
                  <span className="font-semibold text-foreground font-heading">{c.name}</span>
                  <code className="rounded bg-muted px-2 py-0.5 text-xs font-mono text-muted-foreground shrink-0">
                    {c.token}
                  </code>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">{c.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Typography */}
      <div className="space-y-6">
        <div className="flex items-center gap-2 border-b border-border pb-3 text-sm font-bold uppercase tracking-widest text-muted-foreground">
          <Type className="size-4 text-primary" />
          <span>Typography</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 rounded-2xl border border-border bg-card p-8 shadow-sm">
          <div className="space-y-4 border-b md:border-b-0 md:border-r border-border/50 pb-6 md:pb-0 md:pr-8">
            <span className="eyebrow text-primary">Headings · Geist Sans</span>
            <div className="font-heading text-5xl font-medium tracking-tight text-foreground">
              Geist 500
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Large display type stays at medium weight, never bold — confident at 500 reads as
              considered, not shouty. Emphasis comes from a solid{" "}
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">.hero-accent</code>{" "}
              underline, never a gradient fill on text.
            </p>
          </div>

          <div className="space-y-4">
            <span className="eyebrow text-primary">Body &amp; UI · Geist Sans</span>
            <div className="font-sans text-3xl font-medium text-foreground">
              Geist 400
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">
              One family across headings, body, and UI — weight and size carry hierarchy, not a
              second typeface.{" "}
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">Geist Mono</code>{" "}
              handles numerals, timestamps, and data.
            </p>
          </div>
        </div>
      </div>

      {/* Principles */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="rounded-2xl border border-border bg-card p-6 shadow-sm space-y-3">
          <div className="size-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
            <Sparkles className="size-5" />
          </div>
          <h4 className="font-semibold text-foreground font-heading">Quiet intelligence</h4>
          <p className="text-xs text-muted-foreground leading-relaxed">
            No neon terminals or gimmick cyber-text. AI activity is shown like a calm, high-end
            build log.
          </p>
        </div>

        <div className="rounded-2xl border border-border bg-card p-6 shadow-sm space-y-3">
          <div className="size-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
            <ShieldCheck className="size-5" />
          </div>
          <h4 className="font-semibold text-foreground font-heading">One accent, used sparingly</h4>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Primary coral carries every call-to-action and active state. Violet is reserved for the
            logo mark only. Success/warning/destructive are strictly status — never decoration.
          </p>
        </div>

        <div className="rounded-2xl border border-border bg-card p-6 shadow-sm space-y-3">
          <div className="size-10 rounded-xl bg-success/10 text-success flex items-center justify-center">
            <Layers className="size-5" />
          </div>
          <h4 className="font-semibold text-foreground font-heading">Tokens, not hex</h4>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Every surface, border, and status color resolves to a CSS variable in{" "}
            <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px]">styles.css</code> —
            no component hardcodes a Tailwind palette color like{" "}
            <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px]">emerald-600</code>{" "}
            or a raw{" "}
            <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px]">black/N</code>{" "}
            opacity.
          </p>
        </div>
      </div>
    </PageShell>
  );
}
