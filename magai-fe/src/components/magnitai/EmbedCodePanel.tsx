import { Check, Code2, Copy, ExternalLink, Loader2, MapPin, RefreshCw } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useReadiness } from "@/lib/api";

export type PlatformTab = "html" | "react" | "webflow" | "wordpress" | "shopify";

const PLATFORMS: Array<{ id: PlatformTab; label: string; instruction: string }> = [
  { id: "html", label: "HTML", instruction: "Paste before the closing body tag." },
  {
    id: "react",
    label: "React / Next.js",
    instruction: "Render this component where the tool belongs.",
  },
  { id: "webflow", label: "Webflow", instruction: "Paste into a Custom Embed element." },
  { id: "wordpress", label: "WordPress", instruction: "Paste into a Custom HTML block." },
  { id: "shopify", label: "Shopify", instruction: "Paste into a Custom Liquid section." },
];

function InstallationVerifier({ widgetId }: { widgetId: string }) {
  const readiness = useReadiness(widgetId);
  const [result, setResult] = useState<"installed" | "missing" | "error" | null>(null);

  async function verifyInstallation() {
    const response = await readiness.refetch();
    if (response.error || !response.data) {
      setResult("error");
      return;
    }

    const embedded = response.data.checks.find((check) => check.id === "embedded");
    setResult(embedded?.done ? "installed" : "missing");
  }

  const message =
    result === "installed"
      ? "Installation detected"
      : result === "missing"
        ? "Not detected yet"
        : result === "error"
          ? "Could not check"
          : "";

  return (
    <div className="flex flex-wrap items-center gap-3">
      <button
        type="button"
        onClick={() => void verifyInstallation()}
        disabled={readiness.isFetching}
        className="btn btn-secondary h-9 px-3 text-xs"
      >
        {readiness.isFetching ? (
          <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
        ) : result === "installed" ? (
          <Check className="size-3.5 text-success" aria-hidden="true" />
        ) : (
          <RefreshCw className="size-3.5" aria-hidden="true" />
        )}
        Verify installation
      </button>
      <span
        role={message ? "status" : undefined}
        className={`text-xs ${
          result === "installed"
            ? "text-success"
            : result === "missing" || result === "error"
              ? "text-muted-foreground"
              : ""
        }`}
      >
        {message}
      </span>
    </div>
  );
}

/**
 * The React component a developer drops into their app.
 *
 * The other four platforms take raw HTML, so they get the API's own snippet
 * verbatim — one implementation, no chance of the height behaviour drifting
 * between them. React cannot, so this is the one place the same contract is
 * written twice, and it is written to match: same message type, same source
 * check, same bounds.
 */
function reactSnippet(embedUrl: string): string {
  const origin = new URL(embedUrl).origin;
  return `import { useEffect, useRef, useState } from "react";

const TOOL_URL = "${embedUrl}";
const TOOL_ORIGIN = "${origin}";

export function MagnitaiTool() {
  const frame = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(520);

  useEffect(() => {
    function onMessage(event: MessageEvent) {
      if (event.source !== frame.current?.contentWindow) return;
      if (event.origin !== TOOL_ORIGIN) return;
      if (event.data?.type !== "magnit:resize") return;
      const next = Number(event.data.height);
      if (Number.isFinite(next) && next >= 240 && next <= 5000) {
        setHeight(Math.ceil(next));
      }
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  return (
    <iframe
      ref={frame}
      src={TOOL_URL}
      title="Interactive decision tool"
      loading="lazy"
      style={{ display: "block", width: "100%", height, border: 0 }}
    />
  );
}`;
}

const PLATFORM_HEADER: Partial<Record<PlatformTab, string>> = {
  webflow: "<!-- Paste into a Webflow Custom Embed element -->",
  wordpress: "<!-- Paste into a WordPress Custom HTML block -->",
  shopify: "{% comment %} Paste into a Shopify Custom Liquid section {% endcomment %}",
};

