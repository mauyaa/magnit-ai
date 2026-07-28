import { AlertCircle, Check, ChevronDown, ChevronUp, Loader2, Plus, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  useDecision,
  useSaveDecision,
  type DecisionQuestion,
  type DecisionSpec,
  type WidgetData,
} from "@/lib/api";
import { PlanGate } from "@/lib/plan";

const FIELD =
  "h-10 w-full rounded-lg border border-border bg-card px-3 text-sm text-foreground outline-none placeholder:text-n-400 focus:border-foreground/40";

const INPUT_TYPES: Array<{ value: DecisionQuestion["input_type"]; label: string; hint: string }> = [
  { value: "single_choice", label: "Choice", hint: "Pick one of a list" },
  { value: "number", label: "Number", hint: "Type or slide a value" },
  { value: "boolean", label: "Yes / no", hint: "A single toggle" },
];

/**
 * A stable, schema-legal id for a new question.
 *
 * The server requires `^[a-z][a-z0-9_]*$` and rejects duplicates, and the
 * calculation refers to questions by this id — so it is generated once and never
 * derived from the label, which the owner will rename.
 */
function newQuestionId(existing: string[]): string {
  let index = existing.length + 1;
  let candidate = `question_${index}`;
  while (existing.includes(candidate)) {
    index += 1;
    candidate = `question_${index}`;
  }
  return candidate;
}

function blankQuestion(existing: string[]): DecisionQuestion {
  return {
    id: newQuestionId(existing),
    label: "",
    help_text: "",
    input_type: "single_choice",
    required: true,
    options: ["", ""],
    minimum: null,
    maximum: null,
    step: null,
    default: null,
    weight: 1,
    option_scores: [],
    true_score: 100,
    evidence_ref: null,
  };
}

export function QuestionEditor({ widget }: { widget: WidgetData }) {
  return (
    <PlanGate feature="question_editor">
      <QuestionEditorBody widget={widget} />
    </PlanGate>
  );
}

