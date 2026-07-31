import { createFileRoute } from "@tanstack/react-router";

import { AppShell } from "@/components/magnitai/AppShell";
import { LandingPage } from "@/components/magnitai/LandingPage";

const DESCRIPTION =
  "Turn more website visitors into qualified leads. Magnitai builds a branded calculator, quiz, or audit from your existing website and gives you one embed to publish it.";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Magnitai · Turn website traffic into qualified leads" },
      { name: "description", content: DESCRIPTION },
      { property: "og:title", content: "Magnitai · Turn website traffic into qualified leads" },
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
