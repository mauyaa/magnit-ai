import { createFileRoute } from "@tanstack/react-router";

import { AppShell } from "@/components/magnitai/AppShell";
import { LegalPage } from "@/components/magnitai/LegalPage";

const CONTENTS = [
  { id: "using-magnitai", label: "Using Magnitai" },
  { id: "accounts", label: "Accounts and access" },
  { id: "subscriptions", label: "Subscriptions" },
  { id: "content", label: "Content and data" },
  { id: "operation", label: "Service operation" },
  { id: "acceptable-use", label: "Acceptable use" },
  { id: "ending", label: "Ending the service" },
];

export const Route = createFileRoute("/terms")({
  head: () => ({ meta: [{ title: "Terms of Service · Magnitai" }] }),
  component: Terms,
});

function Terms() {
  return (
    <AppShell activeSection="landing">
      <LegalPage
        title="Terms of service"
        updated="July 5, 2026"
        summary="These terms govern access to Magnitai, the tools it generates and the hosted services used to publish them."
        contents={CONTENTS}
        related={{ label: "Read the privacy policy", to: "/privacy" }}
      >
        <section id="using-magnitai">
          <h2>1. Using Magnitai</h2>
          <p>
            You may use Magnitai to create and operate tools for websites you own or are authorised
            to manage. You are responsible for the content, claims and data collection within your
            published experiences.
          </p>
        </section>

        <section id="accounts">
          <h2>2. Accounts and access</h2>
          <p>
            Keep account credentials accurate and secure. You are responsible for activity carried
            out through your workspace except where unauthorised access results from a failure of
            the Magnitai service itself.
          </p>
        </section>

        <section id="subscriptions">
          <h2>3. Subscriptions and payment</h2>
          <p>
            Paid plans renew for the period shown at purchase until cancelled. Prices, plan limits
            and included capabilities are shown before checkout. A cancellation takes effect at the
            end of the current paid period unless applicable law requires otherwise.
          </p>
        </section>

        <section id="content">
          <h2>4. Content, generated tools and data</h2>
          <p>
            You retain rights in the business content and visitor data you provide. You give
            Magnitai permission to process that material only as needed to create, host, monitor and
            support the service.
          </p>
          <p>
            Generated output should be reviewed before publication. You remain responsible for the
            accuracy, legality and suitability of claims shown to visitors.
          </p>
        </section>

        <section id="operation">
          <h2>5. Service operation</h2>
          <p>
            Magnitai may update generated tools to maintain compatibility, accessibility, security
            and alignment with the source brand. Material service changes will be communicated
            through the product when practical.
          </p>
        </section>

        <section id="acceptable-use">
          <h2>6. Acceptable use</h2>
          <p>Do not use the service to:</p>
          <ul>
            <li>distribute malware or interfere with another service;</li>
            <li>mislead visitors or impersonate a person or business;</li>
            <li>collect information without the notices or permission the law requires;</li>
            <li>violate intellectual-property, privacy or other legal rights; or</li>
            <li>attempt to bypass security or usage limits.</li>
          </ul>
        </section>

        <section id="ending">
          <h2>7. Ending or suspending access</h2>
          <p>
            You may cancel a paid plan from workspace settings. Magnitai may limit access when
            reasonably needed to address abuse, security risk, non-payment or a material violation
            of these terms, and will try to limit the interruption to what is necessary.
          </p>
        </section>
      </LegalPage>
    </AppShell>
  );
}