function QuestionEditorBody({ widget }: { widget: WidgetData }) {
  const { data, isLoading } = useDecision(widget.id);
  const save = useSaveDecision(widget.id);
  const [draft, setDraft] = useState<DecisionSpec | null>(null);
  const [openIndex, setOpenIndex] = useState(0);

  useEffect(() => {
    if (data?.decision) setDraft(data.decision);
  }, [data?.decision]);

  const dirty = useMemo(
    () =>
      Boolean(draft && data?.decision && JSON.stringify(draft) !== JSON.stringify(data.decision)),
    [draft, data?.decision],
  );

  if (isLoading) {
    return (
      <div className="flex justify-center py-24">
        <Loader2 className="size-5 animate-spin text-muted-foreground" aria-label="Loading" />
      </div>
    );
  }

  if (!draft) {
    return (
      <div className="surface px-6 py-14 text-center">
        <p className="text-sm font-medium text-foreground">No question flow yet</p>
        <p className="mx-auto mt-1.5 max-w-sm text-sm leading-6 text-muted-foreground">
          Magnitai writes the questions when it builds the tool. Once it has, you can reword,
          reorder and rescore them here.
        </p>
      </div>
    );
  }

  const update = (patch: Partial<DecisionSpec>) => setDraft({ ...draft, ...patch });
  const updateQuestion = (index: number, patch: Partial<DecisionQuestion>) =>
    update({
      questions: draft.questions.map((question, position) =>
        position === index ? { ...question, ...patch } : question,
      ),
    });

  const move = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= draft.questions.length) return;
    const questions = [...draft.questions];
    [questions[index], questions[target]] = [questions[target], questions[index]];
    update({ questions });
    setOpenIndex(target);
  };

  const remove = (index: number) => {
    // The schema requires at least two questions, and the calculation may refer
    // to this one — so removing it drops any term that pointed at it rather than
    // leaving a reference the server will reject.
    if (draft.questions.length <= 2) return;
    const removed = draft.questions[index];
    update({
      questions: draft.questions.filter((_, position) => position !== index),
      calculation: {
        ...draft.calculation,
        terms: draft.calculation.terms.filter((term) => term.question_id !== removed.id),
      },
    });
    setOpenIndex(0);
  };

  return (
    <div className="space-y-4">
      <div className="surface p-4">
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-foreground">
            The question this tool answers
          </span>
          <input
            value={draft.buyer_question}
            maxLength={220}
            onChange={(event) => update({ buyer_question: event.target.value })}
            className={FIELD}
          />
          <span className="mt-1 block text-xs leading-5 text-muted-foreground">
            The headline a visitor sees before they start.
          </span>
        </label>
      </div>

      <div className="surface overflow-hidden">
        <div className="flex items-baseline justify-between gap-3 border-b border-border px-4 py-3">
          <h2 className="text-base font-medium text-foreground">Question flow</h2>
          <span className="text-xs text-muted-foreground">
            {draft.questions.length} of 7 questions
          </span>
        </div>

        <ol className="divide-y divide-border">
          {draft.questions.map((question, index) => {
            const open = index === openIndex;
            return (
              <li key={question.id}>
                <div className="flex items-center gap-3 px-4 py-3">
                  <span className="tabular grid size-6 shrink-0 place-items-center rounded-md bg-secondary text-xs font-medium text-foreground">
                    {index + 1}
                  </span>
                  <button
                    type="button"
                    onClick={() => setOpenIndex(open ? -1 : index)}
                    aria-expanded={open}
                    className="min-w-0 flex-1 text-left"
                  >
                    <span className="block truncate text-sm font-medium text-foreground">
                      {question.label || "Untitled question"}
                    </span>
                    <span className="mt-0.5 block text-xs capitalize text-muted-foreground">
                      {question.input_type.replace("_", " ")} · weight {question.weight}
                    </span>
                  </button>

                  <div className="flex shrink-0 items-center gap-0.5">
                    <button
                      type="button"
                      onClick={() => move(index, -1)}
                      disabled={index === 0}
                      className="btn btn-ghost size-7 px-0 disabled:opacity-30"
                      aria-label={`Move question ${index + 1} up`}
                    >
                      <ChevronUp className="size-4" aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      onClick={() => move(index, 1)}
                      disabled={index === draft.questions.length - 1}
                      className="btn btn-ghost size-7 px-0 disabled:opacity-30"
                      aria-label={`Move question ${index + 1} down`}
                    >
                      <ChevronDown className="size-4" aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      onClick={() => remove(index)}
                      disabled={draft.questions.length <= 2}
                      className="btn btn-ghost size-7 px-0 disabled:opacity-30"
                      aria-label={`Remove question ${index + 1}`}
                    >
                      <Trash2 className="size-3.5" aria-hidden="true" />
                    </button>
                  </div>
                </div>

                {open && (
                  <div className="space-y-3 border-t border-border bg-n-25 px-4 py-4">
                    <label className="block">
                      <span className="mb-1.5 block text-sm font-medium text-foreground">
                        Question
                      </span>
                      <input
                        value={question.label}
                        maxLength={180}
                        onChange={(event) => updateQuestion(index, { label: event.target.value })}
                        className={FIELD}
                      />
                    </label>

                    <label className="block">
                      <span className="mb-1.5 block text-sm font-medium text-foreground">
                        Helper text
                      </span>
                      <input
                        value={question.help_text}
                        maxLength={240}
                        placeholder="Optional. Sits under the question."
                        onChange={(event) =>
                          updateQuestion(index, { help_text: event.target.value })
                        }
                        className={FIELD}
                      />
                    </label>

                    <div>
                      <span className="mb-1.5 block text-sm font-medium text-foreground">
                        Answer type
                      </span>
                      <div className="grid gap-2 sm:grid-cols-3">
                        {INPUT_TYPES.map((type) => (
                          <button
                            key={type.value}
                            type="button"
                            aria-pressed={question.input_type === type.value}
                            onClick={() =>
                              updateQuestion(index, {
                                input_type: type.value,
                                // Each shape carries different fields, and the
                                // server rejects a question holding another
                                // type's — options on a number question, say.
                                options: type.value === "single_choice" ? ["", ""] : [],
                                option_scores: [],
                                minimum: type.value === "number" ? 0 : null,
                                maximum: type.value === "number" ? 100 : null,
                                default: null,
                              })
                            }
                            className={`rounded-lg border px-3 py-2.5 text-left transition-colors ${
                              question.input_type === type.value
                                ? "border-foreground bg-card"
                                : "border-border hover:border-foreground/30"
                            }`}
                          >
                            <span className="block text-sm font-medium text-foreground">
                              {type.label}
                            </span>
                            <span className="mt-0.5 block text-xs text-muted-foreground">
                              {type.hint}
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>

                    {question.input_type === "single_choice" && (
                      <div>
                        <span className="mb-1.5 block text-sm font-medium text-foreground">
                          Options
                        </span>
                        <div className="space-y-2">
                          {question.options.map((option, optionIndex) => (
                            <div key={optionIndex} className="flex items-center gap-2">
                              <input
                                value={option}
                                aria-label={`Option ${optionIndex + 1}`}
                                onChange={(event) =>
                                  updateQuestion(index, {
                                    options: question.options.map((item, position) =>
                                      position === optionIndex ? event.target.value : item,
                                    ),
                                  })
                                }
                                className={FIELD}
                              />
                              <button
                                type="button"
                                disabled={question.options.length <= 2}
                                onClick={() =>
                                  updateQuestion(index, {
                                    options: question.options.filter(
                                      (_, position) => position !== optionIndex,
                                    ),
                                    option_scores: question.option_scores.filter(
                                      (_, position) => position !== optionIndex,
                                    ),
                                  })
                                }
                                className="btn btn-ghost size-9 shrink-0 px-0 disabled:opacity-30"
                                aria-label={`Remove option ${optionIndex + 1}`}
                              >
                                <Trash2 className="size-3.5" aria-hidden="true" />
                              </button>
                            </div>
                          ))}
                        </div>
                        {question.options.length < 8 && (
                          <button
                            type="button"
                            onClick={() =>
                              updateQuestion(index, { options: [...question.options, ""] })
                            }
                            className="btn btn-ghost mt-2 h-8 px-2.5 text-xs"
                          >
                            <Plus className="size-3.5" aria-hidden="true" />
                            Add option
                          </button>
                        )}
                      </div>
                    )}

                    {question.input_type === "number" && (
                      <div className="grid gap-3 sm:grid-cols-2">
                        <label className="block">
                          <span className="mb-1.5 block text-sm font-medium text-foreground">
                            Lowest value
                          </span>
                          <input
                            type="number"
                            value={question.minimum ?? 0}
                            onChange={(event) =>
                              updateQuestion(index, { minimum: Number(event.target.value) })
                            }
                            className={`${FIELD} tabular`}
                          />
                        </label>
                        <label className="block">
                          <span className="mb-1.5 block text-sm font-medium text-foreground">
                            Highest value
                          </span>
                          <input
                            type="number"
                            value={question.maximum ?? 100}
                            onChange={(event) =>
                              updateQuestion(index, { maximum: Number(event.target.value) })
                            }
                            className={`${FIELD} tabular`}
                          />
                        </label>
                      </div>
                    )}

                    <label className="block max-w-xs">
                      <span className="mb-1.5 block text-sm font-medium text-foreground">
                        How much this counts
                      </span>
                      <div className="flex h-10 items-center gap-3 rounded-lg border border-border bg-card px-3">
                        <input
                          type="range"
                          min={0}
                          max={5}
                          step={0.5}
                          value={question.weight}
                          aria-label="Question weight"
                          onChange={(event) =>
                            updateQuestion(index, { weight: Number(event.target.value) })
                          }
                          className="h-1 flex-1 accent-[var(--foreground)]"
                        />
                        <output className="tabular w-7 text-right text-sm font-medium text-foreground">
                          {question.weight}
                        </output>
                      </div>
                      <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                        Relative to the other questions. Zero removes it from the score entirely.
                      </span>
                    </label>
                  </div>
                )}
              </li>
            );
          })}
        </ol>

        {draft.questions.length < 7 && (
          <div className="border-t border-border p-3">
            <button
              type="button"
              onClick={() => {
                update({
                  questions: [...draft.questions, blankQuestion(draft.questions.map((q) => q.id))],
                });
                setOpenIndex(draft.questions.length);
              }}
              className="btn btn-secondary h-9 w-full text-sm"
            >
              <Plus className="size-4" aria-hidden="true" />
              Add a question
            </button>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3 border-t border-border px-4 py-3">
          <button
            type="button"
            onClick={() => save.mutate(draft)}
            disabled={!dirty || save.isPending || data?.editable === false}
            className="btn btn-primary h-9 text-sm"
          >
            {save.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            ) : (
              <Check className="size-4" aria-hidden="true" />
            )}
            Save questions
          </button>

          {data?.editable === false && (
            <span className="text-xs text-muted-foreground">
              Locked while this tool is building.
            </span>
          )}
          {dirty && !save.isPending && data?.editable !== false && (
            <span className="text-xs text-muted-foreground">Unsaved changes</span>
          )}
          {!dirty && save.isSuccess && (
            <span aria-live="polite" className="text-xs text-success">
              Live on your tool now
            </span>
          )}
          {save.isError && (
            <p role="alert" className="flex items-center gap-1.5 text-xs text-destructive">
              <AlertCircle className="size-3.5 shrink-0" aria-hidden="true" />
              {(save.error as Error).message}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
