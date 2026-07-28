import { createFileRoute } from "@tanstack/react-router";

import { AppShell } from "@/components/magnitai/AppShell";
import { LandingPage } from "@/components/magnitai/LandingPage";

const DESCRIPTION =
  "Give Magnitai your website address. It builds a calculator, quiz, or audit in your own brand, hosts it, and keeps it in sync as your site changes.";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Magnitai · Interactive tools in your brand" },
      { name: "description", content: DESCRIPTION },
      { property: "og:title", content: "Magnitai · Interactive tools in your brand" },
      { property: "og:description", content: DESCRIPTION },
    ],
  }),
  component: Index,
});

function Index() {
  // This used to branch on `const isLive = "false"` — a non-empty string, so the
  // waitlist branch was unreachable and the landing page shipped regardless.
  // Rendering it directly keeps the behaviour and drops the flag that implied
  // a switch nobody could actually throw. WaitlistLanding is still on disk if
  // the pre-launch page is ever wanted back.
  return (
    <AppShell activeSection="landing">
      <LandingPage />
    </AppShell>
  );
}
