import { ArrowRight, ArrowUpRight, Check, TrendingUp } from "lucide-react";
import { useState } from "react";

function AuditCard() {
  return (
    <article
      className="showcase-card showcase-card-audit"
      aria-label="Website growth audit example"
    >
      <div className="showcase-card-topline">
        <span>Website growth audit</span>
        <span className="showcase-card-badge">02 min</span>
      </div>
      <div className="showcase-orbit" aria-hidden="true" />
      <div className="showcase-audit-content">
        <p className="showcase-serif">Your clearest growth gap</p>
        <h3>Make the outcome obvious.</h3>
        <div className="showcase-score">
          <div>
            <span>Growth score</span>
            <strong>84</strong>
          </div>
          <div className="showcase-score-ring" aria-hidden="true">
            <span />
          </div>
        </div>
        <div className="showcase-insight">
          <ArrowUpRight className="size-4" />
          Top priority
        </div>
      </div>
    </article>
  );
}

function CalculatorCard() {
  const [customers, setCustomers] = useState(24);
  const annualVal = (customers * 100000).toLocaleString();

  // Dynamic SVG curve calculation based on current customer slider value
  const h1 = Math.max(10, 55 - customers * 0.7);
  const h2 = Math.max(8, 40 - customers * 0.5);
  const h3 = Math.max(4, 18 - customers * 0.25);
  const svgPath = `M 0,60 Q 50,${h1} 100,${h2} T 200,${h3} L 200,70 L 0,70 Z`;
  const linePath = `M 0,60 Q 50,${h1} 100,${h2} T 200,${h3}`;

  return (
    <article
      className="showcase-card showcase-card-calculator"
      aria-label="Revenue opportunity calculator example"
    >
      <div className="showcase-card-topline">
        <span>Revenue opportunity</span>
        <span>Estimate / 01</span>
      </div>
      <div className="showcase-calculator-intro">
        <p className="showcase-serif">Revenue calculator</p>
        <h3>What is your growth worth?</h3>
      </div>

      {/* Dynamic SVG Area Curve Chart */}
      <div className="mt-3 mb-1 h-14 w-full overflow-hidden rounded-xl border border-black/10 bg-black/5 p-1 relative">
        <svg viewBox="0 0 200 70" className="w-full h-full" preserveAspectRatio="none">
          <defs>
            <linearGradient id="calc-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#22c55e" stopOpacity="0.45" />
              <stop offset="100%" stopColor="#22c55e" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d={svgPath} fill="url(#calc-grad)" />
          <path d={linePath} fill="none" stroke="#22c55e" strokeWidth="3" strokeLinecap="round" />
        </svg>
      </div>

      <div className="showcase-controls">
        <div className="showcase-control-label">
          <span>New customers / month</span>
          <strong className="transition-all duration-150">{customers}</strong>
        </div>
        <input
          type="range"
          min="1"
          max="60"
          value={customers}
          onChange={(e) => setCustomers(Number(e.target.value))}
          className="w-full cursor-pointer accent-slate-900 dark:accent-lime-400 my-2 transition-opacity hover:opacity-90"
          aria-label="New customers per month"
        />
        <div className="showcase-control-foot">
          <span>0</span>
          <span>60</span>
        </div>
      </div>
      <div className="showcase-calculator-result">
        <span>
          <TrendingUp className="size-4" /> Annual opportunity
        </span>
        <strong className="transition-all duration-200">${annualVal}</strong>
        <span className="showcase-card-cta cursor-pointer transition-all duration-200 hover:scale-[1.01] active:scale-[0.98]">
          See my result
          <ArrowRight className="size-4" />
        </span>
      </div>
    </article>
  );
}

