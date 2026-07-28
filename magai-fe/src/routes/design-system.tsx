import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/magnitai/AppShell";
import { DesignSystemOverview } from "@/components/magnitai/DesignSystemOverview";

export const Route = createFileRoute("/design-system")({
  head: () => ({ meta: [{ title: "Design System · Magnitai" }] }),
  component: DesignSystem,
});

function DesignSystem() {
  return (
    <AppShell activeSection="design-system">
      <DesignSystemOverview />
    </AppShell>
  );
}
