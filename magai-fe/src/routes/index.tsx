import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/magnitai/AppShell";
import { LandingPage } from "@/components/magnitai/LandingPage";
import { WaitlistLanding } from "@/components/magnitai/WaitlistLanding";

const isLive ="false";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Magnitai · Self-Healing AI Interactive Widgets" },
      {
        name: "description",
        content:
          "Magnitai builds, deploys, and self-heals interactive widgets for small businesses.",
      },
      { property: "og:title", content: "Magnitai · Self-Healing AI Interactive Widgets" },
      {
        property: "og:description",
        content:
          "Magnitai builds, deploys, and self-heals interactive widgets for small businesses.",
      },
    ],
  }),
  component: Index,
});

function Index() {
  if (isLive) {
    return (
      <AppShell activeSection="landing">
        <LandingPage />
      </AppShell>
    );
  }

  return <WaitlistLanding />;
}
