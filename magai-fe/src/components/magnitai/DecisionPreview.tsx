import { ArrowRight, Check } from "lucide-react";
import { useMemo, useState } from "react";

import type { ArchitectOutput, DecisionQuestion, DecisionSpec } from "@/lib/api";

type Answer = number | string | boolean;

function answerScore(question: DecisionQuestion, answer: Answer): number {
  if (question.input_type === "boolean") return answer ? question.true_score : 0;
  if (question.input_type === "single_choice") {
    const index = question.options.indexOf(String(answer));
    if (index < 0) return 0;
    return (
      question.option_scores[index] ?? (index / Math.max(1, question.options.length - 1)) * 100
    );
  }
  const value = Number(answer);
  if (!Number.isFinite(value)) return 0;
  if (question.minimum != null && question.maximum != null) {
    return ((value - question.minimum) / (question.maximum - question.minimum)) * 100;
  }
  return value;
}

function calculate(spec: DecisionSpec, answers: Record<string, Answer>): number {
  const { calculation } = spec;
  let value = calculation.constant;

  if (calculation.kind === "weighted_score") {
    let weight = 0;
    value = 0;
    for (const question of spec.questions) {
      if (answers[question.id] === undefined) continue;
      value += answerScore(question, answers[question.id]) * question.weight;
      weight += question.weight;
    }
    value = weight ? value / weight : 0;
  } else {
    for (const term of calculation.terms) {
      const question = spec.questions.find((item) => item.id === term.question_id);
      const answer = answers[term.question_id];
      if (!question || answer === undefined) continue;
      const raw = question.input_type === "number" ? Number(answer) : answerScore(question, answer);
      value += raw * term.multiplier;
    }
  }

  if (calculation.clamp_min != null) value = Math.max(calculation.clamp_min, value);
  if (calculation.clamp_max != null) value = Math.min(calculation.clamp_max, value);
  return value;
}

function formattedValue(spec: DecisionSpec, value: number): string {
  const options: Intl.NumberFormatOptions = {
    maximumFractionDigits: spec.calculation.decimals,
    minimumFractionDigits: spec.calculation.decimals,
  };
  if (spec.calculation.output_format === "currency") {
    options.style = "currency";
    options.currency = spec.calculation.currency;
  }
  const rendered = new Intl.NumberFormat(undefined, options).format(value);
  return spec.calculation.output_format === "percent" ? `${rendered}%` : rendered;
}

function currentResult(spec: DecisionSpec, value: number) {
  return (
    spec.results.find(
      (result) =>
        (result.minimum_score == null || value >= result.minimum_score) &&
        (result.maximum_score == null || value <= result.maximum_score),
    ) ?? spec.results[0]
  );
}

