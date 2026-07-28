import { createFileRoute } from "@tanstack/react-router";
import {
  AlertCircle,
  Check,
  ExternalLink,
  Loader2,
  Lock,
  Plug,
  Send,
  Trash2,
  X,
} from "lucide-react";
import { useState } from "react";

import { RequireAuth } from "@/components/magnitai/RequireAuth";
import { PageHeader } from "@/components/magnitai/shell/PageHeader";
import { WorkspaceShell } from "@/components/magnitai/shell/WorkspaceShell";
import {
  useConnectIntegration,
  useDisconnectIntegration,
  useIntegrationCatalog,
  useIntegrations,
  useTestIntegration,
  useUpdateIntegration,
  useWidgets,
  type IntegrationData,
  type IntegrationProvider,
} from "@/lib/api";
import { UpgradeNotice } from "@/lib/plan";

export const Route = createFileRoute("/dashboard/integrations")({
  head: () => ({ meta: [{ title: "Integrations · Magnitai" }] }),
  component: () => (
    <RequireAuth>
      <Integrations />
    </RequireAuth>
  ),
});

const FIELD =
  "h-10 w-full rounded-lg border border-border bg-card px-3 text-sm text-foreground outline-none placeholder:text-n-400 focus:border-foreground/40";

/** A short, human line for a connection's current state. */
function statusLine(integration: IntegrationData): { tone: string; text: string } {
  if (integration.status === "disabled") {
    return { tone: "text-muted-foreground", text: "Paused" };
  }
  if (integration.status === "error") {
    return {
      tone: "text-destructive",
      text: integration.last_error ?? "Last delivery failed",
    };
  }
  if (integration.delivered_count > 0) {
    return {
      tone: "text-success",
      text: `${integration.delivered_count.toLocaleString()} delivered`,
    };
  }
  return { tone: "text-success", text: "Connected" };
}

/**
 * The connect form for one provider.
 *
 * Rendered from the provider's own declared fields rather than a per-provider
 * component, so adding a provider on the server is enough — there is no matching
 * frontend change to forget.
 */
