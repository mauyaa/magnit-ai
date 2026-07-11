import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/magnitai/AppShell";
import { LegalPage } from "@/components/magnitai/LegalPage";

export const Route = createFileRoute("/terms")({
  head: () => ({ meta: [{ title: "Terms of Service · Magnitai" }] }),
  component: Terms,
});

function Terms() {
  return (
    <AppShell activeSection="landing">
      <LegalPage title="Terms of service" updated="July 5, 2026">
        <section>
          <h2>Using Magnitai</h2>
          <p>
            You may use Magnitai to create and operate widgets for websites you own or are
            authorized to manage. You are responsible for the content, claims, and data collection
            within your published experiences.
          </p>
        </section>
        <section>
          <h2>Service operation</h2>
          <p>
            Magnitai may update generated widgets to maintain compatibility, accessibility, and
            security. Material service changes will be communicated through the product.
          </p>
        </section>
        <section>
          <h2>Acceptable use</h2>
          <p>
            Do not use the service to distribute malware, mislead visitors, violate privacy rights,
            or interfere with another system. Access may be limited when required to protect users
            or the platform.
          </p>
        </section>
      </LegalPage>
    </AppShell>
  );
}
