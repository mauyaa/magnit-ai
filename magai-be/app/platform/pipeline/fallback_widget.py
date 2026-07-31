"""Deterministic build artifacts for provider-degraded widget builds.

The architect output already contains the customer's approved questions,
scoring, results, copy, and brand. Losing a styling or code-generation provider
must reduce novelty, not make that complete product specification unpublishable.
"""

from __future__ import annotations

from app.platform.pipeline.schemas import ArchitectOutput, DesignTokens, ProjectFile, WidgetCode


def fallback_design_tokens(architect: ArchitectOutput) -> DesignTokens:
    """Map the observed brand directly into the scaffold's token contract."""
    brand = architect.brand
    return DesignTokens(
        css_variables={
            "--color-primary": brand.primary_color,
            "--color-secondary": brand.secondary_color,
            "--color-background": brand.background_color,
            "--color-accent": brand.accent_color,
            "--color-surface": "#ffffff",
            "--color-muted": brand.secondary_color,
            "--font-heading": brand.font_headings,
            "--font-body": brand.font_body,
        },
        component_theme={
            "button_bg": "var(--color-primary)",
            "button_text": "var(--color-background)",
            "input_border": "var(--color-secondary)",
            "card_bg": "var(--color-surface)",
            "card_shadow": "0 18px 60px rgba(15, 23, 42, 0.10)",
            "border_radius": "18px",
            "spacing": "20px",
        },
    )


def fallback_widget_code(design_tokens: DesignTokens) -> WidgetCode:
    """Return a complete, accessible decision flow backed by the runtime SDK."""
    return WidgetCode(
        files=[ProjectFile(path="src/App.jsx", content=_FALLBACK_APP_JSX)],
        design_tokens=design_tokens,
    )


