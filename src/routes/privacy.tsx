import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/magnitai/AppShell";
import { LegalPage } from "@/components/magnitai/LegalPage";

export const Route = createFileRoute("/privacy")({
  head: () => ({ meta: [{ title: "Privacy Policy · Magnitai" }] }),
  component: Privacy,
});

function Privacy() {
  return (
    <AppShell activeSection="landing">
      <LegalPage title="Privacy policy" updated="July 5, 2026">
        <section>
          <h2>Information we process</h2>
          <p>
            Magnitai processes the website URL, widget brief, and configuration details you provide
            to create and maintain your interactive experience. We only collect operational data
            needed to provide, secure, and improve the service.
          </p>
        </section>
        <section>
          <h2>How information is used</h2>
          <p>
            Data is used to generate widgets, monitor their health, deliver analytics, prevent
            abuse, and provide support. Magnitai does not sell personal information.
          </p>
        </section>
        <section>
          <h2>Retention and control</h2>
          <p>
            Customers may request access, correction, export, or deletion of their account data.
            Operational records are retained only for legitimate security and service needs.
          </p>
        </section>
      </LegalPage>
    </AppShell>
  );
}
