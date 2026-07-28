import { Check, Code2, Copy, ExternalLink } from "lucide-react";
import { useEffect, useRef, useState } from "react";

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

export function EmbedCodePanel({
  embedCode,
  deploymentUrl,
}: {
  embedCode: string | null;
  deploymentUrl: string | null;
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
    if (!embedCode || !deploymentUrl) return "";
    switch (platform) {
      case "react":
        return `// React / Next.js
export function MagnitaiTool() {
  return (
    <iframe
      src="${deploymentUrl}"
      title="Interactive tool"
      width="100%"
      height="640"
      loading="lazy"
      style={{ border: 0, width: "100%" }}
    />
  );
}`;
      case "webflow":
        return `<!-- Webflow Custom Embed -->
<div class="magnitai-tool" style="width:100%; min-height:640px">
  <iframe
    src="${deploymentUrl}"
    title="Interactive tool"
    width="100%"
    height="640"
    loading="lazy"
    style="border:0; width:100%"
  ></iframe>
</div>`;
      case "wordpress":
        return `<!-- WordPress Custom HTML block -->
<iframe
  src="${deploymentUrl}"
  title="Interactive tool"
  width="100%"
  height="640"
  loading="lazy"
  style="border:0; width:100%"
></iframe>`;
      case "shopify":
        return `{% comment %} Shopify Custom Liquid section {% endcomment %}
<iframe
  src="${deploymentUrl}"
  title="Interactive tool"
  width="100%"
  height="640"
  loading="lazy"
  style="border:0; width:100%"
></iframe>`;
      case "html":
      default:
        return embedCode;
    }
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

  if (!embedCode || !deploymentUrl) {
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
            href={deploymentUrl}
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
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-inverse-subtle">
              {active.label}
            </span>
            <span className="text-xs text-inverse-muted">{active.instruction}</span>
          </div>
          <pre className="max-h-[28rem] overflow-auto p-4 text-[12px] leading-6 sm:p-5">
            <code className="font-mono text-inverse-foreground">{currentSnippet}</code>
          </pre>
        </div>
      </div>

      <div className="flex flex-col gap-1 border-t border-border px-5 py-4 text-xs leading-5 text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <span>
          Paste once. The snippet never changes; Magnitai keeps the hosted tool at that address up
          to date.
        </span>
        <span className="font-mono text-[10px] uppercase tracking-[0.12em]">Stable URL</span>
      </div>

      <span aria-live="polite" className="sr-only">
        {copied ? "Embed code copied to clipboard" : ""}
      </span>
    </section>
  );
}