_FALLBACK_APP_JSX = r"""import React, { useMemo, useRef, useState } from 'react';
import {
  calculateDecision,
  isValidEmail,
  submitLead,
  trackCta,
  trackComplete,
  trackProgress,
  trackResult,
  trackStart,
  useLiveConfig,
} from './lib/magnitai.js';

/*
 * Nothing here is read from the build-time config.
 *
 * This app is the one that ships when a generation provider is unavailable, and
 * it used to bind SPEC and OUTCOMES at module scope — freezing the questions and
 * the result copy at whatever they were the day it was built. An owner could
 * then rewrite a question in the editor, be told it was live, and watch the
 * deployed tool keep asking the old one while the score was computed from the
 * new one. useLiveConfig() is the single source both halves now read.
 */

function formatValue(spec, value) {
  if (!spec?.calculation || typeof value !== 'number') return null;
  const config = spec.calculation;
  if (config.output_format === 'currency') {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: config.currency || 'USD',
      maximumFractionDigits: config.decimals ?? 0,
    }).format(value);
  }
  if (config.output_format === 'percent') return `${value.toFixed(config.decimals ?? 0)}%`;
  if (config.output_format === 'score') return `${Math.round(value)} / 100`;
  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits: config.decimals ?? 0,
  }).format(value);
}

function QuestionInput({ question, value, onChange }) {
  if (question.input_type === 'number') {
    return (
      <input
        id={question.id}
        type="number"
        min={question.minimum ?? undefined}
        max={question.maximum ?? undefined}
        step={question.step ?? 1}
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value)}
        className="mt-4 min-h-12 w-full rounded-xl border border-black/20 bg-white px-4 text-base text-[var(--color-secondary)] outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary)] focus:ring-offset-2"
      />
    );
  }

  const options =
    question.input_type === 'boolean'
      ? [
          { label: 'Yes', value: true },
          { label: 'Not yet', value: false },
        ]
      : (question.options || []).map((option) => ({ label: option, value: option }));

  return (
    <div className="mt-4 grid gap-3 sm:grid-cols-2">
      {options.map((option) => {
        const selected = value === option.value;
        return (
          <button
            key={String(option.value)}
            type="button"
            aria-pressed={selected}
            onClick={() => onChange(option.value)}
            className={`min-h-12 rounded-xl border px-4 py-3 text-left text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:ring-offset-2 ${
              selected
                ? 'border-[var(--color-primary)] bg-[var(--color-primary)] text-white'
                : 'border-black/15 bg-white text-[var(--color-secondary)]'
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export default function App() {
  const config = useLiveConfig();
  const spec = config.decisionSpec;
  const outcomes = config.outcomes;
  const questions = spec?.questions || [];
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState({});
  const [phase, setPhase] = useState('questions');
  const [calculated, setCalculated] = useState(null);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [leadStatus, setLeadStatus] = useState('idle');
  const [leadError, setLeadError] = useState('');
  const started = useRef(false);

  // A tool configured with no questions is all result. Derived rather than held
  // in state: the question list arrives with the overlay, after first render.
  const showResult = phase === 'result' || questions.length === 0;
  const outcome = showResult ? (calculated ?? calculateDecision(answers)) : null;

  const question = questions[Math.min(step, Math.max(0, questions.length - 1))];
  const answer = question ? answers[question.id] : undefined;
  const hasAnswer = answer !== undefined && answer !== '';
  const result = outcome?.result;
  const band = outcome?.band;
  const capture = outcomes?.email_capture || {};
  const resultKey = result?.key || band?.key || 'complete';
  // The owner's band label wins over the model's result title: the band is what
  // they edited, and being told their edit is live has to mean something.
  const resultTitle = band?.label || result?.title || 'Your result is ready';
  const resultSummary =
    band?.description || result?.summary || 'A clear next step based on what you shared.';
  const recommendation =
    outcome?.advice?.[0] ||
    result?.recommendation ||
    'Use this result to decide the next step with confidence.';
  const ctaLabel = outcomes?.cta?.label || null;
  const ctaUrl = config.ctaUrl || outcomes?.cta?.url || null;
  const consentText = config.consentText || capture.consent_text || null;
  const captureHeading = capture.heading || 'Get your full results';
  const captureSubheading = capture.subheading || '';
  const submitLabel = capture.button_label || 'Send my results';
  const emailPlaceholder = capture.placeholder || '';
  const requireName = capture.require_name === true;
  const captureEnabled = capture.enabled !== false && config.acceptingLeads !== false;
  const displayedValue = useMemo(
    () => formatValue(spec, outcome?.value),
    [spec, outcome?.value]
  );

  function updateAnswer(value) {
    if (!started.current) {
      started.current = true;
      trackStart();
    } else if (question) {
      trackProgress(question.id);
    }
    setAnswers((current) => ({ ...current, [question.id]: value }));
  }

  function continueFlow() {
    if (!question || !hasAnswer) return;
    if (step < questions.length - 1) {
      setStep((current) => current + 1);
      return;
    }
    const finished = calculateDecision(answers);
    const key = finished.result?.key || finished.band?.key || 'complete';
    setCalculated(finished);
    setPhase('result');
    trackComplete(key);
    trackResult(key);
  }

  async function captureLead(event) {
    event.preventDefault();
    if (!isValidEmail(email)) {
      setLeadError('Enter a valid email address.');
      return;
    }
    setLeadStatus('sending');
    setLeadError('');
    const response = await submitLead({
      email,
      name: name || undefined,
      score: outcome?.value,
      answers,
      metadata: {
        qualification_status: outcome?.qualified ? 'qualified' : 'nurture',
        result_key: resultKey,
      },
    });
    if (response.ok) {
      setLeadStatus('done');
    } else {
      setLeadStatus('error');
      setLeadError(response.error);
    }
  }

  return (
    <main className="min-h-screen bg-[var(--color-background)] px-4 py-8 text-[var(--color-secondary)] sm:px-6 sm:py-14">
      <div className="mx-auto max-w-2xl">
        <div className="mb-5 flex items-center justify-between text-xs font-semibold uppercase tracking-[0.14em] text-[var(--color-secondary)]/65">
          <span>{spec?.mechanism || 'Interactive result'}</span>
          {!showResult && questions.length > 0 && (
            <span>{Math.min(step + 1, questions.length)} / {questions.length}</span>
          )}
        </div>

        <section className="rounded-[1.5rem] border border-black/10 bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.10)] sm:p-9">
          {!showResult && question ? (
            <>
              <p className="text-sm font-semibold text-[var(--color-primary)]">
                {spec?.value_before_gate || 'Get a useful answer'}
              </p>
              {step === 0 && (
                <h1 className="mt-2 font-[var(--font-heading)] text-3xl font-bold leading-tight tracking-tight text-[var(--color-secondary)] sm:text-4xl">
                  {spec?.buyer_question || question.label}
                </h1>
              )}
              <div className={step === 0 ? 'mt-8' : ''}>
                <label
                  htmlFor={question.input_type === 'number' ? question.id : undefined}
                  className="block font-[var(--font-heading)] text-xl font-bold leading-snug text-[var(--color-secondary)]"
                >
                  {question.label}
                </label>
                {question.help_text && (
                  <p className="mt-2 text-sm leading-6 text-[var(--color-secondary)]/70">
                    {question.help_text}
                  </p>
                )}
                <QuestionInput question={question} value={answer} onChange={updateAnswer} />
              </div>
              <button
                type="button"
                onClick={continueFlow}
                disabled={!hasAnswer}
                className="mt-7 min-h-12 w-full rounded-xl bg-[var(--color-primary)] px-5 text-sm font-bold text-white focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-45"
              >
                {step === questions.length - 1 ? 'See my result' : 'Continue'}
              </button>
            </>
          ) : (
            <div aria-live="polite">
              <p className="text-sm font-semibold text-[var(--color-primary)]">Your result</p>
              <h1 className="mt-2 font-[var(--font-heading)] text-3xl font-bold leading-tight tracking-tight text-[var(--color-secondary)] sm:text-5xl">
                {displayedValue || resultTitle}
              </h1>
              {displayedValue && (
                <p className="mt-3 text-lg font-semibold text-[var(--color-secondary)]">
                  {resultTitle}
                </p>
              )}
              <p className="mt-4 text-base leading-7 text-[var(--color-secondary)]/75">
                {resultSummary}
              </p>

              {leadStatus === 'done' ? (
                <div className="mt-8 rounded-2xl bg-[var(--color-background)] p-5">
                  <h2 className="font-[var(--font-heading)] text-xl font-bold">
                    Your next step
                  </h2>
                  <p className="mt-2 leading-7">{recommendation}</p>
                  <p className="mt-4 text-sm font-semibold text-[var(--color-primary)]">
                    Your details were saved successfully.
                  </p>
                  {ctaLabel && ctaUrl && (
                    <a
                      href={ctaUrl}
                      onClick={trackCta}
                      className="mt-5 inline-flex min-h-12 items-center rounded-xl bg-[var(--color-primary)] px-5 text-sm font-bold text-white focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:ring-offset-2"
                    >
                      {ctaLabel}
                    </a>
                  )}
                </div>
              ) : !captureEnabled ? (
                <div className="mt-8 border-t border-black/10 pt-7">
                  <p className="text-base leading-7">{recommendation}</p>
                  {ctaLabel && ctaUrl && (
                    <a
                      href={ctaUrl}
                      onClick={trackCta}
                      className="mt-5 inline-flex min-h-12 items-center rounded-xl bg-[var(--color-primary)] px-5 text-sm font-bold text-white focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:ring-offset-2"
                    >
                      {ctaLabel}
                    </a>
                  )}
                </div>
              ) : (
                <form onSubmit={captureLead} className="mt-8 border-t border-black/10 pt-7">
                  <h2 className="font-[var(--font-heading)] text-xl font-bold">
                    {captureHeading}
                  </h2>
                  {captureSubheading && (
                    <p className="mt-2 text-sm leading-6 text-[var(--color-secondary)]/70">
                      {captureSubheading}
                    </p>
                  )}
                  <div className={`mt-4 grid gap-4 ${requireName ? 'sm:grid-cols-2' : ''}`}>
                    {requireName && (
                      <div>
                        <label htmlFor="lead-name" className="text-sm font-semibold">Name</label>
                        <input
                          id="lead-name"
                          required
                          value={name}
                          onChange={(event) => setName(event.target.value)}
                          autoComplete="name"
                          className="mt-2 min-h-12 w-full rounded-xl border border-black/20 px-4 focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:ring-offset-2"
                        />
                      </div>
                    )}
                    <div>
                      <label htmlFor="lead-email" className="text-sm font-semibold">Email</label>
                      <input
                        id="lead-email"
                        type="email"
                        required
                        value={email}
                        placeholder={emailPlaceholder || undefined}
                        onChange={(event) => setEmail(event.target.value)}
                        autoComplete="email"
                        className="mt-2 min-h-12 w-full rounded-xl border border-black/20 px-4 focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:ring-offset-2"
                      />
                    </div>
                  </div>
                  {consentText && (
                    <p className="mt-4 text-xs leading-5 text-[var(--color-secondary)]/70">
                      {consentText}
                    </p>
                  )}
                  {leadError && <p role="alert" className="mt-3 text-sm text-red-700">{leadError}</p>}
                  <button
                    type="submit"
                    disabled={leadStatus === 'sending'}
                    className="mt-5 min-h-12 w-full rounded-xl bg-[var(--color-primary)] px-5 text-sm font-bold text-white focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:ring-offset-2 disabled:opacity-50"
                  >
                    {leadStatus === 'sending' ? 'Saving…' : submitLabel}
                  </button>
                </form>
              )}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
"""
