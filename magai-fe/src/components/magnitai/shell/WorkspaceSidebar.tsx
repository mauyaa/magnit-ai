import { Link, useRouterState } from "@tanstack/react-router";
import { Plus } from "lucide-react";

import { MagnitaiLogo } from "@/components/magnitai/ui/MagnitaiLogo";
import { useEntitlements, usePlans } from "@/lib/api";
import { UsageMeter } from "@/lib/plan";
import {
  activeDestination,
  WORKSPACE_FOOTER_NAV,
  WORKSPACE_NAV,
  WORKSPACE_SETUP_NAV,
  type WorkspaceDestination,
} from "./WorkspaceNav";

function NavLink({
  destination,
  active,
  onNavigate,
}: {
  destination: WorkspaceDestination;
  active: boolean;
  onNavigate?: () => void;
}) {
  const Icon = destination.icon;
  return (
    <Link
      to={destination.to}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={`flex h-9 items-center gap-2.5 rounded-lg px-2.5 text-sm transition-colors ${
        active
          ? "bg-brand font-medium text-foreground"
          : "text-inverse-muted hover:bg-inverse-raised hover:text-inverse-foreground"
      }`}
    >
      <Icon className="size-4 shrink-0" aria-hidden="true" />
      {destination.label}
    </Link>
  );
}

/**
 * The workspace rail.
 *
 * The app previously navigated itself through the marketing header — one bar
 * that swapped its links once you signed in. That works for a site with a
 * login; it stops working for a product, because there is nowhere to put a
 * plan, a create action, or a section that isn't a top-level page, and because
 * the bar's own container (max-w-6xl) never lined up with the page content it
 * sat above (max-w-7xl), so nothing on any screen shared a left edge.
 *
 * A 16rem rail is the pattern every comparable product converged on, and it is
 * what makes the create action reachable from every screen without being
 * repeated in each page header.
 */
export function WorkspaceSidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const active = activeDestination(pathname);
  const { data: entitlements } = useEntitlements();
  const { data: catalog } = usePlans();

  const plans = catalog?.plans ?? [];
  const currentIndex = plans.findIndex((plan) => plan.id === entitlements?.plan.id);
  const hasHigherPlan = currentIndex >= 0 && currentIndex < plans.length - 1;

  return (
    <div className="flex h-full flex-col bg-inverse text-inverse-foreground">
      <div className="flex h-16 shrink-0 items-center px-4">
        <Link
          to="/dashboard"
          onClick={onNavigate}
          className="flex w-fit items-center rounded-[10px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label="Magnitai workspace home"
        >
          <MagnitaiLogo
            size="md"
            variant="tile"
            className="[&_span:last-child]:text-inverse-foreground"
          />
        </Link>
      </div>

      <div className="px-3 pb-3">
        <Link to="/build" onClick={onNavigate} className="btn btn-accent h-10 w-full text-sm">
          <Plus className="size-4" aria-hidden="true" />
          New tool
        </Link>
      </div>

      <nav className="flex-1 overflow-y-auto px-3" aria-label="Workspace">
        <div className="space-y-0.5">
          {WORKSPACE_NAV.map((destination) => (
            <NavLink
              key={destination.to}
              destination={destination}
              active={active?.to === destination.to}
              onNavigate={onNavigate}
            />
          ))}
        </div>

        <p className="group-label px-2.5 pb-1.5 pt-5 text-inverse-subtle">Set up</p>
        <div className="space-y-0.5">
          {WORKSPACE_SETUP_NAV.map((destination) => (
            <NavLink
              key={destination.to}
              destination={destination}
              active={active?.to === destination.to}
              onNavigate={onNavigate}
            />
          ))}
        </div>
      </nav>

      <div className="space-y-0.5 px-3 pb-3">
        {WORKSPACE_FOOTER_NAV.map((destination) => (
          <NavLink
            key={destination.to}
            destination={destination}
            active={active?.to === destination.to}
            onNavigate={onNavigate}
          />
        ))}
      </div>

      {/*
       * Plan and usage, at the foot of the rail.
       *
       * The limit was only ever visible by navigating to Settings and scrolling,
       * which is the one place you cannot see it from when it starts to matter:
       * the screen where you are about to create another tool. Builds are shown
       * beside live tools because that is the allowance a customer actually
       * runs out of mid-session.
       */}
      {entitlements && (
        <div className="space-y-3 border-t border-inverse-border px-4 py-3.5">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-xs font-medium text-inverse-foreground">
              {entitlements.plan.name}
            </span>
            {entitlements.status === "past_due" && (
              <span className="text-xs font-medium text-warning">Payment failed</span>
            )}
          </div>

          <UsageMeter
            label="Live tools"
            used={entitlements.usage.live_tools}
            limit={entitlements.plan.live_tool_limit}
            inverse
          />
          <UsageMeter
            label="Builds this month"
            used={entitlements.usage.builds_this_period}
            limit={entitlements.plan.monthly_build_limit}
            inverse
          />

          {/* Only when there is genuinely something above this plan. Asking the
              catalogue rather than testing for a hardcoded top tier is what stops
              a fourth plan silently hiding the link. */}
          {hasHigherPlan && (
            <Link
              to="/dashboard/settings"
              hash="billing"
              onClick={onNavigate}
              className="block text-xs font-medium text-brand-on-inverse hover:underline"
            >
              Upgrade plan
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
