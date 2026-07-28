import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/magnitai/AppShell";
import { TransparencyDashboard } from "@/components/magnitai/TransparencyDashboard";

export const Route = createFileRoute("/how-it-works")({
  head: () => ({ meta: [{ title: "How Magnitai Works · Magnitai" }] }),
  component: HowItWorks,
});

function HowItWorks() {
  return (
    <AppShell activeSection="transparency">
      <TransparencyDashboard />
    </AppShell>
  );
}
