import { Link, useNavigate } from "@tanstack/react-router";
import { CreditCard, LogOut, Settings, ShieldCheck } from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/lib/auth";

/** First letter of the local part — enough to identify one account to itself. */
function initial(email: string): string {
  return (email.trim()[0] ?? "?").toUpperCase();
}

/**
 * The account control, top-right.
 *
 * It replaces a raw email address printed as body text next to a bare
 * icon-only sign-out button. Both were unlabelled, neither was grouped, and
 * the email — the longest string in the bar — was competing with the
 * navigation for attention while doing nothing at all.
 *
 * An avatar button opening a menu is the convention this app was the odd one
 * out for not following, and it gives destinations that had no home in the
 * chrome (billing, security) somewhere to live.
 */
export function AccountMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  if (!user) return null;

  const handleSignOut = async () => {
    await logout();
    navigate({ to: "/", replace: true });
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="flex size-9 shrink-0 items-center justify-center rounded-full bg-secondary text-sm font-semibold text-foreground transition-colors hover:bg-n-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        aria-label={`Account menu for ${user.email}`}
      >
        {initial(user.email)}
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" sideOffset={8} className="w-64">
        <div className="px-2 py-2">
          <p className="truncate text-sm font-medium text-foreground" title={user.email}>
            {user.email}
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {user.email_verified ? "Email confirmed" : "Email not confirmed yet"}
          </p>
        </div>

        <DropdownMenuSeparator />

        <DropdownMenuItem asChild>
          <Link to="/dashboard/settings" className="cursor-pointer">
            <Settings className="size-4" aria-hidden="true" />
            Settings
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link to="/dashboard/settings" hash="billing" className="cursor-pointer">
            <CreditCard className="size-4" aria-hidden="true" />
            Plan and billing
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link to="/dashboard/settings" hash="security" className="cursor-pointer">
            <ShieldCheck className="size-4" aria-hidden="true" />
            Security
          </Link>
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        <DropdownMenuItem onSelect={handleSignOut} className="cursor-pointer">
          <LogOut className="size-4" aria-hidden="true" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
