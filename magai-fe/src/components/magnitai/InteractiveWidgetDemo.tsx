import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { RefreshCw } from "lucide-react";
import { SliderField } from "@/components/magnitai/ui/SliderField";

export function InteractiveWidgetDemo() {
  const [visitors, setVisitors] = useState<number>(3500);
  const [conversionBoost, setConversionBoost] = useState<number>(3.8);
  const [avgOrder, setAvgOrder] = useState<number>(120);
  const [isSelfHealing, setIsSelfHealing] = useState<boolean>(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const calculatedRevenue = Math.round(visitors * (conversionBoost / 100) * avgOrder * 12);

  const triggerSelfHealSimulation = () => {
    setIsSelfHealing(true);
    setTimeout(() => {
      setIsSelfHealing(false);
    }, 2000);
  };

  return (
    <div className="relative w-full h-full flex flex-col justify-between transition-all text-foreground">
      {/* Widget Header */}
      <div className="mb-7 flex flex-col items-start gap-4 border-b border-foreground/5 pb-6 sm:mb-10 sm:flex-row sm:items-center sm:justify-between sm:pb-8">
        <div className="flex items-center gap-4">
          <div className="font-mono text-xs font-bold tracking-widest text-primary border-2 border-foreground px-2 py-1 bg-foreground text-background">
            [ CALC ]
          </div>
          <div>
            <h4 className="text-xl font-bold tracking-tight font-heading">ROI Calculator</h4>
            <p className="eyebrow mt-1">
              Autonomous Component
            </p>
          </div>
        </div>

        <div className="flex w-full items-center justify-between gap-2 sm:w-auto sm:justify-start sm:gap-3">
          <AnimatePresence mode="wait">
            {isSelfHealing ? (
              <motion.div
                key="healing"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                className="flex items-center gap-2 px-4 py-2 border-2 border-foreground bg-card text-primary"
              >
                <RefreshCw className="size-3.5 animate-spin" />
                <span className="text-[11px] font-bold tracking-wider uppercase">
                  Self-Healing...
                </span>
              </motion.div>
            ) : (
              <motion.div
                key="guard"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center gap-2 border-2 border-foreground bg-card px-3 py-2 text-foreground sm:px-4"
              >
                <span className="size-1.5 rounded-full bg-success animate-pulse" />
                <span className="text-[11px] font-bold tracking-wider uppercase">Guard Active</span>
              </motion.div>
            )}
          </AnimatePresence>
          <button
            onClick={triggerSelfHealSimulation}
            className="p-2 text-muted-foreground hover:text-foreground hover:bg-foreground/5 transition-colors rounded-full"
            title="Trigger Self Heal"
            aria-label="Simulate self-healing process"
          >
            <RefreshCw className="size-4" />
          </button>
        </div>
      </div>

      <div className="flex flex-col gap-10 mt-6">
        {/* Inputs */}
        <div className="space-y-8">
          <SliderField
            id="visitors"
            label="Monthly Visitors"
            value={visitors}
            displayValue={visitors.toLocaleString()}
            min={500}
            max={25000}
            step={250}
            onChange={(val) => setVisitors(val)}
          />

          <SliderField
            id="conversion"
            label="Conversion Boost"
            value={conversionBoost}
            displayValue={`+${conversionBoost}%`}
            min={1}
            max={10}
            step={0.2}
            onChange={(val) => setConversionBoost(val)}
          />

          <SliderField
            id="aov"
            label="Avg Order Value"
            value={avgOrder}
            displayValue={`$${avgOrder}`}
            min={20}
            max={500}
            step={10}
            onChange={(val) => setAvgOrder(val)}
          />
        </div>

        {/* Output Preview */}
        <div className="relative w-full flex flex-col justify-center p-8 md:p-10 bg-card border-2 border-foreground overflow-hidden group mt-4 transition-all hover:shadow-[8px_8px_0_0_var(--foreground)]">
          <div className="relative z-10 w-full flex flex-col items-center text-center">
            <div className="flex items-center justify-center gap-2 mb-6">
              <span className="text-[11px] font-mono tracking-widest text-foreground uppercase">
                Estimated Annual Lift
              </span>
            </div>

            {mounted && (
              <motion.div
                key={calculatedRevenue}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-5xl md:text-6xl font-black font-mono tracking-tighter text-foreground mb-8"
              >
                +${calculatedRevenue.toLocaleString()}
              </motion.div>
            )}

            <button className="flex items-center justify-center w-full max-w-sm h-12 bg-foreground text-background font-bold text-sm border-2 border-foreground hover:bg-card hover:text-foreground hover:shadow-[4px_4px_0_0_var(--foreground)] transition-all duration-300 px-6 active:scale-[0.98]">
              Claim Your Audit
            </button>
          </div>
        </div>
      </div>

      <div className="mt-12 pt-6 border-t border-foreground/5 flex items-center justify-between text-[11px] text-muted-foreground uppercase tracking-widest font-bold">
        <div className="flex items-center gap-2">
          <span>100% Real-time sync</span>
        </div>
      </div>
    </div>
  );
}
