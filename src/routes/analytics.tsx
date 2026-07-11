import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/magnitai/AppShell";
import { OwnerAnalyticsDashboard } from "@/components/magnitai/OwnerAnalyticsDashboard";

export const Route = createFileRoute("/analytics")({
  head: () => ({ meta: [{ title: "Analytics & Self-Healing · Magnitai" }] }),
  component: Analytics,
});

function Analytics() {
  return (
    <AppShell activeSection="analytics">
      <OwnerAnalyticsDashboard />
    </AppShell>
  );
}
