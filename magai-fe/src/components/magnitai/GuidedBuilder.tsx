import { ArrowLeft, ArrowRight, Check, Lightbulb, Loader2, Sparkles } from "lucide-react";
import { useState, type ReactNode } from "react";

import type { CreationBrief, WidgetKind } from "@/lib/api";

type Delegable =
  | "preferred_type"
  | "audience"
  | "visitor_question"
  | "goal"
  | "offer"
  | "tone"
  | "result_style"
  | "question_count";

const DEFAULTS: Pick<CreationBrief, Delegable> = {
  preferred_type: null,
  audience: "",
  visitor_question: "",
  goal: "capture_qualified_leads",
  offer: "",
  tone: "match_site",
  result_style: "recommendation",
  question_count: 4,
};

const FIELD_LABELS: Record<Delegable, string> = {
  preferred_type: "Tool format",
  audience: "Audience",
  visitor_question: "Visitor question",
  goal: "Business goal",
  offer: "Offer",
  tone: "Tone",
  result_style: "Result",
  question_count: "Length",
};

const TYPES: Array<{ value: WidgetKind; label: string; hint: string }> = [
  { value: "roi_calculator", label: "Calculator", hint: "Works out a useful number" },
  { value: "readiness_quiz", label: "Quiz", hint: "Scores and recommends" },
  { value: "audit_tool", label: "Audit", hint: "Checks and reports back" },
  { value: "competitive_comparison", label: "Comparison", hint: "Compares two paths" },
  { value: "interactive_checklist", label: "Checklist", hint: "Creates a next-step plan" },
];

const GOALS: Array<{ value: CreationBrief["goal"]; label: string }> = [
  { value: "capture_qualified_leads", label: "Qualify leads" },
  { value: "book_more_calls", label: "Book more calls" },
  { value: "educate_buyers", label: "Educate buyers" },
  { value: "estimate_value", label: "Estimate value" },
  { value: "recommend_next_step", label: "Recommend a next step" },
];

const TONES: Array<{ value: CreationBrief["tone"]; label: string }> = [
  { value: "match_site", label: "Match my site" },
  { value: "warm", label: "Warm" },
  { value: "direct", label: "Direct" },
  { value: "premium", label: "Premium" },
  { value: "technical", label: "Technical" },
  { value: "playful", label: "Playful" },
];

const RESULTS: Array<{ value: CreationBrief["result_style"]; label: string }> = [
  { value: "score", label: "A score" },
  { value: "estimate", label: "An estimate" },
  { value: "recommendation", label: "A recommendation" },
  { value: "comparison", label: "A comparison" },
  { value: "action_plan", label: "An action plan" },
];

const INPUT =
  "h-12 w-full rounded-xl border border-border-strong bg-card px-3.5 text-sm text-foreground outline-none transition-[border-color,box-shadow] placeholder:text-n-400 focus:border-foreground/45 focus:shadow-card";

