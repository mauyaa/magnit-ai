import type { WidgetTabId } from "@/components/magnitai/shell/Tabs";
import type { WidgetData } from "@/lib/api";

type RecommendationDestination =
  | {
      kind: "widget";
      widgetId: string;
      tab?: WidgetTabId;
    }
  | {
      kind: "build";
      widgetId: string;
    }
  | {
      kind: "leads";
    };

export interface WorkspaceRecommendation {
  tone: "attention" | "pending" | "action" | "insight";
  title: string;
  detail: string;
  cta: string;
  destination: RecommendationDestination;
}

/**
 * Turn the workspace's real state into one useful next action.
 *
 * The sample guards matter. A handful of visits is not enough evidence to tell
 * an owner to rewrite a working tool, so optimization advice only appears after
 * the relevant stage has a modest amount of traffic. Before that, Magnitai
 * recommends distribution or observation rather than pretending to know.
 */
export function recommendationFor(widgets: WidgetData[]): WorkspaceRecommendation | null {
  const failed = widgets.find((widget) => widget.status === "failed");
  if (failed) {
    return {
      tone: "attention",
      title: `Review ${failed.title}`,
      detail:
        "This tool needs attention. Magnitai preserved the last safe version and the activity log shows what happened.",
      cta: "Review and restore",
      destination: { kind: "widget", widgetId: failed.id },
    };
  }

  const building = widgets.find((widget) => widget.status === "building");
  if (building) {
    return {
      tone: "pending",
      title: `${building.title} is being built`,
      detail:
        "The build continues if you leave. Follow the live stages now, or come back when the published version is ready.",
      cta: "Watch the build",
      destination: { kind: "build", widgetId: building.id },
    };
  }

  const unfinished = widgets.find((widget) => !widget.deployment_url || widget.status !== "active");
  if (unfinished) {
    return {
      tone: "action",
      title: `Finish ${unfinished.title}`,
      detail:
        "Review the questions and result, then publish it to a stable address before sending any traffic.",
      cta: "Finish this tool",
      destination: { kind: "widget", widgetId: unfinished.id },
    };
  }

  const live = widgets.filter(
    (widget) => widget.status === "active" && Boolean(widget.deployment_url),
  );

  const notEmbedded = live.find((widget) => widget.impressions_count === 0);
  if (notEmbedded) {
    return {
      tone: "action",
      title: `Put ${notEmbedded.title} in front of visitors`,
      detail:
        "The tool is live but has not been seen yet. Copy its embed snippet and add it to the page it was built for.",
      cta: "Get the embed",
      destination: { kind: "widget", widgetId: notEmbedded.id, tab: "embed" },
    };
  }

  const noStarts = live.find(
    (widget) => widget.impressions_count >= 20 && widget.starts_count === 0,
  );
  if (noStarts) {
    return {
      tone: "insight",
      title: `Visitors see ${noStarts.title}, but do not start`,
      detail:
        "There is enough traffic to inspect the opening. Make the first question and the promised result more specific.",
      cta: "Edit the opening",
      destination: { kind: "widget", widgetId: noStarts.id, tab: "questions" },
    };
  }

  const earlyDropoff = live.find(
    (widget) =>
      widget.starts_count >= 10 &&
      widget.completions_count / Math.max(widget.starts_count, 1) < 0.5,
  );
  if (earlyDropoff) {
    return {
      tone: "insight",
      title: `People start ${earlyDropoff.title}, then leave`,
      detail:
        "Fewer than half of starters finish. Review the question order and remove anything that does not improve the result.",
      cta: "Review questions",
      destination: { kind: "widget", widgetId: earlyDropoff.id, tab: "questions" },
    };
  }

  const noLeads = live.find((widget) => widget.completions_count >= 5 && widget.leads_count === 0);
  if (noLeads) {
    return {
      tone: "insight",
      title: `${noLeads.title} delivers results, but not leads`,
      detail:
        "Visitors are finishing the experience. Strengthen the result, next step and reason to continue the conversation.",
      cta: "Improve the result",
      destination: { kind: "widget", widgetId: noLeads.id, tab: "outcomes" },
    };
  }

  const withLeads = live.reduce<WidgetData | null>(
    (best, widget) => (!best || widget.leads_count > best.leads_count ? widget : best),
    null,
  );
  if (withLeads && withLeads.leads_count > 0) {
    return {
      tone: "insight",
      title: `Learn from the people using ${withLeads.title}`,
      detail: `${withLeads.leads_count.toLocaleString()} ${
        withLeads.leads_count === 1 ? "lead has" : "leads have"
      } come through this tool. Review their answers and decide who needs a follow-up.`,
      cta: "Review leads",
      destination: { kind: "leads" },
    };
  }

  const collecting = live[0];
  if (collecting) {
    return {
      tone: "action",
      title: `Keep sharing ${collecting.title}`,
      detail:
        "The tool is live and collecting its first useful sample. Send more visitors before changing the experience.",
      cta: "Open the embed",
      destination: { kind: "widget", widgetId: collecting.id, tab: "embed" },
    };
  }

  return null;
}
