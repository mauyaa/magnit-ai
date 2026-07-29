import { Link } from "@tanstack/react-router";
import {
  ArrowRight,
  Calculator,
  Check,
  CheckSquare,
  CircleCheck,
  HelpCircle,
  Layers,
  SearchCheck,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";

import { SHOWCASE } from "@/lib/showcase";
import { DecisionPreview } from "./DecisionPreview";
import { MarketingFooter } from "./MarketingFooter";

type FormatId = "calculator" | "quiz" | "audit" | "comparison" | "checklist";

interface Format {
  id: FormatId;
  name: string;
  shortName: string;
  icon: LucideIcon;
  bestFor: string;
  visitorGets: string;
  leadMoment: string;
}

const FORMATS: Format[] = [
  {
    id: "calculator",
    name: "ROI calculator",
    shortName: "Calculate",
    icon: Calculator,
    bestFor: "A service whose value is easier to calculate than explain.",
    visitorGets: "A personalised value, saving or opportunity.",
    leadMoment: "Email the full calculation",
  },
  {
    id: "quiz",
    name: "Readiness quiz",
    shortName: "Score",
    icon: HelpCircle,
    bestFor: "A long sales cycle where the buyer needs to see the problem first.",
    visitorGets: "A score, a band and the clearest next action.",
    leadMoment: "Send the action plan",
  },
  {
    id: "audit",
    name: "Audit tool",
    shortName: "Diagnose",
    icon: SearchCheck,
    bestFor: "A service that normally starts with a free assessment call.",
    visitorGets: "A graded breakdown of what is working and what is not.",
    leadMoment: "Unlock the detailed findings",
  },
  {
    id: "comparison",
    name: "Comparison tool",
    shortName: "Compare",
    icon: Layers,
    bestFor: "A crowded category where buyers already compare alternatives.",
    visitorGets: "An honest side-by-side and a recommended path.",
    leadMoment: "Save the recommendation",
  },
  {
    id: "checklist",
    name: "Interactive checklist",
    shortName: "Plan",
    icon: CheckSquare,
    bestFor: "Any service with a sequence: onboarding, moving or compliance.",
    visitorGets: "A prioritised plan based on what is already complete.",
    leadMoment: "Email the remaining plan",
  },
];

function Specimen({ format }: { format: FormatId }) {
  const [customers, setCustomers] = useState(24);
  const [answer, setAnswer] = useState(0);
  const [checked, setChecked] = useState([true, false, false]);

  if (format === "calculator") {
    const result = customers * 8400;
    return (
      <div>
        <p className="text-sm text-foreground/65">Revenue calculator</p>
        <h3 className="mt-2 max-w-[11ch] text-4xl font-medium leading-[0.94] tracking-[-0.055em]">
          What is your growth worth?
        </h3>
        <label className="mt-10 block">
          <span className="flex items-center justify-between text-xs font-semibold uppercase tracking-[0.08em]">
            New customers / month
            <strong className="rounded-full border border-foreground/20 px-3 py-1 text-sm tracking-normal">
              {customers}
            </strong>
          </span>
          <input
            className="mt-4 h-11 w-full cursor-pointer accent-[var(--ink)]"
            type="range"
            min="1"
            max="60"
            value={customers}
            onChange={(event) => setCustomers(Number(event.target.value))}
          />
        </label>
        <div className="mt-7 border-t border-foreground/20 pt-6">
          <span className="text-xs font-semibold uppercase tracking-[0.08em]">
            Annual opportunity
          </span>
          <strong className="mt-1 block text-[clamp(2.7rem,7vw,5rem)] leading-none tracking-[-0.075em]">
            ${result.toLocaleString()}
          </strong>
        </div>
      </div>
    );
  }

  if (format === "quiz") {
    return (
      <div>
        <p className="text-sm text-foreground/65">Growth readiness · 02 / 04</p>
        <h3 className="mt-2 max-w-[14ch] text-4xl font-medium leading-[0.98] tracking-[-0.05em]">
          How clearly can a buyer see the outcome?
        </h3>
        <div className="mt-9 grid gap-2" role="radiogroup" aria-label="Choose an answer">
          {["Immediately", "After some reading", "Only after a call"].map((label, index) => (
            <button
              key={label}
              type="button"
              role="radio"
              aria-checked={answer === index}
              onClick={() => setAnswer(index)}
              className={`flex min-h-12 items-center justify-between rounded-xl border px-4 text-left text-sm transition-colors ${
                answer === index
                  ? "border-foreground bg-foreground text-background"
                  : "border-foreground/20 bg-white/30 hover:border-foreground/45"
              }`}
            >
              {label}
              {answer === index ? <Check className="size-4" aria-hidden="true" /> : null}
            </button>
          ))}
        </div>
        <div className="mt-8 h-1.5 overflow-hidden rounded-full bg-foreground/15">
          <div className="h-full w-1/2 rounded-full bg-foreground" />
        </div>
      </div>
    );
  }

  if (format === "audit") {
    return (
      <div>
        <p className="text-sm text-foreground/65">Website growth audit</p>
        <h3 className="mt-2 max-w-[12ch] text-4xl font-medium leading-[0.98] tracking-[-0.05em]">
          Find the clearest growth gap.
        </h3>
        <label className="mt-9 block text-xs font-semibold uppercase tracking-[0.08em]">
          Website address
          <span className="mt-2 flex min-h-12 items-center rounded-xl border border-foreground/25 bg-white/35 px-4 text-sm font-normal normal-case tracking-normal text-foreground/70">
            yourbusiness.com
          </span>
        </label>
        <div className="mt-7 grid grid-cols-[1fr_auto] items-end gap-4 border-t border-foreground/20 pt-6">
          <div>
            <span className="text-xs font-semibold uppercase tracking-[0.08em]">Growth score</span>
            <strong className="mt-1 block text-7xl leading-none tracking-[-0.08em]">84</strong>
          </div>
          <div className="space-y-2 pb-1 text-xs">
            {["Offer clarity", "Proof", "Next step"].map((item, index) => (
              <span key={item} className="flex items-center justify-end gap-2">
                {item}
                <i
                  className={`block size-2 rounded-full ${index < 2 ? "bg-success" : "bg-warning"}`}
                />
              </span>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (format === "comparison") {
    return (
      <div>
        <p className="text-sm text-foreground/65">Path comparison</p>
        <h3 className="mt-2 max-w-[14ch] text-4xl font-medium leading-[0.98] tracking-[-0.05em]">
          Which route gets you live sooner?
        </h3>
        <div className="mt-9 grid gap-3 sm:grid-cols-2">
          {[
            { label: "Current process", time: "6–8 weeks", tone: "bg-white/35" },
            { label: "Recommended path", time: "10 days", tone: "bg-foreground text-background" },
          ].map((item, index) => (
            <div
              key={item.label}
              className={`rounded-2xl border border-foreground/20 p-4 ${item.tone}`}
            >
              <span className="text-xs opacity-70">{item.label}</span>
              <strong className="mt-10 block text-3xl tracking-[-0.05em]">{item.time}</strong>
              {index === 1 ? (
                <span className="mt-2 inline-flex items-center gap-1 text-xs">
                  <CircleCheck className="size-3.5" aria-hidden="true" />
                  Best fit
                </span>
              ) : null}
            </div>
          ))}
        </div>
      </div>
    );
  }

  const tasks = ["Define the goal", "Connect the form", "Add proof"];
  return (
    <div>
      <p className="text-sm text-foreground/65">Launch checklist</p>
      <h3 className="mt-2 max-w-[13ch] text-4xl font-medium leading-[0.98] tracking-[-0.05em]">
        What is left before launch?
      </h3>
      <div className="mt-9 grid gap-2">
        {tasks.map((task, index) => (
          <button
            key={task}
            type="button"
            aria-pressed={checked[index]}
            onClick={() =>
              setChecked((items) => items.map((value, item) => (item === index ? !value : value)))
            }
            className="flex min-h-12 items-center gap-3 rounded-xl border border-foreground/20 bg-white/30 px-4 text-left text-sm"
          >
            <span
              className={`grid size-6 place-items-center rounded-full border ${
                checked[index]
                  ? "border-foreground bg-foreground text-background"
                  : "border-foreground/30"
              }`}
            >
              {checked[index] ? <Check className="size-3.5" aria-hidden="true" /> : null}
            </span>
            <span className={checked[index] ? "line-through opacity-55" : ""}>{task}</span>
          </button>
        ))}
      </div>
      <p className="mt-6 text-sm text-foreground/65">
        {checked.filter(Boolean).length} of {tasks.length} complete
      </p>
    </div>
  );
}

export function WidgetGallery() {
  const [activeId, setActiveId] = useState<FormatId>("calculator");
  const active = FORMATS.find((format) => format.id === activeId) ?? FORMATS[0];

  return (
    <>
      <div>
        <section className="mx-auto max-w-6xl px-6 pb-16 pt-36 lg:px-8 lg:pb-24 lg:pt-44">
          <div className="grid items-end gap-12 lg:grid-cols-[1.15fr_0.85fr]">
            <div>
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                What we build · Five useful formats
              </span>
              <h1 className="mt-5 max-w-[13ch] text-balance font-display text-[clamp(3.2rem,6.3vw,6rem)] font-normal leading-[0.9] tracking-[-0.055em] text-foreground">
                Not another form. A useful answer.
              </h1>
            </div>
            <div className="border-t border-foreground pt-5 lg:mb-2">
              <p className="max-w-md text-base leading-7 text-muted-foreground">
                The format follows the question your buyer needs answered. Try each specimen below;
                every control is real.
              </p>
              <Link
                to="/build"
                className="group mt-7 inline-flex min-h-11 items-center gap-2 text-sm font-semibold"
              >
                Build from your website
                <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" />
              </Link>
            </div>
          </div>
        </section>

        <section className="editorial-grid-dark relative overflow-hidden bg-inverse text-inverse-foreground">
          <div className="relative mx-auto grid max-w-6xl gap-8 px-6 py-8 lg:grid-cols-[17rem_1fr] lg:px-8 lg:py-12">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-brand-on-inverse">
                Product specimen
              </p>
              <div className="mt-5 grid gap-1" role="tablist" aria-label="Widget format">
                {FORMATS.map((format, index) => {
                  const Icon = format.icon;
                  const selected = activeId === format.id;
                  return (
                    <button
                      key={format.id}
                      type="button"
                      role="tab"
                      id={`format-tab-${format.id}`}
                      aria-controls="format-panel"
                      aria-selected={selected}
                      onClick={() => setActiveId(format.id)}
                      className={`group flex min-h-12 items-center gap-3 rounded-xl px-3 text-left text-sm transition-colors ${
                        selected
                          ? "bg-brand text-foreground"
                          : "text-inverse-muted hover:bg-inverse-raised hover:text-inverse-foreground"
                      }`}
                    >
                      <span className="w-5 font-mono text-[10px] opacity-65">0{index + 1}</span>
                      <Icon className="size-4 shrink-0" aria-hidden="true" />
                      <span className="font-medium">{format.name}</span>
                    </button>
                  );
                })}
              </div>
              <p className="mt-6 max-w-[28ch] text-sm leading-6 text-inverse-muted">
                {active.bestFor}
              </p>
            </div>

            <div
              id="format-panel"
              role="tabpanel"
              aria-labelledby={`format-tab-${active.id}`}
              className="min-h-[34rem] rounded-[2rem] bg-brand p-5 text-foreground shadow-float sm:p-8 lg:p-10"
            >
              <div className="mx-auto flex min-h-[29rem] max-w-2xl flex-col rounded-[1.5rem] border border-foreground/20 bg-brand px-5 py-6 sm:px-8 sm:py-8">
                <div className="mb-8 flex items-center justify-between border-b border-foreground/20 pb-4 font-mono text-[10px] uppercase tracking-[0.14em]">
                  <span>{active.name}</span>
                  <span>Example / 01</span>
                </div>
                <Specimen format={active.id} />
                <button
                  type="button"
                  className="mt-auto flex min-h-12 items-center justify-between rounded-full bg-foreground px-5 text-sm font-semibold text-background"
                >
                  {active.leadMoment}
                  <ArrowRight className="size-4" aria-hidden="true" />
                </button>
              </div>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-6 py-20 lg:px-8 lg:py-28">
          <div className="grid gap-10 lg:grid-cols-[0.65fr_1.35fr]">
            <div>
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Choose by outcome
              </span>
              <h2 className="mt-4 max-w-[12ch] text-3xl font-medium leading-[1.02] tracking-[-0.04em]">
                The interface is the last decision, not the first.
              </h2>
              <p className="mt-4 max-w-sm text-sm leading-6 text-muted-foreground">
                Start with what a visitor should understand or decide. Magnitai proposes the format
                that asks for the least effort.
              </p>
            </div>

            <div className="overflow-hidden rounded-[1.5rem] border border-border bg-card">
              <div className="hidden grid-cols-[0.75fr_1.15fr_1.15fr] gap-5 border-b border-border px-5 py-3 font-mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground sm:grid">
                <span>Format</span>
                <span>Best when</span>
                <span>Visitor gets</span>
              </div>
              <ol className="divide-y divide-border">
                {FORMATS.map((format, index) => (
                  <li
                    key={format.id}
                    className="grid gap-4 px-5 py-5 sm:grid-cols-[0.75fr_1.15fr_1.15fr] sm:gap-5"
                  >
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-[10px] text-muted-foreground">
                        0{index + 1}
                      </span>
                      <strong className="text-sm">{format.name}</strong>
                    </div>
                    <p className="text-sm leading-6 text-muted-foreground">{format.bestFor}</p>
                    <p className="text-sm leading-6 text-foreground">{format.visitorGets}</p>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </section>

        <PlayableExamples />
      </div>

      <MarketingFooter />
    </>
  );
}

/**
 * Three finished tools, playable without a URL and without an account.
 *
 * The rest of this page explains five formats. Explaining is not the same as
 * showing, and a visitor deciding whether to spend a minute of their own site's
 * time on us is deciding against competitors who lead with hundreds of browsable
 * templates. These run through `DecisionPreview` — the same component and the
 * same scoring the builder produces — so playing one is genuinely using the
 * product rather than watching a mock of it.
 *
 * The businesses are generic by design. Dressing an example in a real company's
 * brand implies a customer who does not exist, and not claiming things we cannot
 * evidence is the one rule this product is built around.
 */
function PlayableExamples() {
  const [openId, setOpenId] = useState(SHOWCASE[0].id);
  const open = SHOWCASE.find((example) => example.id === openId) ?? SHOWCASE[0];

  return (
    <section
      className="mx-auto max-w-6xl px-6 pb-24 lg:px-8"
      aria-labelledby="playable-examples-title"
    >
      <div className="border-t border-foreground pt-8">
        <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          Finished examples · Nothing to sign up for
        </span>
        <h2
          id="playable-examples-title"
          className="mt-4 max-w-[18ch] text-balance font-display text-[clamp(2.2rem,4.4vw,3.6rem)] font-normal leading-[0.94] tracking-[-0.05em] text-foreground"
        >
          Play one before you give us anything.
        </h2>
        <p className="mt-4 max-w-xl text-base leading-7 text-muted-foreground">
          Each of these is a complete tool of the kind Magnitai builds from a website — real
          questions, real scoring, a real result at the end. Answer one and see what your visitor
          would see.
        </p>
      </div>

      <div className="mt-9 flex flex-wrap gap-2" role="tablist" aria-label="Example tools">
        {SHOWCASE.map((example) => {
          const selected = example.id === open.id;
          return (
            <button
              key={example.id}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => setOpenId(example.id)}
              className={`rounded-full border px-4 py-2 text-sm transition-colors motion-reduce:transition-none ${
                selected
                  ? "border-foreground bg-foreground text-background"
                  : "border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              {example.business}
            </button>
          );
        })}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[0.85fr_1.15fr]">
        <div className="surface p-5 sm:p-6">
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
            {open.sector}
          </span>
          <h3 className="mt-3 text-xl font-medium tracking-[-0.03em] text-foreground">
            {open.business}
          </h3>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">{open.reasoning}</p>

          <dl className="mt-6 grid gap-4 border-t border-border pt-5 text-sm">
            <div>
              <dt className="font-mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground">
                The decision it helps with
              </dt>
              <dd className="mt-1 text-foreground">{open.architect.decision?.buyer_question}</dd>
            </div>
            <div>
              <dt className="font-mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground">
                What they get before any email
              </dt>
              <dd className="mt-1 text-foreground">{open.architect.decision?.value_before_gate}</dd>
            </div>
          </dl>

          <Link to="/build" className="btn btn-primary mt-7 h-10 w-full text-sm">
            Build this from my website
            <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </div>

        {/* Keyed so switching examples resets the answers rather than carrying
            one tool's state into another's questions. */}
        <DecisionPreview key={open.id} architect={open.architect} />
      </div>
    </section>
  );
}