function Decision({
  id,
  label,
  hint,
  delegated,
  onToggle,
  children,
}: {
  id: string;
  label: string;
  hint: string;
  delegated: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  return (
    <section className="border-t border-border py-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 id={`${id}-label`} className="text-sm font-semibold text-foreground">
            {label}
          </h3>
          <p className="mt-1 max-w-sm text-xs leading-5 text-muted-foreground">{hint}</p>
        </div>
        <button
          type="button"
          onClick={onToggle}
          aria-pressed={delegated}
          className={`inline-flex h-8 shrink-0 items-center gap-1.5 rounded-full border px-3 text-[11px] font-medium transition-colors ${
            delegated
              ? "border-brand-solid/20 bg-brand-wash text-brand-solid"
              : "border-border-strong bg-card text-muted-foreground hover:text-foreground"
          }`}
        >
          <Sparkles className="size-3" aria-hidden="true" />
          {delegated ? "Magnitai decides" : "Let Magnitai decide"}
        </button>
      </div>

      <div className="mt-4">
        {delegated ? (
          <div className="flex items-center gap-2.5 rounded-xl border border-dashed border-border-strong px-3.5 py-3 text-xs leading-5 text-muted-foreground">
            <Sparkles className="size-3.5 shrink-0 text-brand-solid" aria-hidden="true" />
            Magnitai will infer this from the website and the rest of your brief.
          </div>
        ) : (
          children
        )}
      </div>
    </section>
  );
}

export function GuidedBuilder({
  domain,
  pending,
  error,
  onBack,
  onBuild,
}: {
  domain: string;
  pending: boolean;
  error: string | null;
  onBack: () => void;
  onBuild: (brief: Omit<CreationBrief, "mode">) => void;
}) {
  const [intent, setIntent] = useState("");
  const [values, setValues] = useState<Pick<CreationBrief, Delegable>>(DEFAULTS);
  const [instructions, setInstructions] = useState("");
  const [delegated, setDelegated] = useState<Set<Delegable>>(
    () => new Set(Object.keys(DEFAULTS) as Delegable[]),
  );

  const mine = (Object.keys(DEFAULTS) as Delegable[]).filter((key) => !delegated.has(key));
  const yourChoices = [
    ...(intent.trim() ? ["Core idea"] : []),
    ...mine.map((key) => FIELD_LABELS[key]),
    ...(instructions.trim() ? ["Extra direction"] : []),
  ];

  function toggle(key: Delegable) {
    const returningToAi = !delegated.has(key);
    if (returningToAi) {
      setValues((current) => ({ ...current, [key]: DEFAULTS[key] }));
    }
    setDelegated((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function set<K extends Delegable>(key: K, value: Pick<CreationBrief, Delegable>[K]) {
    setValues((current) => ({ ...current, [key]: value }));
  }

  function submit() {
    const brief = {
      ...DEFAULTS,
      intent: intent.trim(),
      instructions: instructions.trim(),
    } as Omit<CreationBrief, "mode">;

    for (const key of mine) {
      (brief as Record<string, unknown>)[key] = values[key];
    }
    onBuild(brief);
  }

  return (
    <div className="mx-auto min-h-[100svh] max-w-6xl px-5 pb-24 pt-24 sm:px-6 sm:pt-28 lg:px-8">
      <button
        type="button"
        onClick={onBack}
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        Back
      </button>

      <div className="mt-8 max-w-3xl">
        <div className="inline-flex items-center gap-2 rounded-full border border-brand-solid/20 bg-brand-wash px-3 py-1.5 text-xs font-medium text-brand-solid">
          <Sparkles className="size-3.5" aria-hidden="true" />
          Guided lead magnet builder
        </div>
        <h1 className="mt-6 font-heading text-[clamp(2.65rem,6vw,4.5rem)] font-medium leading-[0.96] tracking-[-0.055em] text-foreground">
          Shape what matters. Let Magnitai complete the rest.
        </h1>
        <p className="mt-6 max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg sm:leading-8">
          Describe the result your visitor should get. Set any detail that matters and leave the
          rest to Magnitai.
        </p>
      </div>

      <div className="mt-12 grid items-start gap-12 lg:grid-cols-[minmax(0,1fr)_19rem] lg:gap-16">
        <div>
          <section>
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground">
              <Lightbulb className="size-4 text-brand-solid" aria-hidden="true" />
              Start anywhere
            </div>
            <label
              htmlFor="gb-intent"
              className="mt-4 block text-2xl font-semibold tracking-[-0.035em] text-foreground"
            >
              What should Magnitai build?
            </label>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              Write one sentence or a full idea. Leave it blank and Magnitai will recommend the lead
              magnet from your website.
            </p>
            <textarea
              id="gb-intent"
              rows={6}
              maxLength={600}
              value={intent}
              onChange={(event) => setIntent(event.target.value)}
              placeholder="For example: Build a planning tool that helps operations leaders estimate the time and cost they could save. Ask about team size, current workflow and their biggest bottleneck, then recommend a practical next step."
              className="mt-5 w-full resize-y rounded-[1.4rem] border border-border-strong bg-card px-5 py-4 text-base leading-7 text-foreground shadow-card outline-none transition-[border-color,box-shadow] placeholder:text-n-400 focus:border-foreground/45 focus:shadow-float"
            />
          </section>

          <section className="mt-12">
            <div>
              <h2 className="text-2xl font-semibold tracking-[-0.035em] text-foreground">
                Tailor any detail
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                Magnitai can recommend every detail. Take control only where it matters to you.
              </p>
            </div>

            <div className="mt-5 grid gap-x-8 sm:grid-cols-2">
              <Decision
                id="gb-type"
                label="Tool format"
                hint="Choose a familiar format, or describe something different above."
                delegated={delegated.has("preferred_type")}
                onToggle={() => toggle("preferred_type")}
              >
                <div role="group" aria-labelledby="gb-type-label" className="grid gap-2">
                  {TYPES.map((type) => {
                    const active = values.preferred_type === type.value;
                    return (
                      <button
                        key={type.value}
                        type="button"
                        onClick={() => set("preferred_type", type.value)}
                        aria-pressed={active}
                        className={`rounded-xl border px-3.5 py-3 text-left transition-[border-color,background-color] ${
                          active
                            ? "border-foreground bg-brand-wash"
                            : "border-border-strong bg-card hover:border-foreground/30"
                        }`}
                      >
                        <span className="block text-sm font-medium text-foreground">
                          {type.label}
                        </span>
                        <span className="mt-0.5 block text-xs text-muted-foreground">
                          {type.hint}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </Decision>

              <Decision
                id="gb-audience"
                label="Audience"
                hint="Who should feel this was made specifically for them?"
                delegated={delegated.has("audience")}
                onToggle={() => toggle("audience")}
              >
                <input
                  aria-labelledby="gb-audience-label"
                  value={values.audience}
                  maxLength={240}
                  onChange={(event) => set("audience", event.target.value)}
                  placeholder="Operations leaders at growing teams"
                  className={INPUT}
                />
              </Decision>

              <Decision
                id="gb-question"
                label="Visitor question"
                hint="What useful answer should the visitor leave with?"
                delegated={delegated.has("visitor_question")}
                onToggle={() => toggle("visitor_question")}
              >
                <input
                  aria-labelledby="gb-question-label"
                  value={values.visitor_question}
                  maxLength={220}
                  onChange={(event) => set("visitor_question", event.target.value)}
                  placeholder="How much could this save my team?"
                  className={INPUT}
                />
              </Decision>

              <Decision
                id="gb-offer"
                label="Offer"
                hint="What should the experience naturally lead toward?"
                delegated={delegated.has("offer")}
                onToggle={() => toggle("offer")}
              >
                <input
                  aria-labelledby="gb-offer-label"
                  value={values.offer}
                  maxLength={280}
                  onChange={(event) => set("offer", event.target.value)}
                  placeholder="A free workflow review"
                  className={INPUT}
                />
              </Decision>

              <Decision
                id="gb-goal"
                label="Business goal"
                hint="What should this experience do for the business?"
                delegated={delegated.has("goal")}
                onToggle={() => toggle("goal")}
              >
                <select
                  aria-labelledby="gb-goal-label"
                  value={values.goal}
                  onChange={(event) => set("goal", event.target.value as CreationBrief["goal"])}
                  className={INPUT}
                >
                  {GOALS.map((goal) => (
                    <option key={goal.value} value={goal.value}>
                      {goal.label}
                    </option>
                  ))}
                </select>
              </Decision>

              <Decision
                id="gb-tone"
                label="Tone"
                hint="Choose a voice, or let Magnitai match the website."
                delegated={delegated.has("tone")}
                onToggle={() => toggle("tone")}
              >
                <select
                  aria-labelledby="gb-tone-label"
                  value={values.tone}
                  onChange={(event) => set("tone", event.target.value as CreationBrief["tone"])}
                  className={INPUT}
                >
                  {TONES.map((tone) => (
                    <option key={tone.value} value={tone.value}>
                      {tone.label}
                    </option>
                  ))}
                </select>
              </Decision>

              <Decision
                id="gb-result"
                label="Visitor result"
                hint="How should the answer be delivered at the end?"
                delegated={delegated.has("result_style")}
                onToggle={() => toggle("result_style")}
              >
                <select
                  aria-labelledby="gb-result-label"
                  value={values.result_style}
                  onChange={(event) =>
                    set("result_style", event.target.value as CreationBrief["result_style"])
                  }
                  className={INPUT}
                >
                  {RESULTS.map((result) => (
                    <option key={result.value} value={result.value}>
                      {result.label}
                    </option>
                  ))}
                </select>
              </Decision>

              <Decision
                id="gb-count"
                label="Length"
                hint="Two questions is a glance. Seven feels like a consultation."
                delegated={delegated.has("question_count")}
                onToggle={() => toggle("question_count")}
              >
                <div
                  role="group"
                  aria-labelledby="gb-count-label"
                  className="flex h-12 items-center gap-4 rounded-xl border border-border-strong bg-card px-3.5"
                >
                  <input
                    aria-label="Number of questions"
                    type="range"
                    min={2}
                    max={7}
                    step={1}
                    value={values.question_count}
                    onChange={(event) => set("question_count", Number(event.target.value))}
                    className="h-1.5 flex-1 accent-[var(--foreground)]"
                  />
                  <output className="tabular w-8 text-right text-sm font-medium text-foreground">
                    {values.question_count}
                  </output>
                </div>
              </Decision>
            </div>
          </section>

          <section className="border-t border-border pt-8">
            <label
              htmlFor="gb-notes"
              className="text-xl font-semibold tracking-[-0.025em] text-foreground"
            >
              Add anything the controls did not cover
            </label>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              Include must-haves, calculations, inputs, language, constraints or anything Magnitai
              should avoid.
            </p>
            <textarea
              id="gb-notes"
              rows={4}
              maxLength={800}
              value={instructions}
              onChange={(event) => setInstructions(event.target.value)}
              placeholder="For example: Keep it under five questions. Do not mention pricing. End with a useful result before asking for contact details."
              className="mt-4 w-full resize-y rounded-[1.4rem] border border-border-strong bg-card px-5 py-4 text-sm leading-6 text-foreground shadow-card outline-none transition-[border-color,box-shadow] placeholder:text-n-400 focus:border-foreground/45 focus:shadow-float"
            />
          </section>
        </div>

        <aside aria-label="Lead magnet brief" className="lg:sticky lg:top-28">
          <div className="rounded-[1.7rem] bg-inverse p-5 text-inverse-foreground shadow-float">
            <div className="flex items-center gap-2 text-xs text-inverse-muted">
              <Sparkles className="size-4 text-brand-on-inverse" aria-hidden="true" />
              Your brief
            </div>
            <h2 className="mt-5 font-heading text-2xl font-medium leading-[1.05] tracking-[-0.04em]">
              Your choices stay fixed. Magnitai completes the rest.
            </h2>

            <div className="mt-6 grid grid-cols-2 border-y border-inverse-border py-4">
              <div>
                <span className="block font-mono text-2xl text-inverse-foreground">
                  {yourChoices.length}
                </span>
                <span className="mt-1 block text-[11px] text-inverse-muted">Directed by you</span>
              </div>
              <div className="border-l border-inverse-border pl-4">
                <span className="block font-mono text-2xl text-inverse-foreground">
                  {delegated.size}
                </span>
                <span className="mt-1 block text-[11px] text-inverse-muted">
                  Recommended by Magnitai
                </span>
              </div>
            </div>

            <div className="mt-5">
              {yourChoices.length ? (
                <div className="grid gap-2">
                  {yourChoices.map((choice) => (
                    <div
                      key={choice}
                      className="flex items-center gap-2 text-xs text-inverse-muted"
                    >
                      <span className="flex size-5 items-center justify-center rounded-full bg-inverse-raised text-brand-on-inverse">
                        <Check className="size-3" aria-hidden="true" />
                      </span>
                      {choice}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs leading-5 text-inverse-muted">
                  Start with a blank brief and Magnitai will propose everything from {domain}.
                </p>
              )}
            </div>

            {error ? (
              <p
                role="alert"
                className="mt-5 rounded-xl border border-destructive/35 px-3 py-2.5 text-xs leading-5 text-inverse-foreground"
              >
                {error}
              </p>
            ) : null}

            <button
              type="button"
              onClick={submit}
              disabled={pending}
              className="btn mt-6 h-12 w-full bg-brand px-5 text-sm font-semibold text-foreground hover:brightness-95 disabled:cursor-wait disabled:opacity-60"
            >
              {pending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
              Create my lead magnets
              <ArrowRight className="size-4" aria-hidden="true" />
            </button>

            <p className="mt-3 text-center text-[10px] leading-4 text-inverse-subtle">
              Your brief stays intact if you need to sign in.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
