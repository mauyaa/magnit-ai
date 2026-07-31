import { Link, useNavigate } from "@tanstack/react-router";
import { ArrowRight, BarChart3, Check, Globe2, ShieldCheck, Users } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";

import { normalizeWebsiteUrl, websiteFieldValue } from "@/lib/website-url";
import { ConversionProof } from "./ConversionProof";
import { MarketingFooter } from "./MarketingFooter";

const STEPS = [
  {
    number: "01",
    title: "Paste the page",
    detail: "Magnitai reads the offer, audience, brand and decision the visitor is trying to make.",
  },
  {
    number: "02",
    title: "Choose the lead magnet",
    detail: "Compare two complete calculators, quizzes or audits before creating an account.",
  },
  {
    number: "03",
    title: "Publish and learn",
    detail:
      "Add one embed to your site, then see every result, lead and drop-off in one workspace.",
  },
] as const;

const OPERATING_VALUE = [
  {
    icon: Users,
    title: "Follow up with context",
    detail: "See the result, score and answers behind every lead.",
  },
  {
    icon: BarChart3,
    title: "Improve the right moment",
    detail: "Know where visitors stop and which tool creates action.",
  },
  {
    icon: ShieldCheck,
    title: "Keep it working",
    detail: "Magnitai watches the live tool and its source brand after launch.",
  },
] as const;

