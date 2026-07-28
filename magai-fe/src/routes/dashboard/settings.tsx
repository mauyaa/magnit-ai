import { createFileRoute } from "@tanstack/react-router";

import { RequireAuth } from "@/components/magnitai/RequireAuth";
import { SettingsExperience } from "@/components/magnitai/settings/SettingsExperience";
import { WorkspaceShell } from "@/components/magnitai/shell/WorkspaceShell";

export const Route = createFileRoute("/dashboard/settings")({
  head: () => ({ meta: [{ title: "Settings · Magnitai" }] }),
  component: () => (
    <RequireAuth>
      <WorkspaceShell breadcrumb={[{ label: "Settings" }]}>
        <SettingsExperience />
      </WorkspaceShell>
    </RequireAuth>
  ),
});
