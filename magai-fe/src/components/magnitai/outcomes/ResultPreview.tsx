import { ArrowRight, Check, Trophy } from "lucide-react";

import type { OutcomeConfig, WidgetData } from "@/lib/api";

/**
 * The result screen as a visitor will see it.
 *
 * Rendered from the same configuration the deployed widget reads, in the tool's
 * own brand rather than in Magnit's — so what the owner is editing looks like
 * the thing that will be on their website, not like a settings form. The
 * preview is the argument that the editor is worth using.
 */
export function ResultPreview({
  config,
  widget,
  score = 86,
}: {
  config: OutcomeConfig;
  widget: WidgetData;
  /** Which band to demonstrate. The editor lets you step through them. */
  score?: number;
}) {
  const brand = (widget.brand_tokens ?? {}) as Record<string, string>;
  const background = brand.background_color ?? "#FFFFFF";
  const ink = brand.secondary_color ?? "#1F2430";
  const primary = brand.primary_color ?? ink;
  const headingFont = brand.font_headings ? `${brand.font_headings}, serif` : undefined;

  const ordered = [...config.bands].sort((a, b) => a.minimum_score - b.minimum_score);
  const band =
    ordered.find((item) => score >= item.minimum_score && score <= item.maximum_score) ??
    ordered[ordered.length - 1] ??
    null;

  const advice = config.advice.filter(
    (item) => !item.band_key || (band && item.band_key === band.key),
  );
  const accent = band?.accent_color ?? "#16A34A";

  return (
    <div
      className="overflow-hidden rounded-[1.15rem] border p-5 sm:p-6"
      style={{
        background,
        color: ink,
        borderColor: `color-mix(in srgb, ${primary} 16%, transparent)`,
        fontFamily: brand.font_body ? `${brand.font_body}, system-ui, sans-serif` : undefined,
      }}
    >
      <div className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
        <div className="text-center">
          <span
            className="mx-auto grid size-16 place-items-center rounded-full"
            style={{ background: `color-mix(in srgb, ${accent} 16%, transparent)` }}
          >
            <Trophy className="size-7" style={{ color: accent }} aria-hidden="true" />
          </span>

          <p className="mt-4 text-[11px] uppercase tracking-[0.14em] opacity-55">Your result</p>
          <h3
            className="mt-1 text-[clamp(1.6rem,3vw,2.1rem)] font-semibold leading-tight tracking-[-0.03em]"
            style={{ color: accent, fontFamily: headingFont }}
          >
            {band?.label ?? "Your result"}
          </h3>

          <p className="mt-3 text-[11px] uppercase tracking-[0.14em] opacity-55">Your score</p>
          <p className="tabular mt-0.5 text-3xl font-semibold tracking-[-0.04em]">
            {score}
            <span className="text-lg opacity-45"> / 100</span>
          </p>

          {band?.description && (
            <p className="mx-auto mt-4 max-w-[32ch] text-sm leading-6 opacity-75">
              {band.description}
            </p>
          )}
        </div>

        {advice.length > 0 && (
          <div>
            <p className="text-sm font-semibold" style={{ fontFamily: headingFont }}>
              Recommended for you
            </p>
            <ul className="mt-3 space-y-2">
              {advice.map((item, index) => (
                <li
                  key={`${item.text}-${index}`}
                  className="flex items-start gap-2.5 rounded-xl border p-3 text-sm leading-6"
                  style={{ borderColor: `color-mix(in srgb, ${primary} 14%, transparent)` }}
                >
                  <span
                    className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full"
                    style={{ background: accent, color: background }}
                  >
                    <Check className="size-3" aria-hidden="true" />
                  </span>
                  {item.text}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {config.email_capture.enabled && (
        <div
          className="mt-6 flex flex-col gap-3 rounded-2xl p-4 sm:flex-row sm:items-center sm:justify-between"
          style={{ background: `color-mix(in srgb, ${accent} 10%, transparent)` }}
        >
          <div className="min-w-0">
            <p className="text-sm font-semibold">{config.email_capture.heading}</p>
            <p className="mt-0.5 text-xs leading-5 opacity-70">{config.email_capture.subheading}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <span
              className="flex h-9 min-w-[10rem] items-center rounded-lg border px-3 text-xs opacity-55"
              style={{
                borderColor: `color-mix(in srgb, ${primary} 20%, transparent)`,
                background,
              }}
            >
              {config.email_capture.placeholder}
            </span>
            <span
              className="flex h-9 items-center rounded-lg px-3.5 text-xs font-semibold"
              style={{ background: accent, color: background }}
            >
              {config.email_capture.button_label}
            </span>
          </div>
        </div>
      )}

      {config.email_capture.consent_text && (
        <p className="mt-2 text-[11px] leading-4 opacity-55">{config.email_capture.consent_text}</p>
      )}

      {config.cta.label && (
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <span
            className="flex h-10 items-center gap-2 rounded-lg px-4 text-sm font-semibold"
            style={{ background: primary, color: background }}
          >
            {config.cta.label}
            <ArrowRight className="size-4" aria-hidden="true" />
          </span>
          {config.cta.note && <span className="text-xs opacity-60">{config.cta.note}</span>}
        </div>
      )}

      {config.next_steps.length > 0 && (
        <div className="mt-7">
          <p className="text-sm font-semibold" style={{ fontFamily: headingFont }}>
            Recommended next steps
          </p>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            {config.next_steps.map((step, index) => (
              <div
                key={`${step.title}-${index}`}
                className="rounded-xl border p-3.5"
                style={{ borderColor: `color-mix(in srgb, ${primary} 14%, transparent)` }}
              >
                <p className="text-sm font-medium">{step.title}</p>
                {step.description && (
                  <p className="mt-1 text-xs leading-5 opacity-70">{step.description}</p>
                )}
                {step.link_label && (
                  <p className="mt-2 text-xs font-medium" style={{ color: accent }}>
                    {step.link_label} →
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
