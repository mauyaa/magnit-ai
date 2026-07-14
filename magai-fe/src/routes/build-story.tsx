import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/magnitai/AppShell";
import { TransparencyDashboard } from "@/components/magnitai/TransparencyDashboard";

export const Route = createFileRoute("/build-story")({
  head: () => ({ meta: [{ title: "Live AI Build · Magnitai" }] }),
  component: BuildStory,
});

function BuildStory() {
  return (
    <AppShell activeSection="build-story">
      <TransparencyDashboard />
    </AppShell>
  );
}
