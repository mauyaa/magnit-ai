/**
 * Plan gating, in one place.
 *
 * Every screen that has to know what the plan includes asks these helpers
 * instead of reading a subscription object and deciding for itself. That is the
 * whole point: the rules used to be re-derived in the sidebar, the settings page
 * and the pricing page, and the three disagreed about what a free workspace
 * could do.
 *
 * The server is still the authority. Nothing here prevents an action — it
 * decides what to *show*, so a customer sees a locked feature and a way to
 * unlock it rather than a button that 402s when they press it.
 */

import { Link } from "@tanstack/react-router";
import { Lock, Sparkles } from "lucide-react";
import type { ReactNode } from "react";

import { useEntitlements, type PlanFeature } from "./api";

/** Whether the current plan includes a capability. False while loading. */
export function useFeature(feature: PlanFeature): boolean {
  const { data } = useEntitlements();
  return data?.features.includes(feature) ?? false;
}

/**
 * Gating state for one capability, resolved once.
 *
 * `loading` is separate from `allowed` on purpose. Treating "not yet known" as
 * "not allowed" is what makes a paid feature flash a lock on every page load —
 * the caller can render nothing until the answer arrives instead.
 */
export function useGate(feature: PlanFeature) {
  const { data, isLoading } = useEntitlements();
  return {
    loading: isLoading,
    allowed: data?.features.includes(feature) ?? false,
    plan: data?.plan,
  };
}

export function usePlanUsage() {
  const { data } = useEntitlements();
  return data;
}

const FEATURE_COPY: Record<PlanFeature, { title: string; body: string }> = {
  lead_capture: {
    title: "Capture leads on a paid plan",
    body: "Publishing a tool and collecting the details it captures is included from Studio up.",
  },
  lead_notifications: {
    title: "Get told when a lead arrives",
    body: "Email alerts the moment someone leaves their details.",
  },
  lead_pipeline: {
    title: "Track what you did about a lead",
    body: "Statuses, tags and notes so a lead list becomes something you work from.",
  },
  csv_export: {
    title: "Export your leads",
    body: "Download everything you have captured, with your own statuses and tags.",
  },
  webhook_delivery: {
    title: "Send leads anywhere",
    body: "Signed webhooks into Zapier, Make, n8n or your own endpoint.",
  },
  crm_integrations: {
    title: "Connect your CRM",
    body: "Push every lead straight into HubSpot, Salesforce, Mailchimp or a spreadsheet.",
  },
  brand_kit: {
    title: "Set a house style",
    body: "Pin the colours, type and shape every tool you build should use.",
  },
  outcome_editor: {
    title: "Write your own results",
    body: "Rename the score bands, rewrite the advice, and choose where the final button goes.",
  },
  question_editor: {
    title: "Edit the questions",
    body: "Reword, reorder and rescore the flow your visitors answer.",
  },
  advanced_analytics: {
    title: "See where leads come from",
    body: "Attribution, drop-off by step, and a longer history to compare against.",
  },
  self_healing: {
    title: "Keep tools working by themselves",
    body: "Automatic repair when your site rebrands or a deployment goes down.",
  },
  priority_support: {
    title: "Priority support",
    body: "Your questions go to the front of the queue.",
  },
  custom_domains: {
    title: "Use your own domain",
    body: "Connect a branded hostname to any published tool and verify its DNS setup.",
  },
  api_access: {
    title: "Connect through the API",
    body: "Create revocable workspace keys for your own systems and reporting workflows.",
  },
};

/**
 * The standard "your plan doesn't include this" panel.
 *
 * Says what the feature does before it says it is locked — a lock icon over an
 * unexplained feature name is an advert, not an explanation.
 */