function ConnectDialog({
  provider,
  onClose,
}: {
  provider: IntegrationProvider;
  onClose: () => void;
}) {
  const connect = useConnectIntegration();
  const [values, setValues] = useState<Record<string, string>>({});

  const missing = provider.fields
    .filter((field) => field.required && !(values[field.name] ?? "").trim())
    .map((field) => field.name);

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4 backdrop-blur-xs"
      role="dialog"
      aria-modal="true"
      aria-label={`Connect ${provider.name}`}
      onClick={onClose}
    >
      <div
        className="surface w-full max-w-lg overflow-hidden"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div className="min-w-0">
            <h2 className="text-base font-medium text-foreground">Connect {provider.name}</h2>
            <p className="mt-0.5 text-sm leading-6 text-muted-foreground">{provider.setup_hint}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="btn btn-ghost size-8 shrink-0 px-0"
            aria-label="Close"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>

        <form
          className="space-y-3 px-5 py-4"
          onSubmit={(event) => {
            event.preventDefault();
            connect.mutate({ provider: provider.id, values }, { onSuccess: onClose });
          }}
        >
          {provider.fields.map((field) => (
            <label key={field.name} className="block">
              <span className="mb-1.5 block text-sm font-medium text-foreground">
                {field.label}
                {!field.required && (
                  <span className="ml-1.5 text-xs font-normal text-muted-foreground">optional</span>
                )}
              </span>
              <input
                // Secrets are write-only everywhere: never rendered back, and
                // masked as they are typed.
                type={field.kind === "secret" ? "password" : field.kind === "url" ? "url" : "text"}
                autoComplete="off"
                spellCheck={false}
                placeholder={field.placeholder}
                value={values[field.name] ?? ""}
                onChange={(event) =>
                  setValues((current) => ({ ...current, [field.name]: event.target.value }))
                }
                className={FIELD}
              />
              <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                {field.help_text}
              </span>
            </label>
          ))}

          {connect.isError && (
            <p role="alert" className="flex items-start gap-1.5 text-sm text-destructive">
              <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              {(connect.error as Error).message}
            </p>
          )}

          <div className="flex flex-wrap items-center gap-3 pt-1">
            <button
              type="submit"
              disabled={connect.isPending || missing.length > 0}
              className="btn btn-primary h-9 text-sm"
            >
              {connect.isPending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
              Connect
            </button>
            {provider.docs_url && (
              <a
                href={provider.docs_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
              >
                Where do I find this?
                <ExternalLink className="size-3.5" aria-hidden="true" />
              </a>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}

function ConnectedCard({
  integration,
  provider,
  toolCount,
}: {
  integration: IntegrationData;
  provider: IntegrationProvider | undefined;
  toolCount: number;
}) {
  const update = useUpdateIntegration();
  const test = useTestIntegration();
  const disconnect = useDisconnectIntegration();
  const status = statusLine(integration);
  const enabled = integration.status !== "disabled";

  return (
    <article className="surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-medium text-foreground">
            {provider?.name ?? integration.provider}
          </h3>
          <p className={`mt-0.5 text-sm ${status.tone}`}>{status.text}</p>
        </div>

        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          aria-label={`${provider?.name ?? integration.provider} enabled`}
          disabled={update.isPending}
          onClick={() => update.mutate({ id: integration.id, enabled: !enabled })}
          className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
            enabled ? "bg-foreground" : "bg-n-300"
          }`}
        >
          <span
            className={`absolute top-0.5 size-5 rounded-full bg-card shadow-raised transition-transform ${
              enabled ? "translate-x-[1.375rem]" : "translate-x-0.5"
            }`}
          />
        </button>
      </div>

      <dl className="mt-3 grid grid-cols-3 gap-2 border-t border-border pt-3">
        {(
          [
            ["Delivered", integration.delivered_count.toLocaleString()],
            ["Failed", integration.failed_count.toLocaleString()],
            [
              "Tools",
              integration.widget_ids === null
                ? `All ${toolCount}`
                : String(integration.widget_ids.length),
            ],
          ] as const
        ).map(([label, value]) => (
          <div key={label}>
            <dt className="text-[11px] text-muted-foreground">{label}</dt>
            <dd className="tabular mt-0.5 text-sm font-medium text-foreground">{value}</dd>
          </div>
        ))}
      </dl>

      {integration.credential_hint && (
        <p className="mt-3 font-mono text-xs text-muted-foreground">
          Key {integration.credential_hint}
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border pt-3">
        <button
          type="button"
          onClick={() => test.mutate(integration.id)}
          disabled={test.isPending}
          className="btn btn-secondary h-8 px-2.5 text-xs"
        >
          {test.isPending ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
          ) : (
            <Send className="size-3.5" aria-hidden="true" />
          )}
          Send test lead
        </button>

        <button
          type="button"
          onClick={() => disconnect.mutate(integration.id)}
          disabled={disconnect.isPending}
          className="btn btn-ghost h-8 px-2.5 text-xs"
        >
          <Trash2 className="size-3.5" aria-hidden="true" />
          Disconnect
        </button>

        {test.data && (
          <span
            aria-live="polite"
            className={`flex items-center gap-1.5 text-xs ${
              test.data.ok ? "text-success" : "text-destructive"
            }`}
          >
            {test.data.ok ? (
              <Check className="size-3.5" aria-hidden="true" />
            ) : (
              <AlertCircle className="size-3.5" aria-hidden="true" />
            )}
            {test.data.message}
          </span>
        )}
      </div>
    </article>
  );
}

function Integrations() {
  const { data: catalog, isLoading } = useIntegrationCatalog();
  const { data: connected } = useIntegrations();
  const { data: widgetData } = useWidgets();
  const [connecting, setConnecting] = useState<IntegrationProvider | null>(null);

  const providers = catalog?.providers ?? [];
  const integrations = connected?.integrations ?? [];
  const connectedIds = new Set(integrations.map((item) => item.provider));
  const toolCount = widgetData?.widgets.length ?? 0;

  const available = providers.filter((provider) => !connectedIds.has(provider.id));
  const byCategory = available.reduce<Record<string, IntegrationProvider[]>>((groups, provider) => {
    (groups[provider.category] ??= []).push(provider);
    return groups;
  }, {});

  if (isLoading) {
    return (
      <WorkspaceShell breadcrumb={[{ label: "Integrations" }]}>
        <div className="flex justify-center py-32">
          <Loader2 className="size-5 animate-spin text-muted-foreground" aria-label="Loading" />
        </div>
      </WorkspaceShell>
    );
  }

  return (
    <WorkspaceShell breadcrumb={[{ label: "Integrations" }]}>
      <PageHeader
        title="Integrations"
        description="Where a captured lead goes next. Connect once and every tool can use it."
      />

      {integrations.length > 0 && (
        <section className="pb-8">
          <h2 className="pb-3 text-base font-medium text-foreground">Connected</h2>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {integrations.map((integration) => (
              <ConnectedCard
                key={integration.id}
                integration={integration}
                provider={providers.find((p) => p.id === integration.provider)}
                toolCount={toolCount}
              />
            ))}
          </div>
        </section>
      )}

      {Object.entries(byCategory).map(([category, group]) => (
        <section key={category} className="pb-8">
          <h2 className="pb-3 text-base font-medium text-foreground">{category}</h2>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {group.map((provider) => (
              <article key={provider.id} className="surface flex flex-col p-4">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-medium text-foreground">{provider.name}</h3>
                  {!provider.available && (
                    <Lock className="size-3.5 shrink-0 text-n-400" aria-label="Not on your plan" />
                  )}
                </div>
                <p className="mt-1 flex-1 text-sm leading-6 text-muted-foreground">
                  {provider.description}
                </p>

                {provider.available ? (
                  <button
                    type="button"
                    onClick={() => setConnecting(provider)}
                    className="btn btn-secondary mt-4 h-9 w-full text-sm"
                  >
                    <Plug className="size-4" aria-hidden="true" />
                    Connect
                  </button>
                ) : (
                  <div className="mt-4">
                    <UpgradeNotice feature={provider.feature} compact />
                  </div>
                )}
              </article>
            ))}
          </div>
        </section>
      ))}

      {connecting && <ConnectDialog provider={connecting} onClose={() => setConnecting(null)} />}
    </WorkspaceShell>
  );
}
