import { AlertCircle, Check, Clock, Loader2, MinusCircle, RefreshCw } from "lucide-react";

import { useRetryLeadDelivery, type LeadDelivery } from "@/lib/api";

/**
 * Where this lead actually reached.
 *
 * "We captured it" and "your CRM has it" are different claims, and a business
 * that relies on the second one deserves to see which is true rather than
 * assume. Automatic retries are bounded so a dead endpoint does not run
 * forever, which leaves exactly one thing a person has to do — and this is
 * where they do it.
 */
const CHANNEL_LABEL: Record<LeadDelivery["channel"], string> = {
  owner_email: "Email alert",
  webhook: "Your webhook",
  integration: "Connected app",
};

function StatusIcon({ status }: { status: LeadDelivery["status"] }) {
  if (status === "delivered") return <Check className="size-3.5 text-success" aria-hidden="true" />;
  if (status === "failed")
    return <AlertCircle className="size-3.5 text-destructive" aria-hidden="true" />;
  if (status === "skipped")
    return <MinusCircle className="size-3.5 text-muted-foreground" aria-hidden="true" />;
  return <Clock className="size-3.5 text-muted-foreground" aria-hidden="true" />;
}

function statusText(delivery: LeadDelivery): string {
  switch (delivery.status) {
    case "delivered":
      return "Delivered";
    case "skipped":
      return "Turned off";
    case "failed":
      return `Failed after ${delivery.attempts} attempts`;
    default:
      return delivery.attempts > 0 ? "Retrying" : "Sending";
  }
}

export function LeadDeliveryPanel({
  leadId,
  deliveries,
}: {
  leadId: string;
  deliveries: LeadDelivery[];
}) {
  const retry = useRetryLeadDelivery();

  // Nothing to report is not the same as nothing to say, but a tool with no
  // destinations configured has a different screen for that. Stay quiet here.
  if (deliveries.length === 0) return null;

  return (
    <section className="surface p-5">
      <h2 className="text-base font-medium text-foreground">Delivered to</h2>
      <ul className="mt-3 divide-y divide-border">
        {deliveries.map((delivery) => (
          <li key={delivery.id} className="flex items-start gap-2.5 py-2.5 first:pt-0 last:pb-0">
            <span className="mt-0.5 shrink-0">
              <StatusIcon status={delivery.status} />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm capitalize text-foreground">
                {delivery.provider ?? CHANNEL_LABEL[delivery.channel]}
              </p>
              {/*
               * The status, not the reason. The activity timeline beside this
               * already carries the provider's own error text in its proper
               * place — a chronology — and printing it twice on one screen is
               * how a page starts reading as noise instead of an answer. It
               * stays reachable on hover for the moment someone needs it.
               */}
              <p
                className="mt-0.5 text-xs leading-5 text-muted-foreground"
                title={delivery.last_error ?? undefined}
              >
                {statusText(delivery)}
              </p>
            </div>
            {delivery.retryable && (
              <button
                type="button"
                onClick={() => retry.mutate({ leadId, deliveryId: delivery.id })}
                disabled={retry.isPending}
                className="btn btn-ghost h-7 shrink-0 px-2 text-xs"
              >
                {retry.isPending ? (
                  <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                ) : (
                  <RefreshCw className="size-3.5" aria-hidden="true" />
                )}
                Retry
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
