import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, BookOpen, LifeBuoy, Mail, Rocket, Wrench } from "lucide-react";

import { RequireAuth } from "@/components/magnitai/RequireAuth";
import { PageHeader } from "@/components/magnitai/shell/PageHeader";
import { WorkspaceShell } from "@/components/magnitai/shell/WorkspaceShell";
import { useEntitlements } from "@/lib/api";
import { formatUsage, useFeature } from "@/lib/plan";

export const Route = createFileRoute("/dashboard/help")({
  head: () => ({ meta: [{ title: "Help · Magnitai" }] }),
  component: () => (
    <RequireAuth>
      <Help />
    </RequireAuth>
  ),
});

/**
 * Answers to the questions the product actually generates.
 *
 * Deliberately not a link farm to documentation that does not exist yet. Every
 * entry either explains something in one paragraph or points at a screen inside
 * this app — a help centre full of dead links is worse than no help centre.
 */
const TOPICS: Array<{
  icon: typeof Rocket;
  title: string;
  body: string;
  to?: string;
  linkLabel?: string;
}> = [
  {
    icon: Rocket,
    title: "Getting your first tool live",
    body: "Enter your website, choose one of the two directions Magnitai proposes, then paste the embed snippet onto the page it belongs on. The launch checklist on each tool tells you what is still missing.",
    to: "/build",
    linkLabel: "Build a tool",
  },
  {
    icon: Wrench,
    title: "Changing the questions or the result",
    body: "Open a tool and use the Questions and Results tabs. Saving publishes to the live tool straight away — there is no rebuild, and no need to touch the embed snippet again.",
    to: "/dashboard",
    linkLabel: "Open your tools",
  },
  {
    icon: Mail,
    title: "Where your leads go",
    body: "Every lead is stored here and emailed to you. Connect a CRM, a mailing list, a spreadsheet or your own endpoint to have it delivered onward automatically.",
    to: "/dashboard/integrations",
    linkLabel: "Set up delivery",
  },
  {
    icon: BookOpen,
    title: "Why a tool changed on its own",
    body: "Magnitai re-checks each live tool every few hours. If your website rebrands or a deployment stops answering, it repairs the tool and records what it did on that tool's Activity tab.",
  },
];

function Help() {
  const { data: entitlements } = useEntitlements();
  const priority = useFeature("priority_support");

  return (
    <WorkspaceShell breadcrumb={[{ label: "Help" }]}>
      <PageHeader
        title="Help and support"
        description="How the parts fit together, and how to reach a person when they don't."
      />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="grid gap-4 sm:grid-cols-2">
          {TOPICS.map((topic) => {
            const Icon = topic.icon;
            return (
              <article key={topic.title} className="surface flex flex-col p-5">
                <span className="grid size-9 place-items-center rounded-lg bg-secondary">
                  <Icon className="size-4 text-foreground" aria-hidden="true" />
                </span>
                <h2 className="mt-3.5 text-base font-medium text-foreground">{topic.title}</h2>
                <p className="mt-1.5 flex-1 text-sm leading-6 text-muted-foreground">
                  {topic.body}
                </p>
                {topic.to && (
                  <Link
                    to={topic.to}
                    className="mt-4 inline-flex w-fit items-center gap-1.5 text-sm font-medium text-foreground hover:underline"
                  >
                    {topic.linkLabel}
                    <ArrowRight className="size-3.5" aria-hidden="true" />
                  </Link>
                )}
              </article>
            );
          })}
        </div>

        <aside className="space-y-4">
          <section className="surface p-5">
            <span className="grid size-9 place-items-center rounded-lg bg-secondary">
              <LifeBuoy className="size-4 text-foreground" aria-hidden="true" />
            </span>
            <h2 className="mt-3.5 text-base font-medium text-foreground">Talk to us</h2>
            <p className="mt-1.5 text-sm leading-6 text-muted-foreground">
              {priority
                ? "Your plan includes priority support, so your message goes to the front of the queue."
                : "Send us what you are stuck on and we will come back to you."}
            </p>
            <a
              href="mailto:support@magnitai.com"
              className="btn btn-primary mt-4 h-9 w-full text-sm"
            >
              <Mail className="size-4" aria-hidden="true" />
              Email support
            </a>
          </section>

          {entitlements && (
            <section className="surface p-5">
              <h2 className="text-sm font-medium text-foreground">Your workspace</h2>
              <dl className="mt-3 space-y-2 text-sm">
                {(
                  [
                    ["Plan", entitlements.plan.name],
                    [
                      "Live tools",
                      formatUsage(entitlements.usage.live_tools, entitlements.plan.live_tool_limit),
                    ],
                    [
                      "Builds this month",
                      formatUsage(
                        entitlements.usage.builds_this_period,
                        entitlements.plan.monthly_build_limit,
                      ),
                    ],
                  ] as const
                ).map(([label, value]) => (
                  <div key={label} className="flex items-baseline justify-between gap-4">
                    <dt className="text-muted-foreground">{label}</dt>
                    <dd className="tabular font-medium text-foreground">{value}</dd>
                  </div>
                ))}
              </dl>
              <p className="mt-3 text-xs leading-5 text-muted-foreground">
                Quote your plan when you write in — it saves a round trip.
              </p>
            </section>
          )}
        </aside>
      </div>
    </WorkspaceShell>
  );
}