export function DecisionPreview({
  architect,
  compact = false,
}: {
  architect: ArchitectOutput;
  compact?: boolean;
}) {
  const spec = architect.decision;
  const [answers, setAnswers] = useState<Record<string, Answer>>({});
  const answered =
    spec?.questions.filter((question) => answers[question.id] !== undefined).length ?? 0;
  const complete = Boolean(
    spec &&
    spec.questions.every((question) => !question.required || answers[question.id] !== undefined),
  );
  const value = useMemo(() => (spec ? calculate(spec, answers) : 0), [answers, spec]);
  const result = spec ? currentResult(spec, value) : null;
  const activeQuestion = spec?.questions.find((question) => answers[question.id] === undefined);

  if (!spec) {
    return (
      <div className="mx-auto max-w-md py-10 text-center">
        <h3 className="text-2xl font-semibold tracking-[-0.04em]">
          {String(architect.copywriting?.headline || "A focused decision for your visitors")}
        </h3>
        <p className="mx-auto mt-3 max-w-sm text-sm leading-6 opacity-60">
          The finished tool will ask, calculate, and return a useful next step.
        </p>
        <div className="mt-7 grid grid-cols-3 gap-2 text-[10px] font-medium uppercase tracking-[0.12em] opacity-55">
          <span>Answer</span>
          <span>Understand</span>
          <span>Act</span>
        </div>
      </div>
    );
  }

  function answer(question: DecisionQuestion, next: Answer) {
    setAnswers((current) => ({ ...current, [question.id]: next }));
  }

  return (
    <div className="mx-auto max-w-lg py-6 sm:py-8">
      <div className="flex items-center justify-between text-[10px] font-medium uppercase tracking-[0.14em] opacity-55">
        <span>{spec.mechanism}</span>
        <span>
          {answered}/{spec.questions.length}
        </span>
      </div>
      <div className="mt-3 h-1 overflow-hidden rounded-full bg-current/10">
        <span
          className="block h-full rounded-full bg-current transition-[width] duration-300"
          style={{ width: `${Math.max(7, (answered / spec.questions.length) * 100)}%` }}
        />
      </div>

      {!complete && activeQuestion ? (
        <div className={compact ? "mt-6" : "mt-8"}>
          <h3 className="text-balance text-xl font-semibold leading-tight tracking-[-0.035em] sm:text-2xl">
            {activeQuestion.label}
          </h3>
          {activeQuestion.help_text && (
            <p className="mt-2 text-xs leading-5 opacity-55">{activeQuestion.help_text}</p>
          )}

          {activeQuestion.input_type === "single_choice" && (
            <div className="mt-5 grid gap-2">
              {activeQuestion.options.map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => answer(activeQuestion, option)}
                  className="flex min-h-11 items-center justify-between rounded-xl border border-current/15 px-4 text-left text-xs font-medium transition hover:bg-current/5"
                >
                  {option}
                  <ArrowRight className="size-3.5 opacity-45" />
                </button>
              ))}
            </div>
          )}

          {activeQuestion.input_type === "boolean" && (
            <div className="mt-5 grid grid-cols-2 gap-2">
              {[
                ["Yes", true],
                ["Not yet", false],
              ].map(([label, option]) => (
                <button
                  key={String(label)}
                  type="button"
                  onClick={() => answer(activeQuestion, Boolean(option))}
                  className="min-h-11 rounded-xl border border-current/15 text-xs font-medium transition hover:bg-current/5"
                >
                  {String(label)}
                </button>
              ))}
            </div>
          )}

          {activeQuestion.input_type === "number" && (
            <form
              className="mt-5 flex gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                const data = new FormData(event.currentTarget);
                answer(activeQuestion, Number(data.get("answer")));
              }}
            >
              <input
                name="answer"
                type="number"
                required
                // The question is rendered above as display text, which sighted
                // users read as a label and assistive technology does not
                // associate with anything. axe rates an unlabelled input
                // critical, and this is the only free-entry field in every
                // generated tool — a screen-reader user reaching it heard
                // "edit, blank".
                aria-label={activeQuestion.label}
                min={activeQuestion.minimum ?? undefined}
                max={activeQuestion.maximum ?? undefined}
                step={activeQuestion.step ?? "any"}
                defaultValue={
                  typeof activeQuestion.default === "number" ? activeQuestion.default : undefined
                }
                className="min-h-11 min-w-0 flex-1 rounded-xl border border-current/15 bg-transparent px-4 text-sm outline-none focus:ring-2 focus:ring-current/20"
              />
              <button
                type="submit"
                className="min-h-11 rounded-xl bg-current px-4 text-xs font-semibold text-white mix-blend-multiply"
              >
                Next
              </button>
            </form>
          )}
        </div>
      ) : result ? (
        <div className="mt-7">
          <div className="flex size-8 items-center justify-center rounded-full border border-current/15">
            <Check className="size-4" />
          </div>
          <span className="mt-5 block text-[10px] font-medium uppercase tracking-[0.14em] opacity-55">
            {spec.calculation.output_label}
          </span>
          <strong className="mt-1 block text-3xl tracking-[-0.055em]">
            {formattedValue(spec, value)}
          </strong>
          <h3 className="mt-5 text-xl font-semibold tracking-[-0.035em]">{result.title}</h3>
          <p className="mt-2 text-xs leading-5 opacity-65">{result.summary}</p>
          {result.recommendation ? (
            <div className="mt-4 rounded-xl border border-current/15 p-3.5">
              <span className="block text-[9px] font-medium uppercase tracking-[0.14em] opacity-50">
                Recommended next step
              </span>
              <p className="mt-1.5 text-xs leading-5 opacity-75">{result.recommendation}</p>
            </div>
          ) : null}
          <button
            type="button"
            onClick={() => setAnswers({})}
            className="mt-5 text-xs font-semibold underline underline-offset-4"
          >
            Try again
          </button>
        </div>
      ) : null}
    </div>
  );
}
