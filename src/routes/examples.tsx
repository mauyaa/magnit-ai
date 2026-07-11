import { useEffect, useRef, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2 } from "lucide-react";
import { AppShell } from "@/components/magnitai/AppShell";
import { WidgetGallery } from "@/components/magnitai/WidgetGallery";

const widgetNames: Record<string, string> = {
  "roi-calc": "ROI Calculator",
  "brand-quiz": "Product Recommender",
  "seo-audit": "Website Health Auditor",
  "pricing-quote": "Pricing Configurator",
  "onboard-flow": "Onboarding Companion",
};

export const Route = createFileRoute("/examples")({
  head: () => ({ meta: [{ title: "Interactive Widget Examples · Magnitai" }] }),
  component: Examples,
});

function Examples() {
  const navigate = useNavigate();
  const [selectedWidget, setSelectedWidget] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    },
    [],
  );

  const handleSelect = (id: string) => {
    setSelectedWidget(widgetNames[id] ?? "Widget");
    timerRef.current = window.setTimeout(() => {
      navigate({ to: "/build-story" });
    }, 650);
  };

  return (
    <AppShell activeSection="gallery">
      <AnimatePresence>
        {selectedWidget && (
          <motion.div
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            transition={{ duration: 0.16 }}
            className="fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 items-center gap-3 rounded-2xl border border-border bg-card px-5 py-3.5 text-sm font-semibold shadow-xl"
            role="status"
            aria-live="polite"
          >
            <CheckCircle2 className="size-4 shrink-0 text-success" />
            Opening <span className="text-primary">{selectedWidget}</span> build story…
          </motion.div>
        )}
      </AnimatePresence>
      <WidgetGallery onSelectWidget={handleSelect} />
    </AppShell>
  );
}
