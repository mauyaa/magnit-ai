import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/magnitai/AppShell";
import { LiveBuildStory } from "@/components/magnitai/LiveBuildStory";

export const Route = createFileRoute("/build-story/$widgetId")({
  head: () => ({ meta: [{ title: "Live AI Build · Magnitai" }] }),
  component: BuildStory,
});

function BuildStory() {
  const { widgetId } = Route.useParams();
  return (
    <AppShell activeSection="build-story">
      <LiveBuildStory widgetId={widgetId} />
    </AppShell>
  );
}
