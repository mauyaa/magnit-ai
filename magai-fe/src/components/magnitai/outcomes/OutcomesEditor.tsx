import { AlertCircle, Check, Loader2, Plus, RotateCcw, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  useOutcomes,
  useResetOutcomes,
  useSaveOutcomes,
  type AdviceBlock,
  type NextStep,
  type OutcomeConfig,
  type ScoreBand,
  type WidgetData,
} from "@/lib/api";
import { PlanGate } from "@/lib/plan";
import { SaveConfirmation } from "./SaveConfirmation";
import { ResultPreview } from "./ResultPreview";

const FIELD =
  "h-10 w-full rounded-lg border border-border bg-card px-3 text-sm text-foreground outline-none placeholder:text-n-400 focus:border-foreground/40";
const AREA =
  "w-full resize-y rounded-lg border border-border bg-card px-3 py-2 text-sm leading-6 text-foreground outline-none placeholder:text-n-400 focus:border-foreground/40";

type SectionId = "bands" | "advice" | "capture" | "cta" | "next";

const SECTIONS: Array<{ id: SectionId; label: string }> = [
  { id: "bands", label: "Score bands" },
  { id: "advice", label: "Advice" },
  { id: "capture", label: "Email capture" },
  { id: "cta", label: "Call to action" },
  { id: "next", label: "Next steps" },
];

const IMPORTANCE: Array<ScoreBand["importance"]> = ["high", "medium", "low"];

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-foreground">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs leading-5 text-muted-foreground">{hint}</span>}
    </label>
  );
}

/**
 * Keep the bands a gapless, non-overlapping partition of 0-100.
 *
 * The server rejects anything else, and rightly so — a gap means a visitor can
 * score into nothing and see a result screen with no result. Rather than let
 * someone build an invalid layout and then explain the rejection, editing one
 * boundary moves its neighbour with it, so the set is always valid by
 * construction and there is no error state to recover from.
 */
function withBoundary(bands: ScoreBand[], index: number, minimum: number): ScoreBand[] {
  const ordered = [...bands].sort((a, b) => a.minimum_score - b.minimum_score);
  if (index <= 0 || index >= ordered.length) return bands;

  const lowerBound = ordered[index - 1].minimum_score + 1;
  const upperBound = ordered[index].maximum_score;
  const value = Math.max(lowerBound, Math.min(upperBound, minimum));

  const next = ordered.map((band, position) => {
    if (position === index) return { ...band, minimum_score: value };
    if (position === index - 1) return { ...band, maximum_score: value - 1 };
    return band;
  });

  // Restore the caller's original ordering so rows do not jump under the cursor
  // while a number is being typed.
  return bands.map((band) => next.find((item) => item.key === band.key) ?? band);
}

function splitLastBand(bands: ScoreBand[]): ScoreBand[] {
  const ordered = [...bands].sort((a, b) => a.minimum_score - b.minimum_score);
  const lowest = ordered[0];
  const span = lowest.maximum_score - lowest.minimum_score;
  if (span < 1) return bands;

  const boundary = lowest.minimum_score + Math.floor(span / 2);
  const key = `band_${Date.now().toString(36)}`;
  return [
    ...bands.map((band) =>
      band.key === lowest.key ? { ...band, minimum_score: boundary + 1 } : band,
    ),
    {
      key,
      label: "New band",
      minimum_score: lowest.minimum_score,
      maximum_score: boundary,
      importance: "low",
      description: "",
      accent_color: "#6B7280",
    },
  ];
}

function removeBand(bands: ScoreBand[], key: string): ScoreBand[] {
  if (bands.length <= 1) return bands;
  const remaining = bands.filter((band) => band.key !== key);
  const ordered = [...remaining].sort((a, b) => a.minimum_score - b.minimum_score);
  // Close the hole the removed band left, so the set stays a partition.
  let cursor = 0;
  const closed = ordered.map((band, index) => {
    const maximum = index === ordered.length - 1 ? 100 : band.maximum_score;
    const next = { ...band, minimum_score: cursor, maximum_score: Math.max(cursor, maximum) };
    cursor = next.maximum_score + 1;
    return next;
  });
  return remaining.map((band) => closed.find((item) => item.key === band.key) ?? band);
}

/**
 * A number field whose value is clamped against its neighbours.
 *
 * Holds what was typed locally and only commits on blur or Enter. Committing on
 * every keystroke cannot work here: the boundary is clamped against the band
 * below, so clearing the field to type "80" clamps to 1 the instant it is empty
 * and the next keystroke lands against a value the typist never chose. The
 * field ends up fighting whoever is using it.
 */
