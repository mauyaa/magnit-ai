import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { AppShell } from "@/components/magnitai/AppShell";
import { CheckoutFlow } from "@/components/magnitai/CheckoutFlow";

export const Route = createFileRoute("/build")({
  head: () => ({ meta: [{ title: "Build a Self-Healing Widget · Magnitai" }] }),
  component: Build,
});

function Build() {
  const navigate = useNavigate();

  return (
    <AppShell activeSection="checkout">
      <CheckoutFlow
        onBuildStart={(widgetId) =>
          navigate({ to: "/build-story/$widgetId", params: { widgetId }, replace: true })
        }
        onBack={() => navigate({ to: "/" })}
      />
    </AppShell>
  );
}
