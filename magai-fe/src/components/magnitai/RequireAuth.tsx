import { useNavigate, useRouterState } from "@tanstack/react-router";
import { Loader2 } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";

import { useAuth } from "@/lib/auth";

/**
 * Gate for authenticated pages.
 *
 * Client-side only, and deliberately so: it improves the experience but is not
 * the security boundary. Every protected endpoint independently requires a valid
 * token, so bypassing this component reveals nothing — the API returns 401.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const { isAuthenticated, isLoading } = useAuth();
  const pathname = useRouterState({ select: (state) => state.location.href });
  // Freeze the protected destination. During a route transition this component
  // can briefly observe /login; using that moving value caused /login to become
  // its own redirect target and grow the query string forever.
  const destinationRef = useRef(pathname);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      navigate({
        to: "/login",
        search: { redirect: destinationRef.current },
        replace: true,
      });
    }
  }, [isAuthenticated, isLoading, navigate]);

  if (isLoading) {
    return (
      <div
        className="flex min-h-[60vh] items-center justify-center"
        role="status"
        aria-live="polite"
      >
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
        <span className="sr-only">Checking your session…</span>
      </div>
    );
  }

  if (!isAuthenticated) {
    // The effect above is redirecting; render nothing rather than flashing content.
    return null;
  }

  return <>{children}</>;
}
