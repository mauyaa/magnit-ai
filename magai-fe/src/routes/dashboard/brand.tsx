import { createFileRoute, Link } from "@tanstack/react-router";
import {
  AlertCircle,
  ArrowRight,
  Check,
  CheckCircle2,
  ImageIcon,
  Laptop,
  Loader2,
  Monitor,
  RotateCcw,
  Smartphone,
  Sparkles,
  Undo2,
} from "lucide-react";
import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";

import { RequireAuth } from "@/components/magnitai/RequireAuth";
import { WorkspaceShell } from "@/components/magnitai/shell/WorkspaceShell";
import { useSaveWorkspaceBrand, useWorkspaceBrand, type WorkspaceBrand } from "@/lib/api";
import { PlanGate } from "@/lib/plan";

export const Route = createFileRoute("/dashboard/brand")({
  head: () => ({ meta: [{ title: "Brand · Magnitai" }] }),
  component: () => (
    <RequireAuth>
      <BrandScreen />
    </RequireAuth>
  ),
});

const HEX_COLOR = /^#(?:[0-9A-F]{3}|[0-9A-F]{6})$/i;
const HTTP_URL = /^https?:\/\/\S+$/i;

const FIELD =
  "h-11 w-full rounded-lg border border-border-strong bg-card px-3.5 text-sm text-foreground outline-none transition-colors placeholder:text-n-400 focus:border-foreground/50";

const TEXTAREA =
  "min-h-28 w-full resize-y rounded-lg border border-border-strong bg-card px-3.5 py-3 text-sm leading-6 text-foreground outline-none transition-colors placeholder:text-n-400 focus:border-foreground/50";

const TONES: Array<{
  id: "light" | "soft" | "deep";
  label: string;
  note: string;
  swatch: string;
}> = [
  { id: "light", label: "Light", note: "Clean and airy", swatch: "#FFFFFF" },
  { id: "soft", label: "Soft", note: "Warm and inviting", swatch: "#FAF7F2" },
  { id: "deep", label: "Deep", note: "Bold and focused", swatch: "#12151A" },
];

const ACCENT_PRESETS = [
  { label: "Cedar", value: "#45604F" },
  { label: "Clay", value: "#B65C3A" },
  { label: "Cobalt", value: "#3155D9" },
  { label: "Plum", value: "#7C3E70" },
  { label: "Gold", value: "#A16B17" },
  { label: "Ink", value: "#12151A" },
];

const RADII = [0, 4, 8, 12, 16, 24];

const VOICE_STARTERS = [
  "Calm, trustworthy, and clarity-driven",
  "Warm, conversational, and encouraging",
  "Direct, expert, and outcome-focused",
  "Premium, considered, and understated",
  "Technical, precise, and reassuring",
];

type Draft = Pick<
  WorkspaceBrand,
  | "accent_color"
  | "background_color"
  | "font_pairing"
  | "corner_radius"
  | "tone"
  | "logo_url"
  | "brand_personality"
>;

type PreviewMode = "question" | "result" | "lead";
type PreviewDevice = "desktop" | "mobile";

function toDraft(brand: WorkspaceBrand): Draft {
  return {
    accent_color: brand.accent_color,
    background_color: brand.background_color,
    font_pairing: brand.font_pairing,
    corner_radius: brand.corner_radius,
    tone: brand.tone,
    logo_url: brand.logo_url,
    brand_personality: brand.brand_personality,
  };
}

function emptyDraft(): Draft {
  return {
    accent_color: null,
    background_color: null,
    font_pairing: null,
    corner_radius: null,
    tone: null,
    logo_url: null,
    brand_personality: null,
  };
}

function safeHex(value: string | null, fallback: string): string {
  return value && HEX_COLOR.test(value) ? value : fallback;
}

function expandHex(value: string): string {
  const raw = value.replace("#", "");
  if (raw.length === 3) {
    return `#${raw
      .split("")
      .map((character) => `${character}${character}`)
      .join("")}`;
  }
  return `#${raw}`;
}

