import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/magnitai/AppShell";
import { PricingPage } from "@/components/magnitai/PricingPage";

export const Route = createFileRoute("/pricing")({
  head: () => ({ meta: [{ title: "Pricing · Magnitai" }] }),
  component: PricingRoute,
});

function PricingRoute() {
  return (
    <AppShell activeSection="pricing">
      <PricingPage />
    </AppShell>
  );
}
