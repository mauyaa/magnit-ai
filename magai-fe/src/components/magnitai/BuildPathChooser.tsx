import { ArrowRight, Check, Globe2, Loader2 } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { normalizeWebsiteUrl } from "@/lib/website-url";

const NEXT_STEPS = [
  {
    number: "01",
    title: "We read the page",
    detail: "The offer, audience, language and visual cues.",
  },
  {
    number: "02",
    title: "We recommend the format",
    detail: "The calculator, quiz or audit that best fits that page.",
  },
  {
    number: "03",
    title: "You try two complete options",
    detail: "Preview the visitor result before you sign up.",
  },
] as const;

export function BuildPathChooser({
  initialSite,
  pending,
  requestError,
  resumedDomain,
  onStart,
  onCustomize,
  onClearError,
  onBack,
}: {
  initialSite?: string;
  pending: boolean;
  requestError?: string | null;
  /**
   * Set when the customer came back to a draft that was analysed but never
   * taken further. There are no concepts to restore at that point, so the
   * continuity that can honestly be offered is the site itself — which is a
   * great deal better than an empty form and no explanation.
   */
  resumedDomain?: string | null;
  onStart: (url: string) => void;
  onCustomize: (url: string) => void;
  onClearError?: () => void;
  onBack: () => void;
}) {
  const [site, setSite] = useState(initialSite ?? "");
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const message = error ?? requestError;

  /*
   * A resumed draft arrives after this screen has already mounted, and seeding
   * state on mount alone means the field stays empty — so the page says "pick
   * up where you left off" and then asks for the URL again anyway. Adopted only
   * while the field is untouched: whatever the customer has typed outranks
   * anything we recover.
   */
  useEffect(() => {
    if (initialSite && !site) setSite(initialSite);
    // `site` is deliberately absent: this must not re-run as they type, or
    // clearing the field would immediately refill it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialSite]);

  function normalizedSite(): string | null {
    const normalized = normalizeWebsiteUrl(site);
    if (!normalized) {
      setError("Enter a complete website, like northsidedental.com");
      inputRef.current?.focus();
      return null;
    }

    setError(null);
    return normalized;
  }

  function begin(event: FormEvent) {
    event.preventDefault();
    const url = normalizedSite();
    if (url) onStart(url);
  }

  function customize() {
    const url = normalizedSite();
    if (url) onCustomize(url);
  }

  return (
    <div className="mx-auto min-h-[100svh] max-w-[72rem] px-5 pb-20 pt-24 sm:px-6 sm:pt-28 lg:px-8">
      <div className="mx-auto max-w-[50rem]">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex min-h-11 items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowRight className="size-4 rotate-180" aria-hidden="true" />
          Back
        </button>

        <div className="mt-7 flex items-center justify-between gap-6 text-[11px] font-medium text-muted-foreground">
          <span className="uppercase tracking-[0.12em]">Lead magnet builder</span>
          <span>Step 1 of 3 · Website</span>
        </div>
        <div className="mt-3 h-0.5 overflow-hidden rounded-full bg-border" aria-hidden="true">
          <span className="block h-full w-1/3 rounded-full bg-foreground" />
        </div>

        <main className="pt-9 sm:pt-10" aria-labelledby="build-entry-title">
          <h1
            id="build-entry-title"
            className="max-w-[17ch] font-heading text-[clamp(2.55rem,5.5vw,4.25rem)] font-medium leading-[0.96] tracking-[-0.055em] text-foreground"
          >
            {resumedDomain
              ? "Pick up where you left off."
              : "Build the right lead magnet from one website page."}
          </h1>
          <p className="mt-5 max-w-[39rem] text-[15px] leading-7 text-muted-foreground sm:text-lg sm:leading-8">
            {resumedDomain
              ? `You read ${resumedDomain} but never chose a direction. Continue and Magnitai will recommend one.`
              : "Paste the exact page where visitors learn about your offer. Magnitai will recommend the strongest calculator, quiz or audit for that audience."}
          </p>

          <form onSubmit={begin} className="mt-8 sm:mt-9">
            <label
              htmlFor="build-site"
              className="mb-2.5 block text-sm font-medium text-foreground"
            >
              Website page to analyse
            </label>

            <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_12rem]">
              <div
                className={`flex h-14 min-w-0 items-center rounded-xl border bg-card px-4 transition-[border-color,box-shadow] focus-within:ring-4 focus-within:ring-foreground/5 ${
                  message
                    ? "border-destructive focus-within:border-destructive"
                    : "border-border-strong focus-within:border-foreground/50"
                }`}
              >
                <Globe2 className="mr-3 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span className="shrink-0 text-[15px] text-muted-foreground">https://</span>
                <input
                  ref={inputRef}
                  id="build-site"
                  name="site"
                  type="text"
                  inputMode="url"
                  autoComplete="url"
                  spellCheck={false}
                  placeholder="yourwebsite.com/services"
                  value={site}
                  onChange={(event) => {
                    setSite(event.target.value);
                    if (error) setError(null);
                    if (requestError) onClearError?.();
                  }}
                  aria-invalid={message ? true : undefined}
                  aria-describedby={message ? "build-site-error" : "build-site-help"}
                  className="h-full min-w-0 flex-1 bg-transparent text-[15px] text-foreground outline-none placeholder:text-n-400"
                />
              </div>

              <button
                type="submit"
                disabled={pending}
                aria-busy={pending}
                className="group flex h-14 items-center justify-between rounded-xl bg-brand px-5 text-sm font-semibold text-foreground shadow-card transition duration-200 hover:-translate-y-0.5 hover:brightness-95 hover:shadow-float disabled:pointer-events-none disabled:opacity-60"
              >
                {pending ? (
                  <>
                    Creating previews
                    <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  </>
                ) : (
                  <>
                    Recommend my lead magnet
                    <ArrowRight
                      className="size-4 transition-transform group-hover:translate-x-0.5"
                      aria-hidden="true"
                    />
                  </>
                )}
              </button>
            </div>

            {message ? (
              <p id="build-site-error" role="alert" className="mt-3 text-sm text-destructive">
                {message}
              </p>
            ) : (
              <p
                id="build-site-help"
                className="mt-3 flex items-center gap-2 text-xs leading-5 text-muted-foreground"
              >
                <Check className="size-3.5 shrink-0 text-brand-solid" aria-hidden="true" />
                We only read publicly available page content.
              </p>
            )}

            <div className="mt-7 flex flex-col items-start justify-between gap-4 border-t border-border pt-6 sm:flex-row sm:items-center">
              <div>
                <p className="text-sm font-medium text-foreground">Know what you want to build?</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  Set the audience, outcome and questions before Magnitai recommends it.
                </p>
              </div>
              <button
                type="button"
                onClick={customize}
                disabled={pending}
                className="inline-flex min-h-11 shrink-0 items-center gap-2 rounded-lg border border-border-strong bg-card px-4 text-sm font-semibold text-foreground transition hover:border-foreground/40 hover:bg-secondary disabled:pointer-events-none disabled:opacity-60"
              >
                Shape it with me
                <ArrowRight className="size-4" aria-hidden="true" />
              </button>
            </div>
          </form>
        </main>

        <section
          className="mt-12 border-t border-border pt-7 sm:mt-16"
          aria-labelledby="next-title"
        >
          <h2 id="next-title" className="text-sm font-medium text-foreground">
            What happens next
          </h2>
          <ol className="mt-5 grid border-y border-border sm:grid-cols-3">
            {NEXT_STEPS.map((step) => (
              <li
                key={step.number}
                className="border-b border-border py-5 last:border-b-0 sm:border-b-0 sm:border-r sm:px-5 sm:first:pl-0 sm:last:border-r-0 sm:last:pr-0"
              >
                <span className="font-mono text-[10px] text-muted-foreground">{step.number}</span>
                <h3 className="mt-3 text-sm font-semibold text-foreground">{step.title}</h3>
                <p className="mt-1.5 text-xs leading-5 text-muted-foreground">{step.detail}</p>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </div>
  );
}
