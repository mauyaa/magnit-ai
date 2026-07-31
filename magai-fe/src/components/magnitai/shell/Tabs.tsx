import { Link } from "@tanstack/react-router";

/**
 * The tab bar for a tool's detail page.
 *
 * Tabs are links carrying a search param rather than component state, so a tab
 * is addressable: it survives a refresh, it can be linked to from elsewhere,
 * and the back button steps between tabs the way a reader expects.
 *
 * Deliberately typed to the one route it serves instead of being generic. A
 * generic version cannot prove to the router that its tab ids are that route's
 * search union, so it only compiles behind a cast — and a cast here would
 * silently accept a tab id the route rejects. If a second detail page ever
 * needs tabs, generalise it then, with both unions in hand.
 */
export type WidgetTabId =
  "overview" | "questions" | "outcomes" | "embed" | "leads" | "activity" | "settings";

export interface TabDefinition {
  id: WidgetTabId;
  label: string;
  /** Rendered after the label — a count, usually. Hidden when zero. */
  badge?: number;
}

export function WidgetTabs({
  tabs,
  active,
  widgetId,
}: {
  tabs: TabDefinition[];
  active: WidgetTabId;
  widgetId: string;
}) {
  return (
    <div className="border-b border-border">
      <nav className="-mb-px flex gap-1 overflow-x-auto" aria-label="Sections">
        {tabs.map((tab) => {
          const selected = tab.id === active;
          return (
            <Link
              key={tab.id}
              to="/dashboard/widgets/$widgetId"
              params={{ widgetId }}
              search={{ tab: tab.id }}
              aria-current={selected ? "page" : undefined}
              className={`flex shrink-0 items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm transition-colors ${
                selected
                  ? "border-foreground font-medium text-foreground"
                  : "border-transparent text-muted-foreground hover:border-border-strong hover:text-foreground"
              }`}
            >
              {tab.label}
              {tab.badge !== undefined && tab.badge > 0 && (
                <span
                  className={`tabular rounded-full px-1.5 py-0.5 text-xs leading-none ${
                    selected ? "bg-secondary text-foreground" : "bg-n-100 text-muted-foreground"
                  }`}
                >
                  {tab.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
