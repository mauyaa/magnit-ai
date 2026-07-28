import { createFileRoute } from "@tanstack/react-router";
import { LiveBuildStory } from "@/components/magnitai/LiveBuildStory";
import { RequireAuth } from "@/components/magnitai/RequireAuth";
import { WorkspaceShell } from "@/components/magnitai/shell/WorkspaceShell";

export const Route = createFileRoute("/build-story/$widgetId")({
  head: () => ({ meta: [{ title: "Live AI Build · Magnitai" }] }),
  // Streams progress for a specific widget, so it needs the owner's session.
  component: () => (
    <RequireAuth>
      <BuildStory />
    </RequireAuth>
  ),
});

function BuildStory() {
  const { widgetId } = Route.useParams();
  return (
    <WorkspaceShell
      breadcrumb={[{ label: "Overview", to: "/dashboard" }, { label: "Building tool" }]}
    >
      <LiveBuildStory widgetId={widgetId} />
    </WorkspaceShell>
  );
}