function QuizCard() {
  const [step, setStep] = useState<"q1" | "q2" | "result">("q1");
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [q2Idx, setQ2Idx] = useState(1);

  const options = ["Plateaued growth", "Low-quality leads", "Unclear offer"];
  const q2Options = ["10–50 leads/mo", "50–200 leads/mo", "200+ leads/mo"];

  return (
    <article
      className="showcase-card showcase-card-quiz"
      aria-label="Growth readiness quiz example"
    >
      <div className="showcase-card-topline text-white/75">
        <span>Growth quiz</span>
        <span>{step === "q1" ? "01 / 02" : step === "q2" ? "02 / 02" : "Result"}</span>
      </div>

      <div className="showcase-quiz-progress">
        <i style={{ width: step === "q1" ? "50%" : "100%" }} />
      </div>

      {step === "q1" && (
        <>
          <div className="showcase-quiz-copy">
            <p className="showcase-serif">Your next move</p>
            <h3>What's blocking growth?</h3>
          </div>
          <div className="showcase-options">
            {options.map((label, index) => (
              <button
                type="button"
                key={label}
                onClick={() => setSelectedIdx(index)}
                className={`w-full text-left transition-all duration-200 active:scale-[0.99] ${index === selectedIdx ? "is-selected shadow-xs font-semibold" : "hover:bg-white/10"}`}
              >
                <span>{label}</span>
                <i>{index === selectedIdx && <Check className="size-3.5" />}</i>
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => setStep("q2")}
            className="showcase-quiz-next cursor-pointer w-full text-left transition-all duration-200 hover:opacity-90 active:scale-[0.98]"
          >
            <span>Next Question</span>
            <ArrowUpRight className="size-4" />
          </button>
        </>
      )}

      {step === "q2" && (
        <>
          <div className="showcase-quiz-copy">
            <p className="showcase-serif">Scale Potential</p>
            <h3>What is your lead target?</h3>
          </div>
          <div className="showcase-options">
            {q2Options.map((label, index) => (
              <button
                type="button"
                key={label}
                onClick={() => setQ2Idx(index)}
                className={`w-full text-left transition-all duration-200 active:scale-[0.99] ${index === q2Idx ? "is-selected shadow-xs font-semibold" : "hover:bg-white/10"}`}
              >
                <span>{label}</span>
                <i>{index === q2Idx && <Check className="size-3.5" />}</i>
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => setStep("result")}
            className="showcase-quiz-next cursor-pointer w-full text-left transition-all duration-200 hover:opacity-90 active:scale-[0.98]"
          >
            <span>View Analysis</span>
            <ArrowUpRight className="size-4" />
          </button>
        </>
      )}

      {step === "result" && (
        <div className="mt-4 flex flex-col h-full justify-between animate-in fade-in duration-300">
          <div>
            <span className="inline-flex items-center gap-1.5 font-mono text-[10px] text-emerald-400 uppercase tracking-widest bg-emerald-400/10 px-2.5 py-1 rounded-full border border-emerald-400/20">
              High Growth Fit
            </span>
            <h3 className="mt-3 text-xl font-bold text-white leading-tight">
              Ready for Interactive Conversion
            </h3>
            <p className="mt-2 text-xs text-white/70 leading-relaxed">
              Based on your selection ({options[selectedIdx]}), embedding a dynamic tool will
              capture up to 3x more qualified leads.
            </p>
          </div>

          <div className="space-y-2 mt-4">
            <button
              type="button"
              onClick={() => setStep("q1")}
              className="flex items-center justify-center gap-2 w-full text-xs font-semibold py-2.5 rounded-lg border border-white/20 hover:bg-white/10 text-white transition-all"
            >
              Re-take Quiz
            </button>
          </div>
        </div>
      )}
    </article>
  );
}

export function OutputShowcase() {
  return (
    <section className="showcase-shell" aria-labelledby="showcase-title">
      <div className="showcase-grid" aria-hidden="true" />

      <div className="showcase-wing showcase-wing-left">
        <span>MADE</span>
        <span>TO BE</span>
      </div>

      <div className="showcase-stage">
        <AuditCard />
        <CalculatorCard />
        <QuizCard />
      </div>

      <div className="showcase-wing showcase-wing-right">
        <span>USED.</span>
        <p className="showcase-serif">
          Calculators, audits, and quizzes—curated around the questions your customers already have.
        </p>
      </div>

      <h2 id="showcase-title" className="sr-only">
        Curated Magnitai output examples
      </h2>
    </section>
  );
}