function relativeLuminance(value: string): number {
  const hex = expandHex(value);
  const channels = [hex.slice(1, 3), hex.slice(3, 5), hex.slice(5, 7)].map((channel) => {
    const normalized = Number.parseInt(channel, 16) / 255;
    return normalized <= 0.04045 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function contrastRatio(first: string, second: string): number {
  const a = relativeLuminance(first);
  const b = relativeLuminance(second);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

function readableInk(background: string): string {
  return contrastRatio(background, "#12151A") >= contrastRatio(background, "#FFFFFF")
    ? "#12151A"
    : "#FFFFFF";
}

function effectiveBackground(draft: Draft): string {
  if (draft.background_color && HEX_COLOR.test(draft.background_color)) {
    return draft.background_color;
  }
  return TONES.find((tone) => tone.id === draft.tone)?.swatch ?? "#F7F5EE";
}

function pinnedDecisionCount(draft: Draft): number {
  return [
    Boolean(draft.accent_color),
    Boolean(draft.background_color || draft.tone),
    Boolean(draft.font_pairing),
    draft.corner_radius !== null,
    Boolean(draft.logo_url),
    Boolean(draft.brand_personality),
  ].filter(Boolean).length;
}

function _SectionHeading({
  number,
  title,
  description,
  action,
}: {
  number: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex items-start gap-3">
      <span className="tabular mt-0.5 grid size-7 shrink-0 place-items-center rounded-full border border-border-strong font-mono text-xs text-muted-foreground">
        {number}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <h2 className="text-subheading text-foreground">{title}</h2>
          {action}
        </div>
        <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}

function FollowWebsiteButton({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex min-h-8 items-center gap-1.5 rounded-md px-2 text-xs font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
    >
      <RotateCcw className="size-3.5" aria-hidden="true" />
      {children}
    </button>
  );
}

function ColourField({
  label,
  value,
  fallback,
  placeholder,
  error,
  onChange,
}: {
  label: string;
  value: string | null;
  fallback: string;
  placeholder: string;
  error?: string | null;
  onChange: (value: string | null) => void;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-foreground">{label}</span>
      <span className="flex items-center gap-2">
        <input
          type="color"
          value={safeHex(value, fallback)}
          aria-label={`${label} picker`}
          onChange={(event) => onChange(event.target.value.toUpperCase())}
          className="size-11 shrink-0 cursor-pointer rounded-lg border border-border-strong bg-card p-1.5"
        />
        <input
          value={value ?? ""}
          placeholder={placeholder}
          aria-label={`${label} hex`}
          aria-invalid={Boolean(error)}
          onChange={(event) => onChange(event.target.value.toUpperCase() || null)}
          className={`${FIELD} max-w-40 font-mono ${error ? "border-destructive" : ""}`}
        />
      </span>
      {error && (
        <span role="alert" className="mt-1.5 block text-xs text-destructive">
          {error}
        </span>
      )}
    </label>
  );
}

function BrandMark({ logoUrl, accent }: { logoUrl: string | null; accent: string }) {
  const [failed, setFailed] = useState(false);

  useEffect(() => setFailed(false), [logoUrl]);

  if (logoUrl && HTTP_URL.test(logoUrl) && !failed) {
    return (
      <img
        src={logoUrl}
        alt=""
        onError={() => setFailed(true)}
        className="h-7 max-w-32 object-contain object-left"
      />
    );
  }

  return (
    <span
      className="grid size-8 place-items-center text-xs font-semibold"
      style={{ borderRadius: "32%", background: accent, color: readableInk(accent) }}
      aria-hidden="true"
    >
      M
    </span>
  );
}

function PreviewQuestion({
  accent,
  accentInk,
  ink,
  radius,
}: {
  accent: string;
  accentInk: string;
  ink: string;
  radius: string;
}) {
  return (
    <>
      <div className="flex items-center justify-between gap-4">
        <p className="group-label opacity-55">Question 2 of 5</p>
        <p className="text-xs opacity-55">40% complete</p>
      </div>
      <div className="mt-2 h-1 overflow-hidden rounded-full bg-current opacity-15">
        <span className="block h-full w-2/5 rounded-full" style={{ background: accent }} />
      </div>

      <div className="mt-8">
        <p className="text-sm font-medium opacity-60">Team & operations</p>
        <h3 className="mt-2 max-w-xl text-[clamp(1.8rem,3vw,2.8rem)] font-semibold leading-[1.02] tracking-[-0.04em]">
          What is the biggest constraint on your growth right now?
        </h3>
        <p className="mt-3 max-w-lg text-sm leading-6 opacity-65">
          Choose the answer that feels most true today. You can change it later.
        </p>
      </div>

      <div className="mt-7 grid gap-2.5 sm:grid-cols-2">
        {[
          "Not enough qualified leads",
          "Too much manual follow-up",
          "Unclear buyer intent",
          "A slow sales cycle",
        ].map((option, index) => (
          <div
            key={option}
            className="flex min-h-14 items-center gap-3 border px-3.5 py-3 text-sm font-medium"
            style={{
              borderRadius: radius,
              borderColor: index === 1 ? accent : `${ink}2A`,
              background: index === 1 ? `${accent}18` : "transparent",
            }}
          >
            <span
              className="grid size-5 shrink-0 place-items-center rounded-full border"
              style={{ borderColor: index === 1 ? accent : `${ink}4D` }}
            >
              {index === 1 && (
                <span className="size-2.5 rounded-full" style={{ background: accent }} />
              )}
            </span>
            {option}
          </div>
        ))}
      </div>

      <div className="mt-8 flex items-center justify-between gap-4">
        <span className="text-xs opacity-50">Takes about 2 minutes</span>
        <span
          className="inline-flex h-11 items-center gap-2 px-5 text-sm font-semibold"
          style={{ borderRadius: radius, background: accent, color: accentInk }}
        >
          Continue
          <ArrowRight className="size-4" aria-hidden="true" />
        </span>
      </div>
    </>
  );
}

function PreviewResult({
  accent,
  accentInk,
  ink,
  radius,
}: {
  accent: string;
  accentInk: string;
  ink: string;
  radius: string;
}) {
  return (
    <div className="py-2">
      <span
        className="inline-flex size-11 items-center justify-center"
        style={{ borderRadius: radius, background: `${accent}22`, color: accent }}
      >
        <Check className="size-5" strokeWidth={2.4} aria-hidden="true" />
      </span>
      <p className="mt-7 group-label opacity-55">Your readiness result</p>
      <div className="mt-3 flex flex-wrap items-end gap-x-5 gap-y-2">
        <p className="tabular text-7xl font-semibold leading-none tracking-[-0.065em]">82</p>
        <p className="pb-1 text-sm opacity-60">out of 100</p>
      </div>
      <h3 className="mt-7 max-w-xl text-[clamp(1.8rem,3vw,2.8rem)] font-semibold leading-[1.02] tracking-[-0.04em]">
        You have a strong foundation for scalable growth.
      </h3>
      <p className="mt-3 max-w-xl text-sm leading-6 opacity-65">
        Your clearest next win is removing manual follow-up from the first 24 hours of the buyer
        journey.
      </p>

      <div
        className="mt-7 grid gap-3 border p-4 sm:grid-cols-[1fr_auto] sm:items-center"
        style={{ borderRadius: radius, borderColor: `${ink}24`, background: `${ink}08` }}
      >
        <div>
          <p className="text-sm font-semibold">Recommended next step</p>
          <p className="mt-1 text-xs leading-5 opacity-60">
            Build a qualification tool around your highest-value customer.
          </p>
        </div>
        <span
          className="inline-flex h-10 items-center justify-center px-4 text-sm font-semibold"
          style={{ borderRadius: radius, background: accent, color: accentInk }}
        >
          See my plan
        </span>
      </div>
    </div>
  );
}

function PreviewLead({
  accent,
  accentInk,
  ink,
  radius,
}: {
  accent: string;
  accentInk: string;
  ink: string;
  radius: string;
}) {
  return (
    <div className="mx-auto max-w-xl py-3">
      <p className="group-label opacity-55">Your action plan is ready</p>
      <h3 className="mt-3 text-[clamp(1.8rem,3vw,2.8rem)] font-semibold leading-[1.02] tracking-[-0.04em]">
        Where should we send your personalised recommendations?
      </h3>
      <p className="mt-3 text-sm leading-6 opacity-65">
        Get the complete breakdown, including the three actions likely to make the biggest
        difference.
      </p>

      <div className="mt-7 grid gap-3 sm:grid-cols-2">
        {[
          ["Name", "Alex Morgan"],
          ["Work email", "alex@company.com"],
        ].map(([label, value]) => (
          <div key={label}>
            <p className="mb-1.5 text-xs font-medium">{label}</p>
            <div
              className="flex h-11 items-center border px-3.5 text-sm opacity-60"
              style={{ borderRadius: radius, borderColor: `${ink}35` }}
            >
              {value}
            </div>
          </div>
        ))}
      </div>
      <span
        className="mt-4 inline-flex h-11 w-full items-center justify-center gap-2 px-5 text-sm font-semibold"
        style={{ borderRadius: radius, background: accent, color: accentInk }}
      >
        Send my action plan
        <ArrowRight className="size-4" aria-hidden="true" />
      </span>
      <p className="mt-3 text-center text-xs leading-5 opacity-50">
        By continuing, you agree to be contacted about your result.
      </p>
    </div>
  );
}

function BrandPreview({
  draft,
  pairings,
  mode,
  device,
}: {
  draft: Draft;
  pairings: WorkspaceBrand["font_pairings"];
  mode: PreviewMode;
  device: PreviewDevice;
}) {
  const pairing = pairings.find((item) => item.id === draft.font_pairing);
  const accent = safeHex(draft.accent_color, "#45604F");
  const background = safeHex(effectiveBackground(draft), "#F7F5EE");
  const ink = readableInk(background);
  const accentInk = readableInk(accent);
  const contrast = contrastRatio(accent, accentInk);
  const radius = `${draft.corner_radius ?? 12}px`;
  const headingFont = pairing ? `${pairing.heading}, Georgia, serif` : "inherit";
  const bodyFont = pairing ? `${pairing.body}, system-ui, sans-serif` : "inherit";

  return (
    <div
      className={`mx-auto w-full transition-[max-width] duration-200 ${
        device === "mobile" ? "max-w-[25rem]" : "max-w-none"
      }`}
    >
      <div
        className={`overflow-hidden border shadow-float ${
          device === "mobile" ? "min-h-[42rem]" : "min-h-[38rem]"
        }`}
        style={{
          background,
          color: ink,
          borderColor: `${ink}1F`,
          borderRadius: `calc(${radius} + 8px)`,
          fontFamily: bodyFont,
        }}
      >
        <div
          className="flex min-h-16 items-center justify-between gap-4 border-b px-5 sm:px-7"
          style={{ borderColor: `${ink}1F` }}
        >
          <div className="flex min-w-0 items-center gap-3">
            <BrandMark logoUrl={draft.logo_url} accent={accent} />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">Your company</p>
              <p className="truncate text-xs opacity-50">Growth readiness audit</p>
            </div>
          </div>
          <span
            className="hidden items-center gap-1.5 text-xs font-medium sm:inline-flex"
            style={{ color: contrast >= 4.5 ? ink : accent }}
          >
            <CheckCircle2 className="size-3.5" aria-hidden="true" />
            {contrast.toFixed(1)}:1 button contrast
          </span>
        </div>

        <div
          className={`px-5 py-7 sm:px-8 sm:py-9 ${device === "desktop" ? "lg:px-10" : ""}`}
          style={{ "--preview-accent": accent } as CSSProperties}
        >
          <div style={{ fontFamily: headingFont }}>
            {mode === "question" && (
              <PreviewQuestion accent={accent} accentInk={accentInk} ink={ink} radius={radius} />
            )}
            {mode === "result" && (
              <PreviewResult accent={accent} accentInk={accentInk} ink={ink} radius={radius} />
            )}
            {mode === "lead" && (
              <PreviewLead accent={accent} accentInk={accentInk} ink={ink} radius={radius} />
            )}
          </div>
        </div>

        <div
          className="flex min-h-12 items-center justify-between gap-4 border-t px-5 text-xs opacity-55 sm:px-7"
          style={{ borderColor: `${ink}1F` }}
        >
          <span>Powered by Magnitai</span>
          <span>{draft.brand_personality || "Website voice"}</span>
        </div>
      </div>
    </div>
  );
}

function BrandScreen() {
  return (
    <WorkspaceShell breadcrumb={[{ label: "Brand" }]} contentWidth="wide">
      <PlanGate feature="brand_kit">
        <BrandStudioExperience />
      </PlanGate>
    </WorkspaceShell>
  );
}

type BrandSectionId = "colour" | "typography" | "shape" | "logo" | "voice";

const BRAND_SECTIONS: Array<{
  id: BrandSectionId;
  label: string;
  title: string;
  description: string;
}> = [
  {
    id: "colour",
    label: "Colour",
    title: "Colour system",
    description: "Choose the action colour visitors notice and the surface your tools sit on.",
  },
  {
    id: "typography",
    label: "Type",
    title: "Typography",
    description: "Pick one reliable heading and body pairing for every generated experience.",
  },
  {
    id: "shape",
    label: "Shape",
    title: "Shape",
    description: "Set the corner language for cards, answers, inputs, and calls to action.",
  },
  {
    id: "logo",
    label: "Logo",
    title: "Logo",
    description: "Add the public logo file Magnitai should carry into generated tools.",
  },
  {
    id: "voice",
    label: "Voice",
    title: "Voice direction",
    description: "Describe how generated questions, explanations, and results should sound.",
  },
];

function BrandStudioExperience() {
  const brandQuery = useWorkspaceBrand();
  const save = useSaveWorkspaceBrand();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [activeSection, setActiveSection] = useState<BrandSectionId>("colour");
  const [previewMode, setPreviewMode] = useState<PreviewMode>("question");
  const [previewDevice, setPreviewDevice] = useState<PreviewDevice>("desktop");

  useEffect(() => {
    if (brandQuery.data) setDraft(toDraft(brandQuery.data));
  }, [brandQuery.data]);

  const dirty = useMemo(
    () =>
      Boolean(
        draft &&
        brandQuery.data &&
        JSON.stringify(draft) !== JSON.stringify(toDraft(brandQuery.data)),
      ),
    [draft, brandQuery.data],
  );

  if (brandQuery.isLoading || (!draft && !brandQuery.isError)) {
    return (
      <>
        <div className="max-w-2xl">
          <p className="group-label font-mono text-muted-foreground">Brand system</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-foreground">
            Make every tool feel like you.
          </h1>
        </div>
        <div className="flex min-h-[32rem] flex-col items-center justify-center gap-3">
          <Loader2 className="size-5 animate-spin text-muted-foreground" aria-label="Loading" />
          <p className="text-sm text-muted-foreground">Loading your brand studio…</p>
        </div>
      </>
    );
  }

  if (brandQuery.isError || !draft || !brandQuery.data) {
    return (
      <>
        <div className="max-w-2xl">
          <p className="group-label font-mono text-muted-foreground">Brand system</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-foreground">
            Make every tool feel like you.
          </h1>
        </div>
        <div className="mt-8 border-y border-border px-2 py-12 text-center">
          <span className="mx-auto grid size-11 place-items-center rounded-xl bg-secondary">
            <AlertCircle className="size-5 text-destructive" aria-hidden="true" />
          </span>
          <h2 className="mt-4 text-lg font-medium text-foreground">
            Your brand could not be loaded
          </h2>
          <p className="mx-auto mt-1.5 max-w-md text-sm leading-6 text-muted-foreground">
            Nothing has been changed. Check the connection and try loading the studio again.
          </p>
          <button
            type="button"
            onClick={() => void brandQuery.refetch()}
            className="btn btn-primary mt-6 h-10 text-sm"
          >
            Try again
          </button>
        </div>
      </>
    );
  }

  const data = brandQuery.data;
  const update = (patch: Partial<Draft>) => {
    save.reset();
    setDraft((current) => (current ? { ...current, ...patch } : current));
  };

  const accentError =
    draft.accent_color && !HEX_COLOR.test(draft.accent_color)
      ? "Use a 3- or 6-digit hex colour, such as #45604F."
      : null;
  const backgroundError =
    draft.background_color && !HEX_COLOR.test(draft.background_color)
      ? "Use a 3- or 6-digit hex colour, such as #FAF7F2."
      : null;
  const logoError =
    draft.logo_url && !HTTP_URL.test(draft.logo_url)
      ? "Enter a public http or https address."
      : null;
  const valid = !accentError && !backgroundError && !logoError;
  const pinned = pinnedDecisionCount(draft);
  const sectionIndex = BRAND_SECTIONS.findIndex((section) => section.id === activeSection);
  const section = BRAND_SECTIONS[sectionIndex];

  const isSectionPinned = (id: BrandSectionId) => {
    if (id === "colour") return Boolean(draft.accent_color || draft.background_color || draft.tone);
    if (id === "typography") return Boolean(draft.font_pairing);
    if (id === "shape") return draft.corner_radius !== null;
    if (id === "logo") return Boolean(draft.logo_url);
    return Boolean(draft.brand_personality);
  };

  const discard = () => {
    save.reset();
    setDraft(toDraft(data));
  };

  const followWebsite = () => {
    save.reset();
    setDraft(emptyDraft());
  };

  const resetSection = () => {
    if (activeSection === "colour") {
      update({ accent_color: null, background_color: null, tone: null });
    } else if (activeSection === "typography") {
      update({ font_pairing: null });
    } else if (activeSection === "shape") {
      update({ corner_radius: null });
    } else if (activeSection === "logo") {
      update({ logo_url: null });
    } else {
      update({ brand_personality: null });
    }
  };

  return (
    <>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-5">
        <div className="max-w-2xl">
          <p className="group-label font-mono text-muted-foreground">Brand system</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-foreground sm:text-4xl">
            Make every tool feel like you.
          </h1>
          <p className="mt-3 max-w-xl text-sm leading-6 text-muted-foreground sm:text-base">
            Lock the choices that should never drift. Magnitai will keep reading each website for
            everything you leave open.
          </p>
        </div>
        <Link
          to="/dashboard"
          className="inline-flex min-h-11 items-center gap-2 text-sm font-medium text-foreground hover:underline"
        >
          View existing tools
          <ArrowRight className="size-4" aria-hidden="true" />
        </Link>
      </div>

      <div className="sticky top-16 z-20 -mx-4 mb-6 border-y border-border bg-background/95 px-4 py-2.5 backdrop-blur-xl sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2.5" aria-live="polite">
            <span
              className={`size-2 shrink-0 rounded-full ${
                dirty ? "bg-warning" : save.isSuccess ? "bg-success" : "bg-n-400"
              }`}
              aria-hidden="true"
            />
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-foreground">
                {dirty
                  ? "Unsaved changes"
                  : save.isSuccess
                    ? "Brand saved"
                    : pinned > 0
                      ? `${pinned}/6 choices active`
                      : "Following each website"}
              </p>
              <p className="hidden text-xs text-muted-foreground md:block">
                Unpinned choices come from the source website
              </p>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
            <button
              type="button"
              onClick={discard}
              disabled={!dirty || save.isPending}
              className="btn btn-ghost h-9 px-2.5 text-sm sm:px-3"
            >
              <Undo2 className="size-4" aria-hidden="true" />
              <span className="hidden sm:inline">Discard</span>
            </button>
            <button
              type="button"
              onClick={() => save.mutate(draft)}
              disabled={!dirty || !valid || save.isPending}
              className="btn btn-primary h-9 px-3 text-sm"
            >
              {save.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              ) : (
                <Check className="size-4" aria-hidden="true" />
              )}
              Save
            </button>
          </div>
        </div>
        {save.isError && (
          <p role="alert" className="mt-2 flex items-center gap-1.5 text-xs text-destructive">
            <AlertCircle className="size-3.5 shrink-0" aria-hidden="true" />
            {(save.error as Error).message}
          </p>
        )}
      </div>

      <div className="grid items-start gap-8 xl:grid-cols-[minmax(24rem,0.78fr)_minmax(38rem,1.22fr)] 2xl:gap-12">
        <div className="min-w-0">
          <nav aria-label="Brand decisions" className="flex overflow-x-auto border-y border-border">
            {BRAND_SECTIONS.map((item, index) => {
              const active = item.id === activeSection;
              const itemPinned = isSectionPinned(item.id);
              return (
                <button
                  key={item.id}
                  type="button"
                  aria-current={active ? "step" : undefined}
                  onClick={() => setActiveSection(item.id)}
                  className={`relative flex min-h-14 min-w-[5.5rem] flex-1 items-center justify-center gap-2 px-3 text-sm transition-colors ${
                    active
                      ? "font-medium text-foreground"
                      : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                  }`}
                >
                  <span
                    className={`grid size-5 shrink-0 place-items-center rounded-full border font-mono text-xs ${
                      itemPinned
                        ? "border-foreground bg-foreground text-background"
                        : "border-border-strong"
                    }`}
                    aria-hidden="true"
                  >
                    {itemPinned ? <Check className="size-3" /> : index + 1}
                  </span>
                  {item.label}
                  {active && <span className="absolute inset-x-3 bottom-0 h-0.5 bg-foreground" />}
                  <span className="sr-only">{itemPinned ? "Pinned" : "Following website"}</span>
                </button>
              );
            })}
          </nav>

          <section
            aria-labelledby={`brand-section-${activeSection}`}
            className="min-h-[31rem] py-6"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="group-label font-mono text-muted-foreground">
                  Decision {sectionIndex + 1} of {BRAND_SECTIONS.length}
                </p>
                <h2
                  id={`brand-section-${activeSection}`}
                  className="mt-2 text-2xl font-semibold tracking-[-0.035em] text-foreground"
                >
                  {section.title}
                </h2>
                <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
                  {section.description}
                </p>
              </div>
              {isSectionPinned(activeSection) && (
                <FollowWebsiteButton onClick={resetSection}>Follow website</FollowWebsiteButton>
              )}
            </div>

            {activeSection === "colour" && (
              <div className="mt-6 space-y-6">
                <div>
                  <div className="flex flex-wrap items-end justify-between gap-3">
                    <ColourField
                      label="Action colour"
                      value={draft.accent_color}
                      fallback="#45604F"
                      placeholder="#45604F"
                      error={accentError}
                      onChange={(accent_color) => update({ accent_color })}
                    />
                    <div className="flex flex-wrap items-center gap-2 pb-0.5">
                      {ACCENT_PRESETS.map((preset) => {
                        const active =
                          draft.accent_color?.toUpperCase() === preset.value.toUpperCase();
                        return (
                          <button
                            key={preset.value}
                            type="button"
                            title={`${preset.label} ${preset.value}`}
                            aria-label={`Use ${preset.label} ${preset.value}`}
                            aria-pressed={active}
                            onClick={() => update({ accent_color: preset.value })}
                            className={`grid size-10 place-items-center rounded-full border-2 transition-transform hover:scale-105 ${
                              active ? "border-foreground" : "border-card"
                            }`}
                            style={{ background: preset.value }}
                          >
                            {active && (
                              <Check
                                className="size-4"
                                style={{ color: readableInk(preset.value) }}
                                strokeWidth={2.5}
                                aria-hidden="true"
                              />
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>

                <div className="border-t border-border pt-5">
                  <div className="flex items-end justify-between gap-3">
                    <div>
                      <p className="text-xs font-medium text-foreground">Tool surface</p>
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">
                        Start with a mood or enter an exact colour.
                      </p>
                    </div>
                    {(draft.tone || draft.background_color) && (
                      <FollowWebsiteButton
                        onClick={() => update({ tone: null, background_color: null })}
                      >
                        Reset surface
                      </FollowWebsiteButton>
                    )}
                  </div>

                  <div className="mt-3 grid grid-cols-3 gap-2">
                    {TONES.map((tone) => {
                      const active = draft.tone === tone.id && !draft.background_color;
                      return (
                        <button
                          key={tone.id}
                          type="button"
                          aria-pressed={active}
                          onClick={() => update({ tone: tone.id, background_color: null })}
                          className={`relative min-h-20 overflow-hidden rounded-xl border p-3 text-left transition-colors ${
                            active
                              ? "border-foreground ring-1 ring-foreground"
                              : "border-border-strong hover:border-foreground/40"
                          }`}
                          style={{ background: tone.swatch, color: readableInk(tone.swatch) }}
                        >
                          <span className="block text-sm font-medium">{tone.label}</span>
                          <span className="mt-1 block text-xs opacity-60">{tone.note}</span>
                          {active && (
                            <Check
                              className="absolute bottom-3 right-3 size-4"
                              aria-hidden="true"
                            />
                          )}
                        </button>
                      );
                    })}
                  </div>

                  <div className="mt-4">
                    <ColourField
                      label="Exact surface colour"
                      value={draft.background_color}
                      fallback={effectiveBackground(draft)}
                      placeholder="#FAF7F2"
                      error={backgroundError}
                      onChange={(background_color) =>
                        update({
                          background_color,
                          tone: background_color ? null : draft.tone,
                        })
                      }
                    />
                  </div>
                </div>
              </div>
            )}

            {activeSection === "typography" && (
              <div className="mt-6 grid grid-cols-2 gap-2">
                {data.font_pairings.map((pairing) => {
                  const active = draft.font_pairing === pairing.id;
                  return (
                    <button
                      key={pairing.id}
                      type="button"
                      aria-pressed={active}
                      onClick={() => update({ font_pairing: active ? null : pairing.id })}
                      className={`min-h-24 rounded-xl border p-3.5 text-left transition-colors ${
                        active
                          ? "border-foreground bg-secondary ring-1 ring-foreground"
                          : "border-border-strong bg-card hover:border-foreground/40"
                      }`}
                    >
                      <span className="flex items-start justify-between gap-3">
                        <span
                          className="text-[1.65rem] leading-none text-foreground"
                          style={{ fontFamily: `${pairing.heading}, Georgia, serif` }}
                        >
                          Aa
                        </span>
                        {active && (
                          <CheckCircle2 className="size-4 text-foreground" aria-hidden="true" />
                        )}
                      </span>
                      <span className="mt-2.5 block text-sm font-medium text-foreground">
                        {pairing.label}
                      </span>
                      <span className="mt-0.5 block text-xs text-muted-foreground">
                        {pairing.note}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}

            {activeSection === "shape" && (
              <div className="mt-6 grid grid-cols-6 gap-1.5">
                {RADII.map((radius) => {
                  const active = draft.corner_radius === radius;
                  return (
                    <button
                      key={radius}
                      type="button"
                      aria-label={`${radius} pixel corner radius`}
                      aria-pressed={active}
                      onClick={() => update({ corner_radius: active ? null : radius })}
                      className={`flex min-h-20 flex-col items-center justify-center gap-2 rounded-lg border transition-colors ${
                        active
                          ? "border-foreground bg-secondary ring-1 ring-foreground"
                          : "border-border-strong bg-card hover:border-foreground/40"
                      }`}
                    >
                      <span
                        className="size-6 border-2 border-foreground/70"
                        style={{ borderRadius: `${radius}px` }}
                        aria-hidden="true"
                      />
                      <span className="tabular text-xs text-muted-foreground">{radius}px</span>
                    </button>
                  );
                })}
              </div>
            )}

            {activeSection === "logo" && (
              <div className="mt-6">
                <label className="block">
                  <span className="mb-1.5 block text-xs font-medium text-foreground">
                    Public logo URL
                  </span>
                  <div className="flex items-center gap-3">
                    <span className="grid size-12 shrink-0 place-items-center rounded-lg border border-border-strong bg-card">
                      {draft.logo_url && HTTP_URL.test(draft.logo_url) ? (
                        <img
                          src={draft.logo_url}
                          alt=""
                          className="size-9 object-contain"
                          onError={(event) => {
                            event.currentTarget.style.display = "none";
                          }}
                        />
                      ) : (
                        <ImageIcon className="size-4 text-muted-foreground" aria-hidden="true" />
                      )}
                    </span>
                    <input
                      type="url"
                      value={draft.logo_url ?? ""}
                      placeholder="https://company.com/logo.svg"
                      aria-invalid={Boolean(logoError)}
                      onChange={(event) => update({ logo_url: event.target.value || null })}
                      className={`${FIELD} ${logoError ? "border-destructive" : ""}`}
                    />
                  </div>
                  {logoError ? (
                    <span role="alert" className="mt-1.5 block text-xs text-destructive">
                      {logoError}
                    </span>
                  ) : (
                    <span className="mt-2 block text-xs leading-5 text-muted-foreground">
                      Use a public SVG or transparent PNG. Maximum URL length: 2,048 characters.
                    </span>
                  )}
                </label>
              </div>
            )}

            {activeSection === "voice" && (
              <div className="mt-6">
                <label className="block">
                  <span className="mb-1.5 flex items-center justify-between gap-3 text-xs font-medium text-foreground">
                    Brand personality
                    <span className="tabular font-normal text-muted-foreground">
                      {(draft.brand_personality ?? "").length}/240
                    </span>
                  </span>
                  <textarea
                    value={draft.brand_personality ?? ""}
                    maxLength={240}
                    placeholder="For example: calm, trustworthy, concise, and clear about the next step."
                    onChange={(event) => update({ brand_personality: event.target.value || null })}
                    className={TEXTAREA}
                  />
                </label>
                <div className="mt-3 flex flex-wrap gap-2">
                  {VOICE_STARTERS.map((starter) => {
                    const active = draft.brand_personality === starter;
                    return (
                      <button
                        key={starter}
                        type="button"
                        aria-pressed={active}
                        onClick={() => update({ brand_personality: starter })}
                        className={`min-h-9 rounded-full border px-3 text-xs transition-colors ${
                          active
                            ? "border-foreground bg-foreground text-background"
                            : "border-border-strong bg-card text-muted-foreground hover:border-foreground/40 hover:text-foreground"
                        }`}
                      >
                        {starter}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="mt-7 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
              <button
                type="button"
                disabled={sectionIndex === 0}
                onClick={() => setActiveSection(BRAND_SECTIONS[sectionIndex - 1].id)}
                className="btn btn-ghost h-10 px-3 text-sm"
              >
                Back
              </button>
              <div className="flex items-center gap-2">
                <a href="#brand-preview" className="btn btn-ghost h-10 px-3 text-sm xl:hidden">
                  See preview
                </a>
                {sectionIndex < BRAND_SECTIONS.length - 1 ? (
                  <button
                    type="button"
                    onClick={() => setActiveSection(BRAND_SECTIONS[sectionIndex + 1].id)}
                    className="btn btn-secondary h-10 px-4 text-sm"
                  >
                    Next: {BRAND_SECTIONS[sectionIndex + 1].label}
                    <ArrowRight className="size-4" aria-hidden="true" />
                  </button>
                ) : (
                  <a href="#brand-preview" className="btn btn-secondary h-10 px-4 text-sm">
                    Review preview
                    <ArrowRight className="size-4" aria-hidden="true" />
                  </a>
                )}
              </div>
            </div>
          </section>

          <div className="flex flex-wrap items-center justify-between gap-4 border-y border-border py-4">
            <div>
              <p className="text-sm font-medium text-foreground">{pinned}/6 choices pinned</p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Everything else follows each source website.
              </p>
            </div>
            <button
              type="button"
              onClick={followWebsite}
              className="inline-flex min-h-10 items-center gap-2 rounded-lg px-2 text-xs font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
            >
              <RotateCcw className="size-4" aria-hidden="true" />
              Follow website for everything
            </button>
          </div>
        </div>

        <aside id="brand-preview" className="min-w-0 scroll-mt-36 xl:sticky xl:top-32">
          <div className="overflow-hidden border border-border bg-card shadow-raised">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3 sm:px-5">
              <div>
                <h2 className="text-sm font-medium text-foreground">Live tool preview</h2>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Every change appears here immediately.
                </p>
              </div>
              <div className="flex items-center gap-1 rounded-lg border border-border bg-n-50 p-1">
                {(
                  [
                    ["desktop", Monitor, "Desktop preview"],
                    ["mobile", Smartphone, "Mobile preview"],
                  ] as const
                ).map(([value, Icon, label]) => (
                  <button
                    key={value}
                    type="button"
                    aria-label={label}
                    aria-pressed={previewDevice === value}
                    onClick={() => setPreviewDevice(value)}
                    className={`grid size-8 place-items-center rounded-md transition-colors ${
                      previewDevice === value
                        ? "bg-card text-foreground shadow-raised"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    <Icon className="size-4" aria-hidden="true" />
                  </button>
                ))}
              </div>
            </div>

            <div className="flex gap-1 overflow-x-auto border-b border-border px-4 pt-2 sm:px-5">
              {(
                [
                  ["question", "Question"],
                  ["result", "Result"],
                  ["lead", "Lead capture"],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={previewMode === value}
                  onClick={() => setPreviewMode(value)}
                  className={`relative min-h-10 shrink-0 px-3 text-sm transition-colors ${
                    previewMode === value
                      ? "font-medium text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {label}
                  {previewMode === value && (
                    <span className="absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-foreground" />
                  )}
                </button>
              ))}
            </div>

            <div className="bg-n-100 p-3 sm:p-5">
              <BrandPreview
                draft={draft}
                pairings={data.font_pairings}
                mode={previewMode}
                device={previewDevice}
              />
            </div>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="flex items-start gap-3 border-t border-border pt-3">
              <Laptop className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <p className="text-xs leading-5 text-muted-foreground">
                New tools receive this house style automatically.
              </p>
            </div>
            <div className="flex items-start gap-3 border-t border-border pt-3">
              <Sparkles
                className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                aria-hidden="true"
              />
              <p className="text-xs leading-5 text-muted-foreground">
                Regenerate an existing tool when you want it to adopt the update.
              </p>
            </div>
          </div>
        </aside>
      </div>
    </>
  );
}

/*
const _LegacyBrandForm = function LegacyBrandForm() {
  const brandQuery = useWorkspaceBrand();
  const save = useSaveWorkspaceBrand();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [previewMode, setPreviewMode] = useState<PreviewMode>("question");
  const [previewDevice, setPreviewDevice] = useState<PreviewDevice>("desktop");

  useEffect(() => {
    if (brandQuery.data) setDraft(toDraft(brandQuery.data));
  }, [brandQuery.data]);

  const dirty = useMemo(
    () =>
      Boolean(
        draft &&
        brandQuery.data &&
        JSON.stringify(draft) !== JSON.stringify(toDraft(brandQuery.data)),
      ),
    [draft, brandQuery.data],
  );

  if (brandQuery.isLoading || (!draft && !brandQuery.isError)) {
    return (
      <div className="flex min-h-[28rem] flex-col items-center justify-center gap-3">
        <Loader2 className="size-5 animate-spin text-muted-foreground" aria-label="Loading" />
        <p className="text-sm text-muted-foreground">Loading your brand studio…</p>
      </div>
    );
  }

  if (brandQuery.isError || !draft || !brandQuery.data) {
    return (
      <div className="surface mx-auto max-w-xl px-6 py-12 text-center">
        <span className="mx-auto grid size-11 place-items-center rounded-xl bg-secondary">
          <AlertCircle className="size-5 text-destructive" aria-hidden="true" />
        </span>
        <h2 className="mt-4 text-lg font-medium text-foreground">Your brand could not be loaded</h2>
        <p className="mx-auto mt-1.5 max-w-md text-sm leading-6 text-muted-foreground">
          Nothing has been changed. Check the connection and try loading the studio again.
        </p>
        <button
          type="button"
          onClick={() => void brandQuery.refetch()}
          className="btn btn-primary mt-6 h-10 text-sm"
        >
          Try again
        </button>
      </div>
    );
  }

  const data = brandQuery.data;
  const update = (patch: Partial<Draft>) => {
    save.reset();
    setDraft((current) => (current ? { ...current, ...patch } : current));
  };

  const accentError =
    draft.accent_color && !HEX_COLOR.test(draft.accent_color)
      ? "Use a 3- or 6-digit hex colour, such as #45604F."
      : null;
  const backgroundError =
    draft.background_color && !HEX_COLOR.test(draft.background_color)
      ? "Use a 3- or 6-digit hex colour, such as #FAF7F2."
      : null;
  const logoError =
    draft.logo_url && !HTTP_URL.test(draft.logo_url)
      ? "Enter a public http or https address."
      : null;
  const valid = !accentError && !backgroundError && !logoError;
  const pinned = pinnedDecisionCount(draft);

  const discard = () => {
    save.reset();
    setDraft(toDraft(data));
  };

  const followWebsite = () => {
    save.reset();
    setDraft(emptyDraft());
  };

  return (
    <>
      <div className="sticky top-16 z-20 -mx-4 mb-7 border-y border-border bg-background/95 px-4 py-3 backdrop-blur-xl sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3" aria-live="polite">
            <span
              className={`size-2 shrink-0 rounded-full ${
                dirty ? "bg-warning" : save.isSuccess ? "bg-success" : "bg-n-400"
              }`}
              aria-hidden="true"
            />
            <div className="min-w-0">
              <p className="text-sm font-medium text-foreground">
                {dirty
                  ? "You have unsaved changes"
                  : save.isSuccess
                    ? "Brand saved"
                    : pinned > 0
                      ? "House style active"
                      : "Following each website"}
              </p>
              <p className="hidden text-xs text-muted-foreground sm:block">
                {pinned} of 6 decisions pinned · Unpinned choices come from the source website
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={discard}
              disabled={!dirty || save.isPending}
              className="btn btn-ghost h-9 px-3 text-sm"
            >
              <Undo2 className="size-4" aria-hidden="true" />
              Discard
            </button>
            <button
              type="button"
              onClick={() => save.mutate(draft)}
              disabled={!dirty || !valid || save.isPending}
              className="btn btn-primary h-9 text-sm"
            >
              {save.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              ) : (
                <Check className="size-4" aria-hidden="true" />
              )}
              Save changes
            </button>
          </div>
        </div>
        {save.isError && (
          <p role="alert" className="mt-2 flex items-center gap-1.5 text-xs text-destructive">
            <AlertCircle className="size-3.5 shrink-0" aria-hidden="true" />
            {(save.error as Error).message}
          </p>
        )}
      </div>

      <div className="mb-8 grid border-y border-border sm:grid-cols-[1.15fr_0.85fr]">
        <div className="py-5 pr-0 sm:border-r sm:border-border sm:pr-8">
          <p className="text-sm font-medium text-foreground">A consistent starting point</p>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
            These choices are layered over Magnitai’s website scan at build time. Pin what should
            never drift; let everything else stay native to each site.
          </p>
        </div>
        <div className="flex items-center justify-between gap-5 border-t border-border py-5 sm:border-t-0 sm:pl-8">
          <div>
            <p className="tabular text-2xl font-medium tracking-[-0.035em] text-foreground">
              {pinned}/6
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">brand decisions pinned</p>
          </div>
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-foreground hover:underline"
          >
            Manage existing tools
            <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </div>
      </div>

      <div className="grid items-start gap-10 xl:grid-cols-[minmax(26rem,0.82fr)_minmax(38rem,1.35fr)] 2xl:gap-14">
        <div className="min-w-0">
          <div className="border-t border-border">
            <section className="border-b border-border py-7">
              <SectionHeading
                number="01"
                title="Colour system"
                description="Pin the action colour visitors should notice and the surface it sits on. Magnitai checks the button label against your colour in the live preview."
                action={
                  <FollowWebsiteButton
                    onClick={() =>
                      update({ accent_color: null, background_color: null, tone: null })
                    }
                  >
                    Follow website
                  </FollowWebsiteButton>
                }
              />

              <div className="ml-10 mt-6 space-y-7">
                <div>
                  <ColourField
                    label="Action colour"
                    value={draft.accent_color}
                    fallback="#45604F"
                    placeholder="#45604F"
                    error={accentError}
                    onChange={(accent_color) => update({ accent_color })}
                  />
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <span className="mr-1 text-xs text-muted-foreground">Suggested</span>
                    {ACCENT_PRESETS.map((preset) => {
                      const active =
                        draft.accent_color?.toUpperCase() === preset.value.toUpperCase();
                      return (
                        <button
                          key={preset.value}
                          type="button"
                          title={`${preset.label} ${preset.value}`}
                          aria-label={`Use ${preset.label} ${preset.value}`}
                          aria-pressed={active}
                          onClick={() => update({ accent_color: preset.value })}
                          className={`grid size-9 place-items-center rounded-full border-2 transition-transform hover:scale-105 ${
                            active ? "border-foreground" : "border-card"
                          }`}
                          style={{ background: preset.value }}
                        >
                          {active && (
                            <Check
                              className="size-4"
                              style={{ color: readableInk(preset.value) }}
                              strokeWidth={2.5}
                              aria-hidden="true"
                            />
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div>
                  <div className="flex items-end justify-between gap-3">
                    <div>
                      <p className="text-xs font-medium text-foreground">Tool surface</p>
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">
                        Choose a mood, use a precise colour, or keep reading the website.
                      </p>
                    </div>
                    {(draft.tone || draft.background_color) && (
                      <FollowWebsiteButton
                        onClick={() => update({ tone: null, background_color: null })}
                      >
                        Reset surface
                      </FollowWebsiteButton>
                    )}
                  </div>

                  <div className="mt-3 grid grid-cols-3 gap-2">
                    {TONES.map((tone) => {
                      const active = draft.tone === tone.id && !draft.background_color;
                      const swatchInk = readableInk(tone.swatch);
                      return (
                        <button
                          key={tone.id}
                          type="button"
                          aria-pressed={active}
                          onClick={() => update({ tone: tone.id, background_color: null })}
                          className={`relative min-h-24 overflow-hidden rounded-xl border p-3 text-left transition-colors ${
                            active
                              ? "border-foreground ring-1 ring-foreground"
                              : "border-border-strong hover:border-foreground/40"
                          }`}
                          style={{ background: tone.swatch, color: swatchInk }}
                        >
                          <span className="block text-sm font-medium">{tone.label}</span>
                          <span className="mt-1 block text-xs opacity-60">{tone.note}</span>
                          {active && (
                            <Check
                              className="absolute bottom-3 right-3 size-4"
                              aria-hidden="true"
                            />
                          )}
                        </button>
                      );
                    })}
                  </div>

                  <div className="mt-4">
                    <ColourField
                      label="Custom surface"
                      value={draft.background_color}
                      fallback={effectiveBackground(draft)}
                      placeholder="#FAF7F2"
                      error={backgroundError}
                      onChange={(background_color) =>
                        update({
                          background_color,
                          tone: background_color ? null : draft.tone,
                        })
                      }
                    />
                  </div>
                </div>
              </div>
            </section>

            <section className="border-b border-border py-7">
              <SectionHeading
                number="02"
                title="Typography"
                description="Choose a tested heading and body pairing that generated tools can load reliably. Leave this open to preserve the type Magnitai finds on each website."
                action={
                  draft.font_pairing ? (
                    <FollowWebsiteButton onClick={() => update({ font_pairing: null })}>
                      Follow website
                    </FollowWebsiteButton>
                  ) : undefined
                }
              />

              <div className="ml-10 mt-5 grid gap-2 sm:grid-cols-2">
                {data.font_pairings.map((pairing) => {
                  const active = draft.font_pairing === pairing.id;
                  return (
                    <button
                      key={pairing.id}
                      type="button"
                      aria-pressed={active}
                      onClick={() => update({ font_pairing: active ? null : pairing.id })}
                      className={`min-h-28 rounded-xl border p-3.5 text-left transition-colors ${
                        active
                          ? "border-foreground bg-secondary ring-1 ring-foreground"
                          : "border-border-strong bg-card hover:border-foreground/40"
                      }`}
                    >
                      <span className="flex items-start justify-between gap-3">
                        <span
                          className="text-[1.65rem] leading-none text-foreground"
                          style={{ fontFamily: `${pairing.heading}, Georgia, serif` }}
                        >
                          Aa
                        </span>
                        {active && (
                          <CheckCircle2 className="size-4 text-foreground" aria-hidden="true" />
                        )}
                      </span>
                      <span className="mt-3 block text-sm font-medium text-foreground">
                        {pairing.label}
                      </span>
                      <span className="mt-0.5 block text-xs text-muted-foreground">
                        {pairing.note}
                      </span>
                    </button>
                  );
                })}
              </div>
            </section>

            <section className="border-b border-border py-7">
              <SectionHeading
                number="03"
                title="Shape"
                description="Set one radius for cards, answers, inputs, and calls to action so every generated interaction speaks the same visual language."
                action={
                  draft.corner_radius !== null ? (
                    <FollowWebsiteButton onClick={() => update({ corner_radius: null })}>
                      Follow website
                    </FollowWebsiteButton>
                  ) : undefined
                }
              />

              <div className="ml-10 mt-5 grid grid-cols-3 gap-2 sm:grid-cols-6">
                {RADII.map((radius) => {
                  const active = draft.corner_radius === radius;
                  return (
                    <button
                      key={radius}
                      type="button"
                      aria-label={`${radius} pixel corner radius`}
                      aria-pressed={active}
                      onClick={() => update({ corner_radius: active ? null : radius })}
                      className={`flex min-h-20 flex-col items-center justify-center gap-2 rounded-lg border transition-colors ${
                        active
                          ? "border-foreground bg-secondary ring-1 ring-foreground"
                          : "border-border-strong bg-card hover:border-foreground/40"
                      }`}
                    >
                      <span
                        className="size-7 border-2 border-foreground/70"
                        style={{ borderRadius: `${radius}px` }}
                        aria-hidden="true"
                      />
                      <span className="tabular text-xs text-muted-foreground">{radius}px</span>
                    </button>
                  );
                })}
              </div>
            </section>

            <section className="border-b border-border py-7">
              <SectionHeading
                number="04"
                title="Logo"
                description="Use a public logo file that can travel with generated tools. SVG and transparent PNG files stay sharp across screen sizes."
                action={
                  draft.logo_url ? (
                    <FollowWebsiteButton onClick={() => update({ logo_url: null })}>
                      Use website logo
                    </FollowWebsiteButton>
                  ) : undefined
                }
              />

              <div className="ml-10 mt-5">
                <label className="block">
                  <span className="mb-1.5 block text-xs font-medium text-foreground">
                    Public logo URL
                  </span>
                  <div className="flex items-center gap-3">
                    <span className="grid size-11 shrink-0 place-items-center rounded-lg border border-border-strong bg-card">
                      {draft.logo_url && HTTP_URL.test(draft.logo_url) ? (
                        <img
                          src={draft.logo_url}
                          alt=""
                          className="size-8 object-contain"
                          onError={(event) => {
                            event.currentTarget.style.display = "none";
                          }}
                        />
                      ) : (
                        <ImageIcon className="size-4 text-muted-foreground" aria-hidden="true" />
                      )}
                    </span>
                    <input
                      type="url"
                      value={draft.logo_url ?? ""}
                      placeholder="https://company.com/logo.svg"
                      aria-invalid={Boolean(logoError)}
                      onChange={(event) => update({ logo_url: event.target.value || null })}
                      className={`${FIELD} ${logoError ? "border-destructive" : ""}`}
                    />
                  </div>
                  {logoError ? (
                    <span role="alert" className="mt-1.5 block text-xs text-destructive">
                      {logoError}
                    </span>
                  ) : (
                    <span className="mt-1.5 block text-xs leading-5 text-muted-foreground">
                      The file must be reachable without a login. Maximum URL length: 2,048
                      characters.
                    </span>
                  )}
                </label>
              </div>
            </section>

            <section className="py-7">
              <SectionHeading
                number="05"
                title="Voice direction"
                description="Give Magnitai the words that should guide generated questions, explanations, and results. Be specific enough that a teammate could recognise the voice."
                action={
                  draft.brand_personality ? (
                    <FollowWebsiteButton onClick={() => update({ brand_personality: null })}>
                      Follow website
                    </FollowWebsiteButton>
                  ) : undefined
                }
              />

              <div className="ml-10 mt-5">
                <label className="block">
                  <span className="mb-1.5 flex items-center justify-between gap-3 text-xs font-medium text-foreground">
                    Brand personality
                    <span className="tabular font-normal text-muted-foreground">
                      {(draft.brand_personality ?? "").length}/240
                    </span>
                  </span>
                  <textarea
                    value={draft.brand_personality ?? ""}
                    maxLength={240}
                    placeholder="For example: calm, trustworthy, concise, and clear about the next step."
                    onChange={(event) => update({ brand_personality: event.target.value || null })}
                    className={TEXTAREA}
                  />
                </label>

                <div className="mt-3 flex flex-wrap gap-2">
                  {VOICE_STARTERS.map((starter) => (
                    <button
                      key={starter}
                      type="button"
                      onClick={() => update({ brand_personality: starter })}
                      className="min-h-8 rounded-full border border-border-strong bg-card px-3 text-xs text-muted-foreground transition-colors hover:border-foreground/40 hover:text-foreground"
                    >
                      {starter}
                    </button>
                  ))}
                </div>

                <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-5">
                  <button
                    type="button"
                    onClick={followWebsite}
                    className="inline-flex min-h-9 items-center gap-2 rounded-lg px-2 text-xs font-medium leading-5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                  >
                    <RotateCcw className="size-4" aria-hidden="true" />
                    Follow website for everything
                  </button>
                  <p className="max-w-xs text-right text-xs leading-5 text-muted-foreground">
                    This only changes your draft. Save to make it the new house style.
                  </p>
                </div>
              </div>
            </section>
          </div>
        </div>

        <aside className="min-w-0 xl:sticky xl:top-36">
          <div className="surface overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3.5 sm:px-5">
              <div>
                <h2 className="text-sm font-medium text-foreground">Live tool preview</h2>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Check the moments visitors actually see.
                </p>
              </div>
              <div className="flex items-center gap-1 rounded-lg border border-border bg-n-50 p-1">
                {(
                  [
                    ["desktop", Monitor, "Desktop preview"],
                    ["mobile", Smartphone, "Mobile preview"],
                  ] as const
                ).map(([value, Icon, label]) => (
                  <button
                    key={value}
                    type="button"
                    aria-label={label}
                    aria-pressed={previewDevice === value}
                    onClick={() => setPreviewDevice(value)}
                    className={`grid size-8 place-items-center rounded-md transition-colors ${
                      previewDevice === value
                        ? "bg-card text-foreground shadow-raised"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    <Icon className="size-4" aria-hidden="true" />
                  </button>
                ))}
              </div>
            </div>

            <div className="flex gap-1 overflow-x-auto border-b border-border px-4 pt-2 sm:px-5">
              {(
                [
                  ["question", "Question"],
                  ["result", "Result"],
                  ["lead", "Lead capture"],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={previewMode === value}
                  onClick={() => setPreviewMode(value)}
                  className={`relative min-h-10 shrink-0 px-3 text-sm transition-colors ${
                    previewMode === value
                      ? "font-medium text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {label}
                  {previewMode === value && (
                    <span className="absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-foreground" />
                  )}
                </button>
              ))}
            </div>

            <div className="bg-n-100 p-3 sm:p-5">
              <BrandPreview
                draft={draft}
                pairings={data.font_pairings}
                mode={previewMode}
                device={previewDevice}
              />
            </div>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="flex items-start gap-3 border-t border-border pt-3">
              <Laptop className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <p className="text-xs leading-5 text-muted-foreground">
                New tools receive this house style when Magnitai builds them.
              </p>
            </div>
            <div className="flex items-start gap-3 border-t border-border pt-3">
              <Sparkles
                className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                aria-hidden="true"
              />
              <p className="text-xs leading-5 text-muted-foreground">
                Existing tools keep their current design until you regenerate them.
              </p>
            </div>
          </div>
        </aside>
      </div>
    </>
  );
};
*/
