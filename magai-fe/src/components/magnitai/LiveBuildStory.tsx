import { useNavigate } from "@tanstack/react-router";
import { ArrowRight, Check, ExternalLink, Loader2, RotateCcw, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";

import { PageHeader, StatusPill } from "@/components/magnitai/shell/PageHeader";
import { api, buildEventsUrl, type WidgetData } from "@/lib/api";

interface PipelineEvent {
  stage: string;
  status: string;
  message: string;
  data: Record<string, unknown> | null;
  progress: number | null;
  timestamp: string;
}

const STAGES = [
  { id: "analyze", label: "Reading the site", output: "Offer, audience and intent" },
  { id: "architect", label: "Designing the tool", output: "Questions, result and flow" },
  { id: "stitcher", label: "Applying the brand", output: "Colour, type and voice" },
  { id: "codegen", label: "Writing the code", output: "Interactive component" },
  { id: "deploy", label: "Publishing", output: "Stable live address" },
] as const;

export function LiveBuildStory({ widgetId }: { widgetId: string }) {
  const navigate = useNavigate();
  const [statuses, setStatuses] = useState<Record<string, string>>({});
  const [activeStage, setActiveStage] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [deployUrl, setDeployUrl] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [title, setTitle] = useState("");

  useEffect(() => {
    const eventsUrl = buildEventsUrl(widgetId);
    const stream = eventsUrl ? new EventSource(eventsUrl) : null;

    if (stream) {
      stream.onmessage = (event) => {
        if (event.data?.startsWith(":")) return;
        try {
          const evt: PipelineEvent = JSON.parse(event.data);
          setStatuses((previous) => ({ ...previous, [evt.stage]: evt.status }));
          setActiveStage(evt.stage);
          setNote(evt.message);
          if (evt.stage === "deploy" && evt.status === "complete" && evt.data?.url) {
            setDeployUrl(evt.data.url as string);
          }
        } catch {
          // A malformed frame must not tear down the stream.
        }
      };
      stream.onerror = () => {};
    }

    const poll = setInterval(() => {
      api
        .get<WidgetData>(`/api/widgets/${widgetId}`)
        .then((data) => {
          if (data.title) setTitle(data.title);
          if (data.status === "active") {
            if (data.deployment_url) setDeployUrl(data.deployment_url);
            setStatuses(Object.fromEntries(STAGES.map((stage) => [stage.id, "complete"])));
          } else if (data.status === "failed") {
            setFailure(data.build_error || "The build didn't finish.");
          } else if (data.build_stage) {
            setActiveStage(data.build_stage);
            setStatuses((previous) => ({ ...previous, [data.build_stage as string]: "active" }));
          }
        })
        .catch(() => {
          // A transient request failure is retried at the next poll.
        });
    }, 4_000);

    return () => {
      stream?.close();
      clearInterval(poll);
    };
  }, [widgetId]);

  const done = Boolean(deployUrl);
  const activeIndex = STAGES.findIndex((stage) => stage.id === activeStage);
  const current = STAGES[Math.max(0, activeIndex)] ?? STAGES[0];

  if (failure) {
    return (
      <>
        <PageHeader
          title="The build needs attention"
          description="The last safe version was preserved. You can return to the brief and try again."
          meta={<StatusPill tone="attention">Build stopped</StatusPill>}
        />
        <section className="surface mx-auto mt-8 max-w-2xl p-6 sm:p-8">
          <span className="grid size-11 place-items-center rounded-xl bg-destructive/10 text-destructive">
            <TriangleAlert className="size-5" aria-hidden="true" />
          </span>
          <h2 className="mt-5 text-xl font-medium tracking-[-0.025em]">
            What the pipeline reported
          </h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{failure}</p>
          <button onClick={() => navigate({ to: "/build" })} className="btn btn-primary mt-7">
            <RotateCcw className="size-4" aria-hidden="true" />
            Return to the brief
          </button>
        </section>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={done ? (title ? `${title} is live` : "Your tool is live") : "Building your tool"}
        description={
          done
            ? "The published tool is running at its stable address. Review it here before embedding it."
            : "Each completed stage leaves a real artifact for the next one. You can leave this page; the build keeps running."
        }
        meta={
          <StatusPill tone={done ? "live" : "pending"}>
            {done ? "Published and healthy" : current.label}
          </StatusPill>
        }
      />

      <div className="grid items-start gap-5 lg:grid-cols-[19rem_minmax(0,1fr)]">
        <aside className="surface overflow-hidden lg:sticky lg:top-24">
          <div className="border-b border-border px-5 py-4">
            <p className="text-sm font-medium">Build pipeline</p>
            <p className="mt-0.5 text-xs text-muted-foreground">Five stages, in order</p>
          </div>
          <ol className="divide-y divide-border" aria-live="polite">
            {STAGES.map((stage, index) => {
              const status = statuses[stage.id] ?? "pending";
              const isActive = !done && (status === "active" || activeStage === stage.id);
              const isComplete = done || status === "complete";

              return (
                <li
                  key={stage.id}
                  className={`grid grid-cols-[2rem_1fr] gap-3 px-5 py-4 ${
                    isActive ? "bg-brand-wash" : ""
                  }`}
                >
                  <span
                    className={`grid size-8 place-items-center rounded-full border text-xs ${
                      isComplete
                        ? "border-foreground bg-foreground text-background"
                        : isActive
                          ? "border-foreground bg-brand text-foreground"
                          : "border-border text-muted-foreground"
                    }`}
                  >
                    {isComplete ? (
                      <Check className="size-3.5" aria-hidden="true" />
                    ) : isActive ? (
                      <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                    ) : (
                      <span className="font-mono text-[10px]">0{index + 1}</span>
                    )}
                  </span>
                  <div>
                    <p
                      className={`text-sm font-medium ${
                        isComplete || isActive ? "text-foreground" : "text-muted-foreground"
                      }`}
                    >
                      {stage.label}
                    </p>
                    <p className="mt-0.5 text-xs leading-5 text-muted-foreground">{stage.output}</p>
                  </div>
                </li>
              );
            })}
          </ol>
        </aside>

        {done && deployUrl ? (
          <section className="overflow-hidden rounded-[1.5rem] border border-border bg-card shadow-card">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4">
              <div>
                <h2 className="text-sm font-medium text-foreground">Live preview</h2>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  This is the deployed tool, not a screenshot.
                </p>
              </div>
              <a
                href={deployUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-secondary h-9 px-3 text-sm"
              >
                Open live
                <ExternalLink className="size-3.5" aria-hidden="true" />
              </a>
            </div>
            <iframe
              src={deployUrl}
              title={title || "Your tool"}
              className="h-[36rem] w-full border-0 bg-white"
              sandbox="allow-scripts allow-same-origin allow-forms"
            />
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-4">
              <p className="text-xs leading-5 text-muted-foreground">
                The address stays the same through future repairs.
              </p>
              <button
                onClick={() =>
                  navigate({ to: "/dashboard/widgets/$widgetId", params: { widgetId } })
                }
                className="btn btn-accent"
              >
                Put it on my site
                <ArrowRight className="size-4" aria-hidden="true" />
              </button>
            </div>
          </section>
        ) : (
          <section className="editorial-grid-dark relative min-h-[34rem] overflow-hidden rounded-[1.5rem] border border-inverse-border bg-inverse text-inverse-foreground shadow-card">
            <div className="relative flex min-h-[34rem] flex-col p-6 sm:p-9">
              <div className="flex items-center justify-between gap-4 border-b border-inverse-border pb-5">
                <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-brand-on-inverse">
                  In progress · 0{Math.max(1, activeIndex + 1)} / 05
                </span>
                <Loader2 className="size-4 animate-spin text-brand-on-inverse" aria-hidden="true" />
              </div>

              <div className="my-auto py-14">
                <p className="text-sm text-inverse-muted">Current stage</p>
                <h2 className="mt-3 max-w-[12ch] font-display text-[clamp(3rem,6vw,5.2rem)] font-normal leading-[0.92] tracking-[-0.055em]">
                  {current.label}
                </h2>
                <p className="mt-5 max-w-lg text-base leading-7 text-inverse-muted">
                  {note || `${current.output} is being prepared for the next stage.`}
                </p>
              </div>

              <div className="border-t border-inverse-border pt-5">
                <p className="max-w-lg text-xs leading-5 text-inverse-subtle">
                  Only pipeline events reported by the build are shown here. There are no decorative
                  confidence scores or simulated completion times.
                </p>
              </div>
            </div>
          </section>
        )}
      </div>
    </>
  );
}