export function EmbedCodePanel({
  widgetId,
  embedCode,
  embedUrl,
  recommendedPlacement,
  targetUrl,
}: {
  widgetId?: string;
  embedCode: string | null;
  /**
   * The tool's permanent address — not the URL of one build.
   *
   * This is what the customer pastes into a page we cannot edit afterwards, so
   * it has to keep resolving after every rebuild, repair and rollback.
   */
  embedUrl: string | null;
  recommendedPlacement?: string;
  targetUrl?: string;
}) {
  const [activePlatform, setActivePlatform] = useState<PlatformTab>("html");
  const [copied, setCopied] = useState(false);
  const resetTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (resetTimer.current) clearTimeout(resetTimer.current);
    },
    [],
  );

  const getSnippetForPlatform = (platform: PlatformTab): string => {
    if (!embedCode || !embedUrl) return "";
    if (platform === "react") return reactSnippet(embedUrl);
    // Every other platform accepts raw HTML, so it gets the identical snippet.
    // The alternative — a hand-written iframe per platform — is how four of
    // them ended up frozen at 640px while only the HTML one grew with its
    // content, cutting off the result on a phone.
    const header = PLATFORM_HEADER[platform];
    return header ? `${header}\n${embedCode}` : embedCode;
  };

  const currentSnippet = getSnippetForPlatform(activePlatform);
  const active = PLATFORMS.find((platform) => platform.id === activePlatform) ?? PLATFORMS[0];

  const handleCopy = async () => {
    if (!currentSnippet) return;
    try {
      await navigator.clipboard.writeText(currentSnippet);
      setCopied(true);
      resetTimer.current = setTimeout(() => setCopied(false), 2_000);
    } catch {
      setCopied(false);
    }
  };

  if (!embedCode || !embedUrl) {
    return (
      <div className="rounded-[1.25rem] border border-dashed border-border-strong bg-background px-6 py-12 text-center">
        <span className="mx-auto grid size-11 place-items-center rounded-xl bg-secondary text-foreground">
          <Code2 className="size-5" aria-hidden="true" />
        </span>
        <h2 className="mt-4 text-base font-medium text-foreground">
          Embed code comes after publish
        </h2>
        <p className="mx-auto mt-1.5 max-w-sm text-sm leading-6 text-muted-foreground">
          Your embed code appears here once this is published. Finish the launch checklist first;
          Magnitai will create one stable address and the exact snippet for each platform.
        </p>
      </div>
    );
  }

  return (
    <section className="surface overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border px-5 py-4 sm:px-6">
        <div>
          <h2 className="text-base font-medium tracking-[-0.02em] text-foreground">
            Put it on your site
          </h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            Choose your platform. The live address stays the same after future repairs.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <a
            href={embedUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-secondary"
          >
            Open live
            <ExternalLink className="size-3.5" aria-hidden="true" />
          </a>
          <button type="button" onClick={handleCopy} className="btn btn-primary">
            {copied ? (
              <Check className="size-4" aria-hidden="true" />
            ) : (
              <Copy className="size-4" aria-hidden="true" />
            )}
            {copied ? "Copied" : "Copy code"}
          </button>
        </div>
      </div>

      {recommendedPlacement ? (
        <div className="flex items-start gap-3 border-b border-border bg-brand-wash px-5 py-4 sm:px-6">
          <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-card text-foreground shadow-xs">
            <MapPin className="size-4" aria-hidden="true" />
          </span>
          <div>
            <p className="text-sm font-medium text-foreground">
              Recommended placement: {recommendedPlacement}
            </p>
            <p className="mt-0.5 text-xs leading-5 text-muted-foreground">
              {targetUrl
                ? `This recommendation comes from the visitor decision Magnitai found on ${targetUrl.replace(/^https?:\/\//, "")}.`
                : "This is where the tool best supports the visitor decision it was built for."}
            </p>
          </div>
        </div>
      ) : null}

      <div className="border-b border-border px-3 sm:px-5">
        <div className="flex overflow-x-auto" role="tablist" aria-label="Embed platform">
          {PLATFORMS.map((platform) => {
            const selected = activePlatform === platform.id;
            return (
              <button
                key={platform.id}
                type="button"
                role="tab"
                id={`embed-tab-${platform.id}`}
                aria-selected={selected}
                aria-controls="embed-code-panel"
                onClick={() => {
                  setActivePlatform(platform.id);
                  setCopied(false);
                }}
                className={`min-h-12 shrink-0 border-b-2 px-3 text-sm transition-colors ${
                  selected
                    ? "border-foreground font-medium text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                {platform.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="p-4 sm:p-5">
        <div
          id="embed-code-panel"
          role="tabpanel"
          aria-labelledby={`embed-tab-${activePlatform}`}
          className="overflow-hidden rounded-[1.1rem] border border-inverse-border bg-inverse"
        >
          <div className="flex items-center justify-between border-b border-inverse-border px-4 py-3">
            <span className="group-label font-mono text-inverse-subtle">{active.label}</span>
            <span className="text-xs text-inverse-muted">{active.instruction}</span>
          </div>
          <pre className="max-h-[28rem] overflow-auto p-4 text-xs leading-6 sm:p-5">
            <code className="font-mono text-inverse-foreground">{currentSnippet}</code>
          </pre>
        </div>
      </div>

      <div className="flex flex-col gap-3 border-t border-border px-5 py-4 text-xs leading-5 text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-6">
        {widgetId ? (
          <InstallationVerifier widgetId={widgetId} />
        ) : (
          <span>
            Paste once. The snippet never changes; Magnitai keeps the hosted tool at that address up
            to date.
          </span>
        )}
        <span className="group-label font-mono">Stable URL</span>
      </div>

      <span aria-live="polite" className="sr-only">
        {copied ? "Embed code copied to clipboard" : ""}
      </span>
    </section>
  );
}
