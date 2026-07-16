import { Link, useRouterState } from "@tanstack/react-router";
import { LayoutDashboard, Users } from "lucide-react";

export function DashboardNav() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  const tabs = [
    { id: "overview", label: "Overview", to: "/dashboard", icon: LayoutDashboard },
    { id: "leads", label: "Leads", to: "/dashboard/leads", icon: Users },
  ];

  return (
    <nav className="flex items-center gap-1 mb-10" aria-label="Dashboard sub-navigation">
      {tabs.map((tab) => {
        const active = tab.to === "/dashboard"
          ? pathname === "/dashboard"
          : pathname.startsWith(tab.to);
        const Icon = tab.icon;
        return (
          <Link
            key={tab.id}
            to={tab.to as "/dashboard" | "/dashboard/leads"}
            aria-current={active ? "page" : undefined}
            className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors ${
              active
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
            }`}
          >
            <Icon className="size-4" />
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