export function UpgradeNotice({
  feature,
  compact = false,
}: {
  feature: PlanFeature;
  compact?: boolean;
}) {
  const { plan } = useGate(feature);
  const copy = FEATURE_COPY[feature];

  if (compact) {
    return (
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-lg border border-dashed border-border-strong bg-n-50 px-3.5 py-3 text-sm">
        <Lock className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
        <span className="text-muted-foreground">{copy.body}</span>
        <Link
          to="/dashboard/settings"
          hash="billing"
          className="font-medium text-foreground underline underline-offset-2"
        >
          Upgrade
        </Link>
      </div>
    );
  }

  return (
    <div className="surface px-6 py-12 text-center">
      <span className="mx-auto grid size-11 place-items-center rounded-xl bg-secondary">
        <Sparkles className="size-5 text-foreground" aria-hidden="true" />
      </span>
      <h2 className="mt-4 text-lg font-medium text-foreground">{copy.title}</h2>
      <p className="mx-auto mt-1.5 max-w-sm text-sm leading-6 text-muted-foreground">{copy.body}</p>
      {plan && <p className="mt-3 text-xs text-muted-foreground">You are on {plan.name}.</p>}
      <Link to="/dashboard/settings" hash="billing" className="btn btn-primary mt-6 h-9 text-sm">
        See plans
      </Link>
    </div>
  );
}

/**
 * Render `children` when the plan allows it, an upgrade prompt when it does not.
 *
 * Renders nothing at all while the answer is still loading, so a paid feature
 * never flashes a lock on the way in.
 */
export function PlanGate({
  feature,
  compact,
  children,
  fallback,
}: {
  feature: PlanFeature;
  compact?: boolean;
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const { loading, allowed } = useGate(feature);
  if (loading) return null;
  if (allowed) return <>{children}</>;
  return <>{fallback ?? <UpgradeNotice feature={feature} compact={compact} />}</>;
}

/**
 * How much of an allowance has been spent, in words.
 *
 * One function because a plan with a zero allowance still has usage — a tool
 * bought outright sits on the free plan, whose live-tool cap is zero — and
 * "1 of 0" is arithmetic, not information. Every surface that prints a usage
 * ratio goes through here, so that case can only be got wrong once.
 */
export function formatUsage(used: number, limit: number, separator = "of"): string {
  if (limit <= 0) {
    return used.toLocaleString();
  }
  return `${used.toLocaleString()} ${separator} ${limit.toLocaleString()}`;
}

/**
 * A used-of-allowed bar.
 *
 * Turns amber at 80% and red once spent, because a number nobody is watching is
 * a number that surprises someone mid-build.
 */
export function UsageMeter({
  label,
  used,
  limit,
  unit,
  inverse = false,
}: {
  label: string;
  used: number;
  limit: number;
  unit?: string;
  inverse?: boolean;
}) {
  const unlimited = limit <= 0;
  const ratio = unlimited ? 0 : Math.min(1, used / limit);
  const tone =
    !unlimited && ratio >= 1
      ? "bg-destructive"
      : !unlimited && ratio >= 0.8
        ? "bg-warning"
        : inverse
          ? "bg-brand"
          : "bg-foreground";

  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className={`text-xs ${inverse ? "text-inverse-subtle" : "text-muted-foreground"}`}>
          {label}
        </span>
        <span
          className={`tabular text-xs font-medium ${
            inverse ? "text-inverse-foreground" : "text-foreground"
          }`}
        >
          {formatUsage(used, limit, "/")}
          {unit ? ` ${unit}` : ""}
        </span>
      </div>
      <div
        className={`mt-1.5 h-1 overflow-hidden rounded-full ${
          inverse ? "bg-inverse-border" : "bg-n-200"
        }`}
      >
        <span
          className={`block h-full rounded-full transition-[width] ${tone}`}
          style={{ width: `${Math.max(ratio > 0 ? 3 : 0, ratio * 100)}%` }}
        />
      </div>
    </div>
  );
}

/** Money, from the integer cents the API returns. */
export function formatPrice(cents: number, currency = "usd"): string {
  if (cents === 0) return "$0";
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: currency.toUpperCase(),
    // Plans are whole dollars; "$99.00" reads like a form field rather than a
    // price, and every reference pricing page drops the cents.
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(cents / 100);
}
