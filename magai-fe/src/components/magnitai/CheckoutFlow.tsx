import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Check,
  Loader2,
  RefreshCw,
  SlidersHorizontal,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  useBuildWidget,
  useClaimGuestConcept,
  useCreateCheckout,
  useGuestConcepts,
  useReadSite,
  useWidget,
  type ArchitectOutput,
  type CreationBrief,
  type CuratedConcept,
  type SiteRead,
  type WidgetKind,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  journeyDomain,
  loadSavedJourney,
  saveJourney,
  type SavedJourney,
} from "@/lib/journey-storage";
import { AuthGateDialog } from "./AuthGateDialog";
import { BuildPathChooser } from "./BuildPathChooser";
import { DecisionPreview } from "./DecisionPreview";
import { GuidedBuilder } from "./GuidedBuilder";

const KIND_LABELS: Record<WidgetKind, string> = {
  roi_calculator: "Value calculator",
  readiness_quiz: "Readiness check",
  competitive_comparison: "Guided comparison",
  audit_tool: "Instant audit",
  interactive_checklist: "Action plan",
};

const DEFAULT_BRIEF: CreationBrief = {
  mode: "autopilot",
  intent: "",
  audience: "",
  goal: "capture_qualified_leads",
  offer: "",
  visitor_question: "",
  preferred_type: null,
  tone: "match_site",
  result_style: "recommendation",
  question_count: 4,
  instructions: "",
};

type GuidedBrief = Omit<CreationBrief, "mode">;

const GENERATION_WORK = [
  {
    title: "Page understanding",
    body: "The offer, audience and decision visitors are trying to make.",
  },
  {
    title: "Brand match",
    body: "The language, colours and visual cues that make the result feel native.",
  },
];

