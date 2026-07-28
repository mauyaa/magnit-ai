import { createFileRoute } from "@tanstack/react-router";

import { AppShell } from "@/components/magnitai/AppShell";
import { WidgetGallery } from "@/components/magnitai/WidgetGallery";

export const Route = createFileRoute("/examples")({
  head: () => ({ meta: [{ title: "What we build · Magnitai" }] }),
  component: Examples,
});

// The gallery used to intercept clicks, show an "Opening … build story…" toast,
// then navigate to /how-it-works after a timer — a confirmation for something
// that never happened. Its links now go where they say they go.
function Examples() {
  return (
    <AppShell activeSection="gallery">
      <WidgetGallery />
    </AppShell>
  );
}
