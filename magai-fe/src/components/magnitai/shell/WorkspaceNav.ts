import { BarChart3, LifeBuoy, LayoutGrid, Palette, Plug, Settings, Users } from "lucide-react";

/**
 * The workspace's destinations, in one place.
 *
 * Previously this list lived inline in `Navigation` and was duplicated as a
 * second row by `DashboardNav`, so the two could — and did — disagree about
 * what the app contains.
 *
 * Order follows how often a signed-in owner needs each screen, which is also
 * the order of the funnel they describe: what did I make, how is it doing, who
 * did it bring me. `Settings` is deliberately not in that group; it sits at the
 * foot of the rail, where every product surveyed puts it.
 */
export interface WorkspaceDestination {
  label: string;
  to: string;
  icon: typeof LayoutGrid;
  /**
   * Paths this destination owns, longest-first. A widget's own page is a child
   * of Overview, so `/dashboard/widgets/abc` has to light Overview up rather
   * than leaving the rail with nothing selected — a naive `startsWith`
   * on `/dashboard` would instead light up Overview on Leads and Settings too.
   */
  owns: string[];
}

export const WORKSPACE_NAV: WorkspaceDestination[] = [
  {
    label: "Overview",
    to: "/dashboard",
    icon: LayoutGrid,
    owns: ["/dashboard", "/dashboard/widgets"],
  },
  { label: "Analytics", to: "/analytics", icon: BarChart3, owns: ["/analytics"] },
  { label: "Leads", to: "/dashboard/leads", icon: Users, owns: ["/dashboard/leads"] },
];

/**
 * Things you configure once and rarely revisit.
 *
 * Separated from the group above because they answer a different question. The
 * first group is "how are my tools doing"; this one is "how should tools behave
 * when I make them". Mixing the two is how a rail grows to nine equal-weight
 * entries that all look equally urgent.
 */
export const WORKSPACE_SETUP_NAV: WorkspaceDestination[] = [
  { label: "Brand", to: "/dashboard/brand", icon: Palette, owns: ["/dashboard/brand"] },
  {
    label: "Integrations",
    to: "/dashboard/integrations",
    icon: Plug,
    owns: ["/dashboard/integrations"],
  },
];

export const WORKSPACE_FOOTER_NAV: WorkspaceDestination[] = [
  { label: "Settings", to: "/dashboard/settings", icon: Settings, owns: ["/dashboard/settings"] },
  { label: "Help", to: "/dashboard/help", icon: LifeBuoy, owns: ["/dashboard/help"] },
];

const ALL = [...WORKSPACE_NAV, ...WORKSPACE_SETUP_NAV, ...WORKSPACE_FOOTER_NAV];

/**
 * Exactly one destination is active for any path: the one whose owned prefix
 * matches longest. Ties are impossible because prefixes are unique strings.
 */
export function activeDestination(pathname: string): WorkspaceDestination | null {
  let best: WorkspaceDestination | null = null;
  let bestLength = -1;

  for (const destination of ALL) {
    for (const prefix of destination.owns) {
      const matches = pathname === prefix || pathname.startsWith(`${prefix}/`);
      if (matches && prefix.length > bestLength) {
        best = destination;
        bestLength = prefix.length;
      }
    }
  }

  return best;
}