function BoundaryInput({
  value,
  disabled,
  onCommit,
  className,
}: {
  value: number;
  disabled?: boolean;
  onCommit: (next: number) => void;
  className?: string;
}) {
  const [draft, setDraft] = useState(String(value));

  // Follow the committed value when it changes from elsewhere — adding a band,
  // or the neighbour above pushing this boundary down.
  useEffect(() => setDraft(String(value)), [value]);

  const commit = () => {
    const parsed = Number(draft);
    if (draft.trim() === "" || Number.isNaN(parsed)) {
      setDraft(String(value));
      return;
    }
    onCommit(Math.round(parsed));
  };

  return (
    <input
      type="number"
      min={0}
      max={100}
      value={draft}
      disabled={disabled}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          commit();
        }
      }}
      className={className}
    />
  );
}

export function OutcomesEditor({ widget }: { widget: WidgetData }) {
  return (
    <PlanGate feature="outcome_editor">
      <OutcomesEditorBody widget={widget} />
    </PlanGate>
  );
}

function OutcomesEditorBody({ widget }: { widget: WidgetData }) {
  const { data, isLoading } = useOutcomes(widget.id);
  const save = useSaveOutcomes(widget.id);
  const reset = useResetOutcomes(widget.id);

  const [draft, setDraft] = useState<OutcomeConfig | null>(null);
  const [section, setSection] = useState<SectionId>("bands");
  const [previewScore, setPreviewScore] = useState(86);

  // Adopt the server's version whenever it changes identity — on first load and
  // after a reset — without clobbering in-progress edits on an unrelated refetch.
  useEffect(() => {
    if (data?.config) setDraft(data.config);
  }, [data?.config]);

  const dirty = useMemo(
    () => Boolean(draft && data?.config && JSON.stringify(draft) !== JSON.stringify(data.config)),
    [draft, data?.config],
  );

  if (isLoading || !draft) {
    return (
      <div className="flex justify-center py-24">
        <Loader2 className="size-5 animate-spin text-muted-foreground" aria-label="Loading" />
      </div>
    );
  }

  const update = (patch: Partial<OutcomeConfig>) => setDraft({ ...draft, ...patch });
  const updateBand = (key: string, patch: Partial<ScoreBand>) =>
    update({
      bands: draft.bands.map((band) => (band.key === key ? { ...band, ...patch } : band)),
    });

  const orderedBands = [...draft.bands].sort((a, b) => b.minimum_score - a.minimum_score);

  return (
    <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(24rem,0.95fr)]">
      <div className="surface overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
          <div className="min-w-0">
            <h2 className="text-base font-medium text-foreground">Results and outcomes</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {data?.customised
                ? "You have edited this result screen."
                : "Written by Magnitai from your site. Edit anything."}
            </p>
          </div>
          {data?.customised && (
            <button
              type="button"
              onClick={() => reset.mutate()}
              disabled={reset.isPending}
              className="btn btn-ghost h-8 shrink-0 px-2.5 text-xs"
            >
              <RotateCcw className="size-3.5" aria-hidden="true" />
              Reset
            </button>
          )}
        </div>

        <nav
          className="flex gap-1 overflow-x-auto border-b border-border px-2"
          aria-label="Outcome sections"
        >
          {SECTIONS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setSection(item.id)}
              aria-current={section === item.id ? "page" : undefined}
              className={`-mb-px shrink-0 border-b-2 px-3 py-2.5 text-sm transition-colors ${
                section === item.id
                  ? "border-foreground font-medium text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="space-y-5 p-4">
          {section === "bands" && (
            <>
              <p className="text-sm leading-6 text-muted-foreground">
                Every score from 0 to 100 falls in exactly one band. Moving a boundary moves the
                band below it, so there is never a score with nowhere to land.
              </p>

              {orderedBands.map((band, position) => {
                const indexInAscending = draft.bands.length - 1 - position;
                return (
                  <section
                    key={band.key}
                    className="rounded-xl border border-border p-3.5"
                    style={{ borderLeftWidth: 3, borderLeftColor: band.accent_color }}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="tabular text-xs font-medium text-muted-foreground">
                        {band.minimum_score} – {band.maximum_score}
                      </span>
                      {draft.bands.length > 1 && (
                        <button
                          type="button"
                          onClick={() => update({ bands: removeBand(draft.bands, band.key) })}
                          className="btn btn-ghost size-7 px-0"
                          aria-label={`Remove ${band.label}`}
                        >
                          <Trash2 className="size-3.5" aria-hidden="true" />
                        </button>
                      )}
                    </div>

                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      <Field label="Band label">
                        <input
                          value={band.label}
                          maxLength={80}
                          onChange={(event) => updateBand(band.key, { label: event.target.value })}
                          className={FIELD}
                        />
                      </Field>

                      <Field label="Starts at">
                        <BoundaryInput
                          value={band.minimum_score}
                          // The lowest band always starts at 0; there is no
                          // neighbour beneath it to give the range to.
                          disabled={indexInAscending === 0}
                          onCommit={(next) =>
                            update({
                              bands: withBoundary(draft.bands, indexInAscending, next),
                            })
                          }
                          className={`${FIELD} tabular disabled:opacity-55`}
                        />
                      </Field>
                    </div>

                    <div className="mt-3">
                      <Field
                        label="What this means"
                        hint="Shown to the visitor under their result."
                      >
                        <textarea
                          rows={2}
                          maxLength={600}
                          value={band.description}
                          onChange={(event) =>
                            updateBand(band.key, { description: event.target.value })
                          }
                          className={AREA}
                        />
                      </Field>
                    </div>

                    <div className="mt-3 flex flex-wrap items-end gap-4">
                      <div>
                        <span className="mb-1.5 block text-sm font-medium text-foreground">
                          Importance
                        </span>
                        <div className="flex gap-1.5">
                          {IMPORTANCE.map((level) => (
                            <button
                              key={level}
                              type="button"
                              onClick={() => updateBand(band.key, { importance: level })}
                              aria-pressed={band.importance === level}
                              className={`h-8 rounded-lg border px-2.5 text-xs capitalize transition-colors ${
                                band.importance === level
                                  ? "border-foreground bg-foreground text-background"
                                  : "border-border text-muted-foreground hover:text-foreground"
                              }`}
                            >
                              {level}
                            </button>
                          ))}
                        </div>
                      </div>

                      <label className="flex items-center gap-2 text-sm font-medium text-foreground">
                        Colour
                        <input
                          type="color"
                          value={band.accent_color}
                          aria-label={`${band.label} colour`}
                          onChange={(event) =>
                            updateBand(band.key, {
                              accent_color: event.target.value.toUpperCase(),
                            })
                          }
                          className="size-8 cursor-pointer rounded-lg border border-border bg-transparent p-0.5"
                        />
                      </label>

                      <button
                        type="button"
                        onClick={() => setPreviewScore(band.minimum_score)}
                        className="btn btn-ghost ml-auto h-8 px-2.5 text-xs"
                      >
                        Preview this band
                      </button>
                    </div>
                  </section>
                );
              })}

              {draft.bands.length < 6 && (
                <button
                  type="button"
                  onClick={() => update({ bands: splitLastBand(draft.bands) })}
                  className="btn btn-secondary h-9 w-full text-sm"
                >
                  <Plus className="size-4" aria-hidden="true" />
                  Add a band
                </button>
              )}
            </>
          )}

          {section === "advice" && (
            <>
              <p className="text-sm leading-6 text-muted-foreground">
                Shown under the heading “Recommended for you”. Leave a line unassigned to show it to
                everyone, whatever they scored.
              </p>

              {draft.advice.map((block, index) => (
                <div key={index} className="rounded-xl border border-border p-3.5">
                  <textarea
                    rows={2}
                    maxLength={300}
                    value={block.text}
                    aria-label={`Advice ${index + 1}`}
                    onChange={(event) =>
                      update({
                        advice: draft.advice.map((item, position) =>
                          position === index ? { ...item, text: event.target.value } : item,
                        ),
                      })
                    }
                    className={AREA}
                  />
                  <div className="mt-2.5 flex items-center gap-2">
                    <select
                      value={block.band_key ?? ""}
                      aria-label={`Show advice ${index + 1} to`}
                      onChange={(event) =>
                        update({
                          advice: draft.advice.map((item, position) =>
                            position === index
                              ? { ...item, band_key: event.target.value || null }
                              : item,
                          ),
                        })
                      }
                      className="h-8 rounded-lg border border-border bg-card px-2 text-xs text-foreground outline-none focus:border-foreground/40"
                    >
                      <option value="">Everyone</option>
                      {draft.bands.map((band) => (
                        <option key={band.key} value={band.key}>
                          {band.label}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => update({ advice: draft.advice.filter((_, p) => p !== index) })}
                      className="btn btn-ghost ml-auto size-7 px-0"
                      aria-label={`Remove advice ${index + 1}`}
                    >
                      <Trash2 className="size-3.5" aria-hidden="true" />
                    </button>
                  </div>
                </div>
              ))}

              {draft.advice.length < 12 && (
                <button
                  type="button"
                  onClick={() =>
                    update({
                      advice: [...draft.advice, { text: "", band_key: null } as AdviceBlock],
                    })
                  }
                  className="btn btn-secondary h-9 w-full text-sm"
                >
                  <Plus className="size-4" aria-hidden="true" />
                  Add advice
                </button>
              )}
            </>
          )}

          {section === "capture" && (
            <>
              <div className="flex items-start justify-between gap-6">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-foreground">Ask for an email</p>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    Always after the result, never before it — the visitor sees what they came for
                    first.
                  </p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={draft.email_capture.enabled}
                  aria-label="Ask for an email"
                  onClick={() =>
                    update({
                      email_capture: {
                        ...draft.email_capture,
                        enabled: !draft.email_capture.enabled,
                      },
                    })
                  }
                  className={`relative mt-0.5 h-6 w-11 shrink-0 rounded-full transition-colors ${
                    draft.email_capture.enabled ? "bg-foreground" : "bg-n-300"
                  }`}
                >
                  <span
                    className={`absolute top-0.5 size-5 rounded-full bg-card shadow-raised transition-transform ${
                      draft.email_capture.enabled ? "translate-x-[1.375rem]" : "translate-x-0.5"
                    }`}
                  />
                </button>
              </div>

              {draft.email_capture.enabled && (
                <div className="grid gap-3 border-t border-border pt-4 sm:grid-cols-2">
                  {(
                    [
                      ["heading", "Heading", 120],
                      ["button_label", "Button label", 60],
                      ["placeholder", "Field placeholder", 80],
                    ] as const
                  ).map(([key, label, max]) => (
                    <Field key={key} label={label}>
                      <input
                        value={draft.email_capture[key]}
                        maxLength={max}
                        onChange={(event) =>
                          update({
                            email_capture: {
                              ...draft.email_capture,
                              [key]: event.target.value,
                            },
                          })
                        }
                        className={FIELD}
                      />
                    </Field>
                  ))}

                  <div className="sm:col-span-2">
                    <Field label="Supporting line">
                      <textarea
                        rows={2}
                        maxLength={240}
                        value={draft.email_capture.subheading}
                        onChange={(event) =>
                          update({
                            email_capture: {
                              ...draft.email_capture,
                              subheading: event.target.value,
                            },
                          })
                        }
                        className={AREA}
                      />
                    </Field>
                  </div>

                  <div className="sm:col-span-2">
                    <Field
                      label="Consent line"
                      hint="Shown beneath the form. Required in some jurisdictions before you may contact someone."
                    >
                      <input
                        value={draft.email_capture.consent_text}
                        maxLength={300}
                        placeholder="By submitting, you agree to be contacted about this result."
                        onChange={(event) =>
                          update({
                            email_capture: {
                              ...draft.email_capture,
                              consent_text: event.target.value,
                            },
                          })
                        }
                        className={FIELD}
                      />
                    </Field>
                  </div>
                </div>
              )}
            </>
          )}

          {section === "cta" && (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Button label">
                <input
                  value={draft.cta.label}
                  maxLength={80}
                  onChange={(event) => update({ cta: { ...draft.cta, label: event.target.value } })}
                  className={FIELD}
                />
              </Field>
              <Field label="Supporting note" hint="Optional. Sits beside the button.">
                <input
                  value={draft.cta.note}
                  maxLength={160}
                  placeholder="Takes 15 minutes"
                  onChange={(event) => update({ cta: { ...draft.cta, note: event.target.value } })}
                  className={FIELD}
                />
              </Field>
              <div className="sm:col-span-2">
                <Field
                  label="Where it sends people"
                  hint="A full address, including https://. This is the one place the tool hands a visitor over to you."
                >
                  <input
                    type="url"
                    value={draft.cta.url}
                    maxLength={2048}
                    placeholder="https://yourcompany.com/book-a-call"
                    onChange={(event) => update({ cta: { ...draft.cta, url: event.target.value } })}
                    className={FIELD}
                  />
                </Field>
              </div>
            </div>
          )}

          {section === "next" && (
            <>
              <p className="text-sm leading-6 text-muted-foreground">
                Up to three cards beneath the result, for people who are not ready for the main
                action yet.
              </p>

              {draft.next_steps.map((step, index) => (
                <div key={index} className="rounded-xl border border-border p-3.5">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="Title">
                      <input
                        value={step.title}
                        maxLength={80}
                        onChange={(event) =>
                          update({
                            next_steps: draft.next_steps.map((item, position) =>
                              position === index ? { ...item, title: event.target.value } : item,
                            ),
                          })
                        }
                        className={FIELD}
                      />
                    </Field>
                    <Field label="Link label">
                      <input
                        value={step.link_label}
                        maxLength={60}
                        placeholder="Read the guide"
                        onChange={(event) =>
                          update({
                            next_steps: draft.next_steps.map((item, position) =>
                              position === index
                                ? { ...item, link_label: event.target.value }
                                : item,
                            ),
                          })
                        }
                        className={FIELD}
                      />
                    </Field>
                    <div className="sm:col-span-2">
                      <Field label="Description">
                        <input
                          value={step.description}
                          maxLength={240}
                          onChange={(event) =>
                            update({
                              next_steps: draft.next_steps.map((item, position) =>
                                position === index
                                  ? { ...item, description: event.target.value }
                                  : item,
                              ),
                            })
                          }
                          className={FIELD}
                        />
                      </Field>
                    </div>
                    <div className="sm:col-span-2">
                      <Field label="Link address">
                        <input
                          type="url"
                          value={step.link_url}
                          maxLength={2048}
                          placeholder="https://yourcompany.com/guide"
                          onChange={(event) =>
                            update({
                              next_steps: draft.next_steps.map((item, position) =>
                                position === index
                                  ? { ...item, link_url: event.target.value }
                                  : item,
                              ),
                            })
                          }
                          className={FIELD}
                        />
                      </Field>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      update({ next_steps: draft.next_steps.filter((_, p) => p !== index) })
                    }
                    className="btn btn-ghost mt-2.5 h-8 px-2.5 text-xs"
                  >
                    <Trash2 className="size-3.5" aria-hidden="true" />
                    Remove
                  </button>
                </div>
              ))}

              {draft.next_steps.length < 3 && (
                <button
                  type="button"
                  onClick={() =>
                    update({
                      next_steps: [
                        ...draft.next_steps,
                        {
                          title: "",
                          description: "",
                          link_label: "",
                          link_url: "",
                        } as NextStep,
                      ],
                    })
                  }
                  className="btn btn-secondary h-9 w-full text-sm"
                >
                  <Plus className="size-4" aria-hidden="true" />
                  Add a next step
                </button>
              )}
            </>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3 border-t border-border px-4 py-3">
          <button
            type="button"
            onClick={() => save.mutate(draft)}
            disabled={!dirty || save.isPending}
            className="btn btn-primary h-9 text-sm"
          >
            {save.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            ) : (
              <Check className="size-4" aria-hidden="true" />
            )}
            Save changes
          </button>

          {dirty && !save.isPending && (
            <span className="text-xs text-muted-foreground">Unsaved changes</span>
          )}
          {!dirty && save.isSuccess && <SaveConfirmation widget={widget} />}
          {save.isError && (
            <p role="alert" className="flex items-center gap-1.5 text-xs text-destructive">
              <AlertCircle className="size-3.5 shrink-0" aria-hidden="true" />
              {(save.error as Error).message}
            </p>
          )}
        </div>
      </div>

      <aside className="xl:sticky xl:top-24">
        <div className="flex items-center justify-between gap-3 pb-3">
          <h2 className="text-base font-medium text-foreground">Result screen preview</h2>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            Score
            <input
              type="range"
              min={0}
              max={100}
              value={previewScore}
              aria-label="Preview score"
              onChange={(event) => setPreviewScore(Number(event.target.value))}
              className="h-1 w-24 accent-[var(--foreground)]"
            />
            <output className="tabular w-7 text-right font-medium text-foreground">
              {previewScore}
            </output>
          </label>
        </div>
        <ResultPreview config={draft} widget={widget} score={previewScore} />
        <p className="mt-2.5 text-xs leading-5 text-muted-foreground">
          Saved changes reach your published tool within a minute. No rebuild, no re-paste.
        </p>
      </aside>
    </div>
  );
}
