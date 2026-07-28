import { useEffect, useRef, useState } from "react";

/**
 * The product, demonstrated rather than described.
 *
 * One calculator, re-skinned into a different business's identity every few
 * seconds — colour, typeface, corner radius, wording all move together, because
 * that is exactly what the Architect stage extracts from a real site. Claiming
 * "on-brand" in a paragraph asks for trust; showing the same tool wearing four
 * different brands earns it in about eight seconds.
 *
 * The skins are archetypes ("a dental clinic"), never invented companies — a
 * fake logo and a fake testimonial are the same lie at different sizes.
 */

interface Skin {
  trade: string;
  bg: string;
  ink: string;
  accent: string;
  surface: string;
  headingFont: string;
  bodyFont: string;
  radius: string;
  weight: number;
  tracking: string;
  question: string;
  unit: string;
  result: string;
  cta: string;
  rate: number;
  /** True when the card's own ground is dark, so its edge needs a light rim
      instead of a dark one to separate it from the stage behind it. */
  darkCard?: boolean;
}

const SKINS: Skin[] = [
  {
    trade: "a dental clinic",
    bg: "#F7FAFC",
    ink: "#12303F",
    // Accents are all >= 4.5:1 against their own surface: the CTA label is
    // normal-size text sitting directly on the accent, so a pretty-but-pale
    // brand colour here would ship an inaccessible button in every demo.
    accent: "#0B6F87",
    surface: "#FFFFFF",
    headingFont: "'Iowan Old Style', 'Palatino Linotype', Palatino, Georgia, serif",
    bodyFont: "system-ui, sans-serif",
    radius: "14px",
    weight: 600,
    tracking: "-0.02em",
    question: "New patients each month",
    unit: "patients",
    result: "Additional yearly revenue",
    cta: "Get my practice report",
    rate: 2100,
  },
  {
    trade: "a law firm",
    bg: "#FBFAF7",
    ink: "#1C1B18",
    accent: "#7A5F35",
    surface: "#FFFFFF",
    headingFont: "'Times New Roman', Times, serif",
    bodyFont: "'Iowan Old Style', Georgia, serif",
    radius: "2px",
    weight: 400,
    tracking: "0.01em",
    question: "Matters opened each month",
    unit: "matters",
    result: "Billable value at stake",
    cta: "Request the analysis",
    rate: 8400,
  },
  {
    trade: "a fitness studio",
    bg: "#111113",
    ink: "#F4F4F5",
    accent: "#C6FF3D",
    surface: "#1B1B1F",
    headingFont: "'Helvetica Neue', Helvetica, Arial, sans-serif",
    bodyFont: "'Helvetica Neue', Helvetica, Arial, sans-serif",
    radius: "999px",
    weight: 800,
    tracking: "-0.03em",
    question: "Members signed up monthly",
    unit: "members",
    result: "Yearly membership value",
    cta: "Show me the numbers",
    rate: 1150,
    darkCard: true,
  },
  {
    trade: "a solar installer",
    bg: "#FFFDF6",
    ink: "#2A2410",
    accent: "#B25A05",
    surface: "#FFFFFF",
    headingFont: "system-ui, sans-serif",
    bodyFont: "system-ui, sans-serif",
    radius: "20px",
    weight: 700,
    tracking: "-0.025em",
    question: "Homes quoted each month",
    unit: "homes",
    result: "Annual install value",
    cta: "Send me my estimate",
    rate: 11500,
  },
];

const HOLD_MS = 5200;

export function InteractiveWidgetDemo() {
  const [index, setIndex] = useState(0);
  const [count, setCount] = useState(24);
  const [paused, setPaused] = useState(false);
  const touched = useRef(false);

  // Rotating stops for good once the visitor takes the controls — at that point
  // they're evaluating the tool, and moving it out from under them is hostile.
  useEffect(() => {
    if (paused || touched.current) return;
    const t = setTimeout(() => setIndex((i) => (i + 1) % SKINS.length), HOLD_MS);
    return () => clearTimeout(t);
  }, [index, paused]);

  const skin = SKINS[index];
  const total = count * skin.rate * 12;

  return (
    <div
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      className="w-full"
    >
      {/*
       * The card is cross-faded by opacity on a keyed wrapper rather than by
       * tw-animate-css. That utility ran with animation-fill-mode: none, so the
       * card sat at opacity 0 before the animation started and snapped back
       * after it — which is how the single most important element on the
       * landing page shipped looking like a ghost.
       */}
      <div
        key={index}
        className="motion-safe:animate-[demoFade_420ms_ease-out_both]"
        style={{
          background: skin.bg,
          color: skin.ink,
          borderRadius: skin.radius === "999px" ? "28px" : skin.radius,
          fontFamily: skin.bodyFont,
          padding: "2rem",
          boxShadow: skin.darkCard
            ? "0 0 0 1px rgba(255,255,255,0.14), 0 24px 60px rgba(0,0,0,0.45)"
            : "0 0 0 1px rgba(0,0,0,0.06), 0 24px 60px rgba(0,0,0,0.35)",
        }}
      >
        <div
          className="text-[27px] leading-tight"
          style={{
            fontFamily: skin.headingFont,
            fontWeight: skin.weight,
            letterSpacing: skin.tracking,
          }}
        >
          What is your growth worth?
        </div>

        <div className="mt-8 flex items-baseline justify-between gap-4 text-sm">
          <span style={{ opacity: 0.7 }}>{skin.question}</span>
          <span className="tabular font-mono">{count}</span>
        </div>

        <input
          type="range"
          min={1}
          max={80}
          value={count}
          aria-label={skin.question}
          onChange={(e) => {
            touched.current = true;
            setCount(Number(e.target.value));
          }}
          className="mt-2 h-11 w-full cursor-pointer bg-transparent"
          style={{ accentColor: skin.accent }}
        />

        <div className="mt-2 border-t pt-6" style={{ borderColor: `${skin.ink}22` }}>
          <div
            className="tabular text-[44px] leading-none"
            style={{
              color: skin.accent,
              fontFamily: skin.headingFont,
              fontWeight: skin.weight,
              letterSpacing: skin.tracking,
            }}
          >
            ${total.toLocaleString()}
          </div>
          <div className="mt-2 text-xs" style={{ opacity: 0.65 }}>
            {skin.result} · {count} {skin.unit}/month
          </div>
        </div>

        <div
          className="mt-7 flex h-12 items-center justify-center text-sm font-semibold"
          style={{
            background: skin.accent,
            color: skin.bg,
            borderRadius: skin.radius === "2px" ? "2px" : skin.radius,
          }}
        >
          {skin.cta}
        </div>
      </div>

      {/* The caption sits on the dark stage, so it is written in light values. */}
      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <span className="text-sm text-white/55">
          The same tool, built for <span className="text-white">{skin.trade}</span>
        </span>
        <span className="flex items-center gap-2" role="tablist" aria-label="Example brands">
          {SKINS.map((s, i) => (
            <button
              key={s.trade}
              role="tab"
              aria-selected={i === index}
              aria-label={`Show ${s.trade}`}
              onClick={() => {
                touched.current = true;
                setIndex(i);
              }}
              className="h-1.5 rounded-full transition-all duration-300"
              style={{
                width: i === index ? "1.5rem" : "0.375rem",
                background: i === index ? "var(--brand)" : "rgba(255,255,255,0.28)",
              }}
            />
          ))}
        </span>
      </div>
    </div>
  );
}
