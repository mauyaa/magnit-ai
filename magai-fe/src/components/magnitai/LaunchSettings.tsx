import { Cable, Check, CheckCircle2, ChevronDown, Loader2, Send } from "lucide-react";
import { useState } from "react";

import { useConfigureLaunch, useTestLaunchConnection, type WidgetData } from "@/lib/api";

function stored(settings: Record<string, unknown> | null, key: string): string {
  const value = settings?.[key];
  return typeof value === "string" ? value : "";
}

const DELIVERY_OPTIONS = [
  { value: "zapier", label: "Zapier", note: "Catch Hook" },
  { value: "make", label: "Make", note: "Custom webhook" },
  { value: "n8n", label: "n8n", note: "Webhook trigger" },
  { value: "custom", label: "Custom", note: "Your endpoint" },
] as const;

export function LaunchSettings({ widget }: { widget: WidgetData }) {
  const configure = useConfigureLaunch();
  const testConnection = useTestLaunchConnection();
  const [secret, setSecret] = useState<string | null>(null);
  const [deliveryMode, setDeliveryMode] = useState(
    stored(widget.launch_settings, "delivery_mode") || "custom",
  );
  const savedStatus = stored(widget.launch_settings, "delivery_status");
  const connected = testConnection.data?.connected ?? savedStatus === "connected";
  const checkedAt =
    testConnection.data?.checked_at || stored(widget.launch_settings, "delivery_checked_at");

  return (
    <details className="group surface overflow-hidden">
      <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 marker:hidden sm:px-6">
        <span className="flex items-start gap-3">
          <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-lg bg-secondary">
            <Cable className="size-4 text-foreground" aria-hidden="true" />
          </span>
          <span>
            <strong className="block text-sm font-medium text-foreground">
              Launch and lead delivery
            </strong>
            <span className="mt-0.5 block text-xs leading-5 text-muted-foreground">
              Choose where the result points and where captured leads are sent.
            </span>
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-3">
          {connected && (
            <span className="hidden items-center gap-1.5 text-xs font-medium text-success sm:flex">
              <CheckCircle2 className="size-3.5" aria-hidden="true" />
              Connected
            </span>
          )}
          <ChevronDown
            className="size-4 text-muted-foreground transition-transform group-open:rotate-180"
            aria-hidden="true"
          />
        </span>
      </summary>

      <form
        className="grid gap-5 border-t border-border px-5 py-6 sm:grid-cols-2 sm:px-6"
        // `mutate` with a callback, not an awaited `mutateAsync`: the server
        // rejects an unreachable or private webhook URL, and awaiting that in a
        // bare submit handler turned a validation error the user should read
        // into an unhandled rejection.
        onSubmit={(event) => {
          event.preventDefault();
          const data = new FormData(event.currentTarget);
          configure.mutate(
            {
              widgetId: widget.id,
              targetPageUrl: String(data.get("target_page_url") || ""),
              ctaUrl: String(data.get("cta_url") || ""),
              ctaLabel: String(data.get("cta_label") || ""),
              deliveryWebhookUrl: String(data.get("webhook_url") || ""),
              deliveryMode: deliveryMode as "custom" | "zapier" | "make" | "n8n",
              consentText: String(data.get("consent_text") || ""),
            },
            { onSuccess: (response) => setSecret(response.webhook_signing_secret) },
          );
        }}
      >
        <div className="sm:col-span-2">
          <p className="text-sm font-medium text-foreground">After the result</p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            Decide where the visitor goes and where every captured lead is delivered.
          </p>
        </div>

        <label className="grid gap-1.5 text-sm font-medium text-foreground">
          Page where this experience will live
          <input
            name="target_page_url"
            type="url"
            defaultValue={stored(widget.launch_settings, "target_page_url")}
            placeholder="https://yourcompany.com/pricing"
            className="h-11 rounded-lg border border-input bg-background px-3 text-sm font-normal text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </label>
        <label className="grid gap-1.5 text-sm font-medium text-foreground">
          Result button label
          <input
            name="cta_label"
            defaultValue={stored(widget.launch_settings, "cta_label")}
            placeholder="Book a consultation"
            className="h-11 rounded-lg border border-input bg-background px-3 text-sm font-normal text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </label>
        <label className="grid gap-1.5 text-sm font-medium text-foreground sm:col-span-2">
          Result button destination
          <input
            name="cta_url"
            type="url"
            defaultValue={stored(widget.launch_settings, "cta_url")}
            placeholder="https://yourcompany.com/book"
            className="h-11 rounded-lg border border-input bg-background px-3 text-sm font-normal text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </label>

        <div className="mt-2 border-t border-border pt-5 sm:col-span-2">
          <p className="text-sm font-medium text-foreground">Lead destination</p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            Choose the service, paste its receiving URL, then send a signed test event.
          </p>
          <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {DELIVERY_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setDeliveryMode(option.value)}
                className={`rounded-xl border px-3 py-3 text-left transition ${
                  deliveryMode === option.value
                    ? "border-foreground bg-foreground text-background"
                    : "border-border bg-background text-foreground hover:border-foreground/25"
                }`}
              >
                <span className="block text-xs font-semibold">{option.label}</span>
                <span
                  className={`mt-1 block text-[10px] ${
                    deliveryMode === option.value ? "text-background/55" : "text-muted-foreground"
                  }`}
                >
                  {option.note}
                </span>
              </button>
            ))}
          </div>
        </div>

        <label className="grid gap-1.5 text-sm font-medium text-foreground sm:col-span-2">
          Receiving URL
          <input
            name="webhook_url"
            type="url"
            defaultValue={widget.delivery_webhook_url ?? ""}
            placeholder="https://hooks.example.com/your-connection"
            className="h-11 rounded-lg border border-input bg-background px-3 text-sm font-normal text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </label>
        <label className="grid gap-1.5 text-sm font-medium text-foreground sm:col-span-2">
          Consent line shown before submission
          <input
            name="consent_text"
            defaultValue={widget.consent_text ?? ""}
            placeholder="By submitting, you agree to be contacted about this result."
            className="h-11 rounded-lg border border-input bg-background px-3 text-sm font-normal text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </label>

        {secret && (
          <div className="rounded-lg bg-secondary p-3 text-xs text-muted-foreground sm:col-span-2">
            Save this signing secret now:{" "}
            <code className="break-all font-mono text-foreground">{secret}</code>
          </div>
        )}

        {(configure.error || testConnection.error) && (
          <p className="text-xs text-destructive sm:col-span-2">
            {((configure.error || testConnection.error) as Error).message}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
          <button type="submit" disabled={configure.isPending} className="btn btn-primary">
            {configure.isPending ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Check className="size-3.5" />
            )}
            Save settings
          </button>
          <button
            type="button"
            disabled={!widget.delivery_webhook_url || testConnection.isPending}
            onClick={() => testConnection.mutate(widget.id)}
            className="btn btn-secondary"
          >
            {testConnection.isPending ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Send className="size-3.5" />
            )}
            Send test
          </button>
          {checkedAt && (
            <span className="text-[11px] text-muted-foreground">
              {connected ? "Accepted" : "Last test failed"} · {new Date(checkedAt).toLocaleString()}
            </span>
          )}
        </div>
      </form>
    </details>
  );
}