function normalizeUrl(raw: string): string {
  const trimmed = raw
    .trim()
    .replace(/^https?:\/\//i, "")
    .replace(/\/+$/, "");
  return trimmed ? `https://${trimmed}` : "";
}

function domainOf(url: string): string {
  return journeyDomain(url);
}

function readCopy(architect: ArchitectOutput, key: string, fallback: string): string {
  const value = architect.copywriting?.[key];
  return typeof value === "string" && value.trim() ? value : fallback;
}

function LegacyPreviewBody({ concept }: { concept: CuratedConcept }) {
  const { architect } = concept;
  const brand = architect.brand;
  const kind = architect.widget_type;
  const headline = readCopy(architect, "headline", concept.blueprint.title);
  const subheadline = readCopy(
    architect,
    "subheadline",
    "A short, useful answer built around your visitor's decision.",
  );
  const cta = readCopy(architect, "cta", "See my result");

  return (
    <div
      className="min-h-[25rem] overflow-hidden rounded-[1.15rem] border p-5 sm:p-6"
      style={{
        color: brand.secondary_color,
        background: brand.background_color,
        borderColor: `color-mix(in srgb, ${brand.primary_color} 16%, transparent)`,
        fontFamily: `${brand.font_body}, system-ui, sans-serif`,
      }}
    >
      <div className="flex items-center justify-between border-b border-current/10 pb-4">
        <span
          className="text-sm font-semibold"
          style={{ color: brand.primary_color, fontFamily: `${brand.font_headings}, sans-serif` }}
        >
          {KIND_LABELS[concept.blueprint.type]}
        </span>
        <span className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-[0.14em] opacity-55">
          <span
            className="size-1.5 rounded-full"
            style={{ background: brand.accent_color }}
            aria-hidden="true"
          />
          Preview
        </span>
      </div>

      <div className="mx-auto max-w-[27rem] py-8 text-center">
        <h3
          className="text-[clamp(1.55rem,3vw,2.1rem)] font-semibold leading-[1.03] tracking-[-0.045em]"
          style={{ color: brand.primary_color, fontFamily: `${brand.font_headings}, sans-serif` }}
        >
          {headline}
        </h3>
        <p className="mx-auto mt-3 max-w-sm text-xs leading-5 opacity-65">{subheadline}</p>

        {kind === "roi_calculator" && (
          <div className="mt-7 text-left">
            <div className="flex justify-between text-[11px] opacity-65">
              <span>Monthly opportunity</span>
              <span>24</span>
            </div>
            <div className="relative mt-3 h-1.5 overflow-hidden rounded-full bg-current/10">
              <span
                className="absolute inset-y-0 left-0 w-[62%] rounded-full"
                style={{ background: brand.accent_color }}
              />
            </div>
            <div className="mt-6 border-t border-current/10 pt-5">
              <span className="text-[10px] uppercase tracking-[0.12em] opacity-55">
                Visitor outcome
              </span>
              <strong
                className="mt-1 block text-3xl tracking-[-0.05em]"
                style={{ color: brand.primary_color }}
              >
                Clear next step
              </strong>
            </div>
          </div>
        )}

        {kind === "readiness_quiz" && (
          <div className="mt-7 text-left">
            <span className="text-[10px] font-medium uppercase tracking-[0.12em] opacity-55">
              Question 01 / 04
            </span>
            <p className="mt-2 text-sm font-semibold">What matters most right now?</p>
            <div className="mt-3 grid gap-2">
              {["More qualified enquiries", "A clearer customer journey"].map((item, index) => (
                <div
                  key={item}
                  className="flex items-center justify-between rounded-lg border border-current/10 px-3 py-2.5 text-xs"
                >
                  {item}
                  {index === 0 && (
                    <Check className="size-3.5" style={{ color: brand.accent_color }} />
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {kind === "competitive_comparison" && (
          <div className="mt-7 grid grid-cols-2 gap-2 text-left">
            {["Your current path", "A focused path"].map((item, index) => (
              <div
                key={item}
                className="rounded-lg border border-current/10 p-3"
                style={index === 1 ? { background: `${brand.accent_color}18` } : undefined}
              >
                <span className="text-[10px] opacity-55">{item}</span>
                <strong className="mt-5 block text-lg">
                  {index === 0 ? "6 steps" : "2 steps"}
                </strong>
                <span className="text-[10px] opacity-55">
                  {index === 0 ? "More friction" : "Clearer action"}
                </span>
              </div>
            ))}
          </div>
        )}

        {(kind === "audit_tool" || kind === "interactive_checklist") && (
          <div className="mt-7 space-y-2 text-left">
            {["Offer clarity", "Decision friction", "Next best action"].map((item, index) => (
              <div
                key={item}
                className="flex items-center gap-3 rounded-lg border border-current/10 px-3 py-2.5 text-xs"
              >
                <span
                  className="grid size-5 place-items-center rounded-full text-[10px]"
                  style={{
                    background: index < 2 ? brand.accent_color : `${brand.primary_color}12`,
                    color: index < 2 ? brand.background_color : brand.primary_color,
                  }}
                >
                  {index < 2 ? "✓" : "3"}
                </span>
                <span>{item}</span>
              </div>
            ))}
          </div>
        )}

        <div
          className="mt-7 flex h-10 items-center justify-center rounded-lg text-xs font-semibold"
          style={{ background: brand.accent_color, color: brand.background_color }}
        >
          {cta}
        </div>
      </div>
    </div>
  );
}

function PreviewBody({ concept }: { concept: CuratedConcept }) {
  const decision = concept.architect.decision;
  if (!decision) {
    return <LegacyPreviewBody concept={concept} />;
  }
  const { architect } = concept;
  const { brand } = architect;
  return (
    <div
      className="min-h-[25rem] overflow-hidden rounded-[1.15rem] border p-5 sm:p-6"
      style={{
        color: brand.secondary_color,
        background: brand.background_color,
        borderColor: `color-mix(in srgb, ${brand.primary_color} 16%, transparent)`,
        fontFamily: `${brand.font_body}, system-ui, sans-serif`,
      }}
    >
      <div className="flex items-center justify-between border-b border-current/10 pb-4">
        <span
          className="text-sm font-semibold"
          style={{ color: brand.primary_color, fontFamily: `${brand.font_headings}, sans-serif` }}
        >
          {KIND_LABELS[concept.blueprint.type]}
        </span>
        <span className="text-[10px] font-medium uppercase tracking-[0.14em] opacity-55">
          Try it
        </span>
      </div>
      <h3
        className="mx-auto mt-7 max-w-[24ch] text-balance text-center text-[clamp(1.35rem,3vw,1.9rem)] font-semibold leading-[1.05] tracking-[-0.045em]"
        style={{ color: brand.primary_color, fontFamily: `${brand.font_headings}, sans-serif` }}
      >
        {decision.buyer_question}
      </h3>
      <DecisionPreview architect={architect} compact />
    </div>
  );
}

function ConceptCard({
  concept,
  index,
  selected,
  onChoose,
  choosing,
}: {
  concept: CuratedConcept;
  index: number;
  selected: boolean;
  onChoose: () => void;
  choosing: boolean;
}) {
  return (
    <article
      className={`group rounded-[1.55rem] border bg-card p-3 shadow-card transition-[border-color,box-shadow,transform] duration-300 ${
        selected
          ? "border-foreground shadow-float"
          : "border-border hover:-translate-y-1 hover:border-foreground/30 hover:shadow-float"
      }`}
    >
      <PreviewBody concept={concept} />
      <div className="px-2 pb-2 pt-5 sm:px-3">
        <div className="flex items-center justify-between gap-4">
          <div>
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
              Direction {String(index + 1).padStart(2, "0")}
            </span>
            <h2 className="mt-1.5 text-xl font-medium tracking-[-0.035em] text-foreground">
              {concept.blueprint.title}
            </h2>
          </div>
          <span className="shrink-0 rounded-full bg-secondary px-3 py-1.5 text-[11px] font-medium text-muted-foreground">
            {KIND_LABELS[concept.blueprint.type]}
          </span>
        </div>

        <p className="mt-3 line-clamp-2 text-sm leading-6 text-muted-foreground">
          {concept.blueprint.description}
        </p>

        <button
          type="button"
          onClick={onChoose}
          disabled={choosing}
          className={`mt-5 flex h-12 w-full items-center justify-center gap-2 rounded-xl text-sm font-semibold transition-colors ${
            selected
              ? "bg-foreground text-background"
              : "border border-border text-foreground hover:border-foreground/35 hover:bg-secondary"
          }`}
        >
          {choosing ? (
            <Loader2 className="size-4 animate-spin" />
          ) : selected ? (
            <>
              <Check className="size-4" /> Chosen direction
            </>
          ) : (
            <>
              Choose this direction <ArrowRight className="size-4" />
            </>
          )}
        </button>
      </div>
    </article>
  );
}

/**
 * Proof that the site was read, shown while the slow half runs.
 *
 * The crawl lands in about five seconds and the directions take another fifty.
 * Filling that gap with a spinner asks the visitor to take it on faith; filling
 * it with their own business name, their own brand colours and their own
 * headlines shows them. Nothing here is predicted — every value is observed, so
 * the panel simply does not appear until there is something true to put in it.
 */
function SiteReadPanel({ read }: { read: SiteRead }) {
  return (
    <section className="mt-9 rounded-[1.15rem] border border-border bg-card p-5 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="text-sm font-medium text-foreground">
          Read {read.business_name || read.domain}
        </h2>
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
          {read.pages_read} pages · {read.signals_found} signals
        </span>
      </div>

      {read.colors.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted-foreground">Your colours</span>
          {read.colors.map((color) => (
            <span
              key={color}
              className="size-5 rounded-full border border-foreground/15"
              style={{ background: color }}
              title={color}
            />
          ))}
        </div>
      )}

      {read.fonts.length > 0 && (
        <p className="mt-2.5 text-xs text-muted-foreground">
          Your type <span className="text-foreground">{read.fonts.join(", ")}</span>
        </p>
      )}

      {read.highlights.length > 0 && (
        <ul className="mt-4 grid gap-1.5 border-t border-border pt-4">
          {read.highlights.slice(0, 3).map((line, index) => (
            <li key={index} className="truncate text-xs text-muted-foreground">
              “{line}”
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function GenerationState({
  domain,
  mode,
  read,
}: {
  domain: string;
  mode: "autopilot" | "guided";
  read: SiteRead | null;
}) {
  const website = domain || "your website";
  const guided = mode === "guided";
  const work = [
    ...GENERATION_WORK,
    {
      title: guided ? "Two recommendations" : "Best-fit recommendation",
      body: guided
        ? "Two useful conversion approaches with different strategic angles."
        : "One complete direction selected from the strongest opportunities.",
    },
  ];

  return (
    <div className="mx-auto min-h-[100svh] max-w-[72rem] px-5 pb-20 pt-24 sm:px-6 sm:pt-28 lg:px-8">
      <section
        className="mx-auto max-w-[50rem]"
        aria-busy="true"
        aria-describedby="generation-description"
      >
        <div className="flex items-center justify-between gap-6 text-[11px] font-medium text-muted-foreground">
          <span className="uppercase tracking-[0.12em]">AI conversion builder</span>
          <span>Step 2 of 3 · Building</span>
        </div>
        <div
          role="progressbar"
          aria-label="Builder journey"
          aria-valuemin={1}
          aria-valuemax={3}
          aria-valuenow={2}
          className="mt-3 h-0.5 overflow-hidden rounded-full bg-border"
        >
          <span className="block h-full w-2/3 rounded-full bg-foreground" />
        </div>

        <main className="pt-10 sm:pt-14">
          <div
            role="status"
            aria-live="polite"
            className="inline-flex items-center gap-2.5 text-sm font-medium text-foreground"
          >
            <span className="grid size-8 place-items-center rounded-full border border-border-strong bg-card">
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            </span>
            {guided ? "Creating your two directions" : "Finding the strongest direction"}
          </div>

          <span className="mt-7 block font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
            {website}
          </span>
          <h1 className="mt-3 max-w-[17ch] font-heading text-[clamp(2.6rem,6vw,4.5rem)] font-medium leading-[0.96] tracking-[-0.055em] text-foreground">
            {guided
              ? `Building two directions for ${website}.`
              : `Building the best direction for ${website}.`}
          </h1>
          <p
            id="generation-description"
            className="mt-5 max-w-[40rem] text-[15px] leading-7 text-muted-foreground sm:text-base"
          >
            {guided
              ? "Magnitai is applying your brief to the page and preparing two distinct recommendations for you to compare."
              : "Magnitai is reading the page, matching its brand and choosing the interaction most useful to its visitors."}
          </p>

          {read && <SiteReadPanel read={read} />}

          <section className="mt-9 border-y border-border" aria-labelledby="generation-work-title">
            <h2
              id="generation-work-title"
              className="border-b border-border py-4 text-sm font-medium text-foreground"
            >
              What Magnitai is preparing
            </h2>
            <ol>
              {work.map((item, index) => (
                <li
                  key={item.title}
                  className="grid grid-cols-[2rem_minmax(0,1fr)] gap-3 border-b border-border py-4 last:border-b-0"
                >
                  <span className="pt-0.5 font-mono text-[10px] text-muted-foreground">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span>
                    <strong className="block text-sm font-medium text-foreground">
                      {item.title}
                    </strong>
                    <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                      {item.body}
                    </span>
                  </span>
                </li>
              ))}
            </ol>
          </section>

          <p className="mt-6 text-xs leading-5 text-muted-foreground">
            Keep this tab open. The next screen will appear automatically when the build is ready.
          </p>
        </main>
      </section>
    </div>
  );
}

function FineTunePanel({
  architect,
  onChange,
}: {
  architect: ArchitectOutput;
  onChange: (next: ArchitectOutput) => void;
}) {
  const decision = architect.decision;
  const headline = String(architect.copywriting?.headline || "");

  const fieldClass =
    "mt-2 h-11 w-full rounded-xl border border-border bg-background px-3 text-sm text-foreground outline-none transition focus:border-foreground/40";

  return (
    <section className="mt-6 rounded-[1.25rem] border border-border bg-card p-4 shadow-card">
      <div className="flex items-start justify-between gap-4">
        <div>
          <span className="font-mono text-[9px] uppercase tracking-[0.16em] text-muted-foreground">
            Human control
          </span>
          <h2 className="mt-1 text-base font-medium text-foreground">Fine-tune the experience</h2>
        </div>
        <SlidersHorizontal className="size-4 text-muted-foreground" aria-hidden="true" />
      </div>

      <div className="mt-5 space-y-4">
        <label className="block text-[11px] font-medium text-muted-foreground">
          Opening headline
          <input
            value={headline}
            maxLength={180}
            onChange={(event) =>
              onChange({
                ...architect,
                copywriting: { ...architect.copywriting, headline: event.target.value },
              })
            }
            className={fieldClass}
          />
        </label>

        {decision && (
          <>
            <label className="block text-[11px] font-medium text-muted-foreground">
              Visitor decision
              <input
                value={decision.buyer_question}
                maxLength={220}
                onChange={(event) =>
                  onChange({
                    ...architect,
                    decision: { ...decision, buyer_question: event.target.value },
                  })
                }
                className={fieldClass}
              />
            </label>

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block text-[11px] font-medium text-muted-foreground">
                Result style
                <select
                  value={decision.mechanism}
                  onChange={(event) =>
                    onChange({
                      ...architect,
                      decision: {
                        ...decision,
                        mechanism: event.target.value as typeof decision.mechanism,
                      },
                    })
                  }
                  className={fieldClass}
                >
                  <option value="estimate">Estimate</option>
                  <option value="diagnose">Diagnosis</option>
                  <option value="advise">Recommendation</option>
                </select>
              </label>
              <label className="block text-[11px] font-medium text-muted-foreground">
                Final action
                <input
                  value={decision.primary_cta}
                  maxLength={80}
                  onChange={(event) =>
                    onChange({
                      ...architect,
                      copywriting: { ...architect.copywriting, cta: event.target.value },
                      decision: { ...decision, primary_cta: event.target.value },
                    })
                  }
                  className={fieldClass}
                />
              </label>
            </div>

            <div>
              <span className="text-[11px] font-medium text-muted-foreground">
                Questions visitors answer
              </span>
              <div className="mt-2 space-y-2">
                {decision.questions.map((question, index) => (
                  <label
                    key={question.id}
                    className="flex items-center gap-3 rounded-xl border border-border bg-background px-3 py-2"
                  >
                    <span className="font-mono text-[9px] text-muted-foreground">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <input
                      value={question.label}
                      maxLength={180}
                      aria-label={`Question ${index + 1}`}
                      onChange={(event) => {
                        const questions = decision.questions.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, label: event.target.value } : item,
                        );
                        onChange({
                          ...architect,
                          decision: { ...decision, questions },
                        });
                      }}
                      className="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none"
                    />
                  </label>
                ))}
              </div>
            </div>
          </>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-[11px] font-medium text-muted-foreground">
            Voice
            <input
              value={architect.brand.tone}
              maxLength={120}
              onChange={(event) =>
                onChange({
                  ...architect,
                  brand: { ...architect.brand, tone: event.target.value },
                })
              }
              className={fieldClass}
            />
          </label>
          <label className="block text-[11px] font-medium text-muted-foreground">
            Visual energy
            <select
              value={architect.visual_language.visual_energy}
              onChange={(event) =>
                onChange({
                  ...architect,
                  visual_language: {
                    ...architect.visual_language,
                    visual_energy: event.target.value,
                  },
                })
              }
              className={fieldClass}
            >
              <option value="calm">Calm</option>
              <option value="balanced">Balanced</option>
              <option value="bold">Bold</option>
            </select>
          </label>
        </div>

        <div className="grid grid-cols-2 gap-3">
          {[
            ["Accent", "accent_color"],
            ["Background", "background_color"],
          ].map(([label, key]) => {
            const color = architect.brand[key as "accent_color" | "background_color"];
            const safeColor = /^#[0-9a-f]{6}$/i.test(color) ? color : "#171a21";
            return (
              <label
                key={key}
                className="flex items-center justify-between rounded-xl border border-border bg-background px-3 py-3 text-[11px] font-medium text-muted-foreground"
              >
                {label}
                <input
                  type="color"
                  value={safeColor}
                  aria-label={`${label} color`}
                  onChange={(event) =>
                    onChange({
                      ...architect,
                      brand: { ...architect.brand, [key]: event.target.value },
                    })
                  }
                  className="size-7 cursor-pointer rounded-lg border-0 bg-transparent p-0"
                />
              </label>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export function CheckoutFlow({
  onBuildStart,
  onBack,
  initialSite,
}: {
  onBuildStart: (widgetId: string) => void;
  onBack: () => void;
  initialSite?: string;
}) {
  const { isAuthenticated, user } = useAuth();
  const [hydrated, setHydrated] = useState(false);
  const [input, setInput] = useState("");
  const [journey, setJourney] = useState<SavedJourney | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [gateOpen, setGateOpen] = useState(false);
  const [autopilotBuilding, setAutopilotBuilding] = useState(false);
  const [siteRead, setSiteRead] = useState<SiteRead | null>(null);
  const [shaping, setShaping] = useState(false);
  const [siteUrl, setSiteUrl] = useState("");
  const [fineTuning, setFineTuning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const claimStarted = useRef(false);

  const guestConcepts = useGuestConcepts();
  const readSite = useReadSite();
  const claimGuest = useClaimGuestConcept();
  const build = useBuildWidget();
  const checkout = useCreateCheckout();
  const widget = useWidget(journey?.widgetId ?? "");

  useEffect(() => {
    const saved = loadSavedJourney();
    setJourney(saved);
    if (saved) {
      setInput(domainOf(saved.target_url));
      // Come back to the desk they left, on the side they left it.
    } else if (initialSite) {
      setInput(initialSite.replace(/^https?:\/\//i, ""));
    }
    setHydrated(true);
  }, [initialSite]);

  useEffect(() => {
    if (
      !hydrated ||
      !isAuthenticated ||
      !journey ||
      journey.selectedIndex === null ||
      journey.widgetId ||
      claimStarted.current
    ) {
      return;
    }

    claimStarted.current = true;
    claimGuest
      .mutateAsync({
        sessionToken: journey.session_token,
        selectedIndex: journey.selectedIndex,
      })
      .then((claimed) => {
        const updated = { ...journey, widgetId: claimed.widget_id };
        setJourney(updated);
        saveJourney(updated);
      })
      .catch((claimError) => {
        claimStarted.current = false;
        setError(
          claimError instanceof Error
            ? claimError.message
            : "We couldn't save that direction. Please try again.",
        );
      });
  }, [claimGuest, hydrated, isAuthenticated, journey]);

  /**
   * Read the site, then propose directions — without an account.
   *
   * This used to open the signup dialog first and analyse afterwards, which
   * contradicted the promise on every page that leads here ("No account needed
   * to look", "Choose before signup"). Nothing about the analysis needed an
   * identity: `/read-site` and `/guest-concepts` are both anonymous and rate
   * limited, and `claim-guest` already carries the result across the account
   * boundary once there is one. The gate belongs at "keep this", not at "look".
   *
   * The read is awaited separately from the directions on purpose. It returns in
   * about five seconds against roughly sixty for the whole call, so the interval
   * that used to be a blank screen now shows the visitor their own business
   * name, their own brand colours and their own headlines — evidence that the
   * site was genuinely read, rather than a spinner asking them to believe it.
   */
  const previewAnonymously = useCallback(
    async (url: string, brief: CreationBrief) => {
      setError(null);
      setInput(domainOf(url));
      setSiteRead(null);
      setAutopilotBuilding(true);

      try {
        // Best-effort: a failed read costs the reassurance, not the run. The
        // directions call re-crawls anyway, so there is nothing to recover.
        void readSite
          .mutateAsync(url)
          .then(setSiteRead)
          .catch(() => undefined);

        const response = await guestConcepts.mutateAsync({ url, brief });
        const next: SavedJourney = { ...response, selectedIndex: null, widgetId: null };
        setJourney(next);
        saveJourney(next);
        setAutopilotBuilding(false);
        setShaping(false);
        setReviewing(true);
      } catch (requestError) {
        setAutopilotBuilding(false);
        setError(
          requestError instanceof Error
            ? requestError.message
            : "We couldn't read that website. Please try another.",
        );
      }
    },
    [guestConcepts, readSite],
  );

  function startPath(url: string) {
    void previewAnonymously(url, { ...DEFAULT_BRIEF, mode: "autopilot" });
  }

  function customizePath(url: string) {
    setInput(domainOf(url));
    setSiteUrl(url);
    setError(null);
    setShaping(true);
  }

  function submitGuidedBrief(brief: GuidedBrief) {
    // Same rule as the hands-off path: shaping a brief is still looking, and
    // looking does not require an account.
    void previewAnonymously(siteUrl, { ...brief, mode: "guided" });
  }

  function handleChoose(index: number) {
    if (!journey) return;
    const updated = { ...journey, selectedIndex: index };
    setJourney(updated);
    saveJourney(updated);
    setReviewing(false);

    // The gate opens over the work rather than navigating away from it. On
    // success the claim effect above notices the session and adopts this exact
    // saved concept, so there is nothing to redirect back to.
    if (!isAuthenticated) setGateOpen(true);
  }

  function updateSelectedArchitect(next: ArchitectOutput) {
    if (!journey || journey.selectedIndex === null) return;
    const concepts = journey.concepts.map((concept, index) =>
      index === journey.selectedIndex ? { ...concept, architect: next } : concept,
    ) as SavedJourney["concepts"];
    const updated = { ...journey, concepts };
    setJourney(updated);
    saveJourney(updated);
  }

  async function handleBuild() {
    if (!journey?.widgetId || journey.selectedIndex === null) return;
    if (!user?.email_verified) {
      setError("Check your inbox and verify your email before building.");
      return;
    }

    const selected = journey.concepts[journey.selectedIndex];
    setError(null);
    try {
      if (widget.data?.entitlement_status === "checkout_pending") {
        setError("Payment is being confirmed. This page will update automatically.");
        return;
      }
      if (widget.data && !widget.data.can_build) {
        const origin = window.location.origin;
        const session = await checkout.mutateAsync({
          widgetId: journey.widgetId,
          successUrl: `${origin}/build?checkout=success`,
          cancelUrl: `${origin}/build?checkout=cancelled`,
        });
        window.location.assign(session.checkout_url);
        return;
      }
      await build.mutateAsync({
        widgetId: journey.widgetId,
        widgetType: selected.blueprint.type,
        architectOverride: selected.architect,
      });
      saveJourney(null);
      onBuildStart(journey.widgetId);
    } catch (buildError) {
      setError(buildError instanceof Error ? buildError.message : "We couldn't start the build.");
    }
  }

  function startAgain() {
    saveJourney(null);
    setJourney(null);
    setInput("");
    setReviewing(false);
    setAutopilotBuilding(false);
    setShaping(false);
    setSiteUrl("");
    setFineTuning(false);
    setError(null);
    claimStarted.current = false;
    // The chooser owns the website field now and autofocuses it on mount, so
    // returning to it is enough — there is no ref to reach across for.
  }

  if (!hydrated) {
    return <div className="min-h-screen" />;
  }

  if (autopilotBuilding || guestConcepts.isPending) {
    return (
      <GenerationState
        domain={siteRead?.domain || domainOf(normalizeUrl(input))}
        mode={autopilotBuilding ? "autopilot" : "guided"}
        read={siteRead}
      />
    );
  }

  if (shaping && !journey) {
    return (
      <>
        <GuidedBuilder
          domain={domainOf(siteUrl || normalizeUrl(input))}
          pending={guestConcepts.isPending}
          error={error}
          onBack={() => {
            setShaping(false);
            setError(null);
          }}
          onBuild={submitGuidedBrief}
        />
      </>
    );
  }

  const selected =
    journey?.selectedIndex !== null && journey?.selectedIndex !== undefined
      ? journey.concepts[journey.selectedIndex]
      : null;
  const showingComparison = Boolean(journey && (!selected || reviewing));

  /*
   * Rendered by both journey screens rather than one.
   *
   * Choosing a direction sets `selectedIndex`, which flips this component from
   * the comparison to the selected-direction view in the same commit that opens
   * the gate — so a dialog mounted only under the comparison branch unmounted
   * on the very interaction that was meant to show it.
   */
  const gate = journey ? (
    <AuthGateDialog
      open={gateOpen}
      onOpenChange={setGateOpen}
      conceptTitle={
        journey.selectedIndex !== null
          ? journey.concepts[journey.selectedIndex].blueprint.title
          : null
      }
      domain={domainOf(journey.target_url)}
    />
  ) : null;

  if (showingComparison && journey) {
    return (
      <div className="mx-auto min-h-screen max-w-6xl px-5 pb-24 pt-28 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div>
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
              {domainOf(journey.target_url)} · 2 ready
            </span>
            <h1 className="mt-3 max-w-2xl font-heading text-4xl font-medium tracking-[-0.05em] text-foreground sm:text-5xl">
              Choose your AI-built direction.
            </h1>
          </div>
          <button
            type="button"
            onClick={startAgain}
            className="inline-flex h-10 items-center gap-2 rounded-full border border-border px-4 text-xs font-medium text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground"
          >
            <RefreshCw className="size-3.5" /> Different website
          </button>
        </div>

        {error && (
          <div
            role="alert"
            className="mt-7 flex items-center gap-2 rounded-xl border border-destructive/25 bg-destructive/5 px-4 py-3 text-sm text-destructive"
          >
            <AlertCircle className="size-4 shrink-0" />
            {error}
          </div>
        )}

        {/*
          Placed here rather than only on the landing page because this is where
          the visitor first weighs keeping the thing. They have seen the work; the
          open question is whether it stays good, and the honest answer to that is
          the only part of the pitch a competitor cannot match right now.
        */}
        <p className="mt-8 flex items-start gap-2.5 rounded-xl border border-border bg-secondary/50 px-4 py-3 text-sm leading-6 text-muted-foreground">
          <RefreshCw className="mt-0.5 size-4 shrink-0 text-foreground" aria-hidden="true" />
          <span>
            Whichever you keep, Magnitai re-reads your site on a schedule and rebuilds the tool if
            your brand changes or the address stops answering — at the same embed address, so you
            never touch your page again.
          </span>
        </p>

        <div className="mt-8 grid gap-6 lg:grid-cols-2">
          {journey.concepts.map((concept, index) => (
            <ConceptCard
              key={`${concept.blueprint.type}-${index}`}
              concept={concept}
              index={index}
              selected={journey.selectedIndex === index}
              onChoose={() => handleChoose(index)}
              choosing={claimGuest.isPending && journey.selectedIndex === index}
            />
          ))}
        </div>

        {gate}
      </div>
    );
  }

  if (journey && selected) {
    const saving = isAuthenticated && !journey.widgetId;
    return (
      <div className="mx-auto min-h-screen max-w-6xl px-5 pb-24 pt-28 sm:px-6 lg:px-8">
        <button
          type="button"
          onClick={() => setReviewing(true)}
          className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> Review both directions
        </button>

        <div className="mt-8 grid items-start gap-8 lg:grid-cols-[minmax(0,1.3fr)_minmax(20rem,0.7fr)]">
          <div className="rounded-[1.7rem] border border-border bg-card p-3 shadow-card">
            <PreviewBody concept={selected} />
          </div>

          <aside
            className={`lg:sticky lg:top-28 ${
              fineTuning ? "lg:max-h-[calc(100vh-8rem)] lg:overflow-y-auto lg:pr-1" : ""
            }`}
          >
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
              Selected direction
            </span>
            <h1 className="mt-3 font-heading text-4xl font-medium tracking-[-0.05em] text-foreground">
              {selected.blueprint.title}
            </h1>
            <p className="mt-3 text-sm text-muted-foreground">Ready to build.</p>

            <div className="mt-7 grid grid-cols-3 border-y border-border py-5">
              {[
                ["Format", KIND_LABELS[selected.blueprint.type]],
                ["Tone", selected.architect.brand.tone],
                ["Status", "Ready"],
              ].map(([label, value]) => (
                <div
                  key={label}
                  className="min-w-0 border-r border-border px-3 first:pl-0 last:border-0 last:pr-0"
                >
                  <span className="block text-[9px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
                    {label}
                  </span>
                  <strong
                    className="mt-1 block truncate text-xs font-medium text-foreground"
                    title={value}
                  >
                    {value}
                  </strong>
                </div>
              ))}
            </div>

            <button
              type="button"
              onClick={() => setFineTuning((current) => !current)}
              aria-expanded={fineTuning}
              className="mt-5 flex h-11 w-full items-center justify-between rounded-xl border border-border bg-card px-4 text-sm font-medium text-foreground transition hover:border-foreground/25"
            >
              <span className="flex items-center gap-2">
                <SlidersHorizontal className="size-4" />
                {fineTuning ? "Close fine-tuning" : "Choose the exact details"}
              </span>
              <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">
                Optional
              </span>
            </button>

            {fineTuning && (
              <FineTunePanel architect={selected.architect} onChange={updateSelectedArchitect} />
            )}

            {error && (
              <div
                role="alert"
                className="mt-5 flex items-start gap-2 rounded-xl border border-destructive/25 bg-destructive/5 px-4 py-3 text-sm text-destructive"
              >
                <AlertCircle className="mt-0.5 size-4 shrink-0" />
                {error}
              </div>
            )}

            <button
              type="button"
              onClick={handleBuild}
              disabled={
                saving ||
                build.isPending ||
                checkout.isPending ||
                widget.isLoading ||
                widget.data?.entitlement_status === "checkout_pending" ||
                !journey.widgetId
              }
              className="group mt-6 flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-brand-solid px-6 text-sm font-semibold text-white transition duration-200 hover:-translate-y-0.5 hover:bg-brand-hover hover:shadow-float disabled:pointer-events-none disabled:opacity-55"
            >
              {saving || build.isPending || checkout.isPending ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  {saving
                    ? "Saving your direction"
                    : checkout.isPending
                      ? "Opening secure checkout"
                      : "Starting the build"}
                </>
              ) : (
                <>
                  {widget.data && !widget.data.can_build
                    ? widget.data.entitlement_status === "checkout_pending"
                      ? "Confirming payment"
                      : "Launch this tool · $99"
                    : "Build this direction"}
                  <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
                </>
              )}
            </button>
          </aside>
        </div>
        {gate}
      </div>
    );
  }

  return (
    <>
      <BuildPathChooser
        initialSite={input || initialSite}
        pending={autopilotBuilding || guestConcepts.isPending}
        requestError={error}
        onStart={startPath}
        onCustomize={customizePath}
        onClearError={() => setError(null)}
        onBack={onBack}
      />
    </>
  );
}