export function LandingPage() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [site, setSite] = useState("");
  const [siteError, setSiteError] = useState<string | null>(null);

  function startFromWebsite(event: FormEvent) {
    event.preventDefault();
    const normalized = normalizeWebsiteUrl(site);
    if (!normalized) {
      setSiteError("Enter a complete website, like northsidedental.com");
      inputRef.current?.focus();
      return;
    }

    setSiteError(null);
    navigate({
      to: "/build",
      search: { site: websiteFieldValue(normalized), start: true },
    });
  }

  return (
    <div className="text-foreground">
      <section className="mx-auto flex min-h-[72vh] max-w-6xl items-center px-6 pb-16 pt-28 lg:px-8">
        <div className="w-full">
          <div className="mx-auto max-w-4xl text-center">
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              Interactive lead magnets for existing websites
            </span>
            <h1 className="mx-auto mt-5 max-w-[16ch] text-balance font-display text-[clamp(3rem,6.8vw,6.2rem)] font-normal leading-[0.92] tracking-[-0.055em]">
              Turn more website visitors into qualified leads.
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-balance text-base leading-7 text-muted-foreground sm:text-lg sm:leading-8">
              Magnitai turns one of your website pages into a branded calculator, quiz or audit that
              gives visitors a useful result—and gives your business the context to follow up.
            </p>
          </div>

          <form
            onSubmit={startFromWebsite}
            className="mx-auto mt-9 max-w-[43rem] text-left"
            noValidate
          >
            <label htmlFor="landing-website" className="sr-only">
              Your website address
            </label>
            <div
              className={`grid overflow-hidden rounded-[1.15rem] border bg-card p-1.5 shadow-float transition-[border-color,box-shadow] focus-within:ring-4 focus-within:ring-foreground/5 sm:grid-cols-[minmax(0,1fr)_13.5rem] ${
                siteError
                  ? "border-destructive"
                  : "border-border-strong focus-within:border-foreground"
              }`}
            >
              <div className="flex h-14 min-w-0 items-center px-3">
                <Globe2 className="mr-3 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span className="shrink-0 text-[15px] text-muted-foreground">https://</span>
                <input
                  ref={inputRef}
                  id="landing-website"
                  name="website"
                  type="text"
                  inputMode="url"
                  autoComplete="url"
                  spellCheck={false}
                  placeholder="yourwebsite.com"
                  value={site}
                  onChange={(event) => {
                    setSite(websiteFieldValue(event.target.value));
                    if (siteError) setSiteError(null);
                  }}
                  aria-invalid={siteError ? true : undefined}
                  aria-describedby={siteError ? "landing-website-error" : "landing-website-help"}
                  className="h-full min-w-0 flex-1 bg-transparent text-[15px] text-foreground outline-none placeholder:text-n-400"
                />
              </div>
              <button
                type="submit"
                className="group flex h-14 items-center justify-between rounded-[0.85rem] bg-brand px-5 text-sm font-semibold text-foreground transition hover:brightness-95"
              >
                Build from my website
                <ArrowRight
                  className="size-4 transition-transform group-hover:translate-x-0.5"
                  aria-hidden="true"
                />
              </button>
            </div>
            {siteError ? (
              <p id="landing-website-error" role="alert" className="mt-2 text-sm text-destructive">
                {siteError}
              </p>
            ) : (
              <p
                id="landing-website-help"
                className="mt-3 flex flex-wrap justify-center gap-x-5 gap-y-1 text-xs text-muted-foreground"
              >
                {["Preview before signup", "No card required", "Nothing publishes without you"].map(
                  (item) => (
                    <span key={item} className="inline-flex items-center gap-1.5">
                      <Check className="size-3 text-foreground" aria-hidden="true" />
                      {item}
                    </span>
                  ),
                )}
              </p>
            )}
          </form>
        </div>
      </section>

      <ConversionProof />

      <section className="border-b border-border bg-background" aria-labelledby="path-title">
        <div className="mx-auto max-w-6xl px-6 py-16 lg:px-8 lg:py-20">
          <div className="flex flex-col gap-5 border-b border-foreground pb-7 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                From page to lead magnet
              </span>
              <h2
                id="path-title"
                className="mt-4 max-w-[15ch] font-display text-[clamp(2.5rem,4.8vw,4.4rem)] font-normal leading-[0.94] tracking-[-0.05em]"
              >
                One clear path to something live.
              </h2>
            </div>
            <Link
              to="/how-it-works"
              className="group inline-flex items-center gap-2 text-sm font-semibold"
            >
              See the full journey
              <ArrowRight
                className="size-4 transition-transform group-hover:translate-x-1"
                aria-hidden="true"
              />
            </Link>
          </div>

          <ol className="grid border-b border-border sm:grid-cols-3">
            {STEPS.map((step) => (
              <li
                key={step.number}
                className="border-b border-border py-7 last:border-b-0 sm:border-b-0 sm:border-r sm:px-6 sm:first:pl-0 sm:last:border-r-0 sm:last:pr-0"
              >
                <span className="font-mono text-[10px] text-muted-foreground">{step.number}</span>
                <h3 className="mt-4 text-lg font-medium tracking-[-0.025em]">{step.title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{step.detail}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="bg-cream" aria-labelledby="operating-value-title">
        <div className="mx-auto max-w-6xl px-6 py-16 lg:px-8 lg:py-20">
          <div className="grid gap-10 lg:grid-cols-[0.72fr_1.28fr] lg:items-start">
            <div>
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                After launch
              </span>
              <h2
                id="operating-value-title"
                className="mt-4 max-w-[13ch] font-display text-[clamp(2.5rem,4.8vw,4.4rem)] font-normal leading-[0.94] tracking-[-0.05em]"
              >
                Know what happened. Know what to do next.
              </h2>
              <p className="mt-5 max-w-md text-sm leading-6 text-muted-foreground">
                The workspace turns every visit into a simple operating view: results, leads, the
                next improvement and the health of every live tool.
              </p>
              <Link to="/pricing" className="btn btn-secondary mt-7">
                Compare plans
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </div>

            <div className="overflow-hidden rounded-[1.5rem] border border-border bg-card shadow-card">
              {OPERATING_VALUE.map(({ icon: Icon, title, detail }) => (
                <article
                  key={title}
                  className="grid grid-cols-[2.5rem_1fr] gap-4 border-b border-border p-5 last:border-b-0 sm:p-6"
                >
                  <span className="grid size-10 place-items-center rounded-xl bg-secondary">
                    <Icon className="size-4" aria-hidden="true" />
                  </span>
                  <div>
                    <h3 className="text-sm font-semibold">{title}</h3>
                    <p className="mt-1 text-sm leading-6 text-muted-foreground">{detail}</p>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>

      <MarketingFooter />
    </div>
  );
}
