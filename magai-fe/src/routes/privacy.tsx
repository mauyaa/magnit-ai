import { createFileRoute } from "@tanstack/react-router";

import { AppShell } from "@/components/magnitai/AppShell";
import { LegalPage } from "@/components/magnitai/LegalPage";

const CONTENTS = [
  { id: "information", label: "Information we process" },
  { id: "use", label: "How information is used" },
  { id: "lead-data", label: "Visitor and lead data" },
  { id: "providers", label: "Service providers" },
  { id: "retention", label: "Retention and control" },
  { id: "security", label: "Security and changes" },
];

export const Route = createFileRoute("/privacy")({
  head: () => ({ meta: [{ title: "Privacy Policy · Magnitai" }] }),
  component: Privacy,
});

function Privacy() {
  return (
    <AppShell activeSection="landing">
      <LegalPage
        title="Privacy policy"
        updated="July 5, 2026"
        summary="This policy explains the information Magnitai needs to build and operate your interactive tools, how that information is used, and the choices available to you."
        contents={CONTENTS}
        related={{ label: "Read the terms", to: "/terms" }}
      >
        <section id="information">
          <h2>1. Information we process</h2>
          <p>
            Magnitai processes the website address, creation brief, brand configuration and account
            details you provide. When the service reads a public website, it processes the public
            page content and visual signals needed to propose and maintain an interactive tool.
          </p>
          <h3>Operational information</h3>
          <p>
            We also process device, request and service-event information needed to authenticate
            users, prevent abuse, diagnose failures and keep published tools available.
          </p>
        </section>

        <section id="use">
          <h2>2. How information is used</h2>
          <p>
            Information is used to generate tools, host and monitor published experiences, deliver
            analytics, support account access, process subscriptions, prevent abuse and improve the
            service. Magnitai does not sell personal information.
          </p>
        </section>

        <section id="lead-data">
          <h2>3. Visitor and lead data</h2>
          <p>
            A published tool may collect answers and contact details configured by its customer.
            That customer determines the questions shown to visitors and is responsible for giving
            any notice or obtaining any consent required for that collection.
          </p>
          <p>
            Magnitai processes this information for the customer so it can be displayed, exported or
            delivered to a connected service. It is not used to advertise to those visitors.
          </p>
        </section>

        <section id="providers">
          <h2>4. Service providers</h2>
          <p>
            Magnitai may use infrastructure, authentication, payment, email and monitoring providers
            to operate the service. Providers receive only the information needed for their role and
            are expected to protect it.
          </p>
        </section>

        <section id="retention">
          <h2>5. Retention and control</h2>
          <p>
            Customers may request access, correction, export or deletion of their account data.
            Operational and security records are retained only for legitimate service, legal and
            abuse-prevention needs. Some information may remain in time-limited backups before it is
            fully removed.
          </p>
        </section>

        <section id="security">
          <h2>6. Security and policy changes</h2>
          <p>
            Magnitai uses access controls, encryption in transit and service monitoring to protect
            information. No internet service can promise absolute security, so material incidents
            are handled and communicated in line with applicable obligations.
          </p>
          <p>
            Material changes to this policy will be identified by a new effective date and, when
            appropriate, communicated through the product.
          </p>
        </section>
      </LegalPage>
    </AppShell>
  );
}
