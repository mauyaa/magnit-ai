import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { z } from "zod";

import { AccountActionPanel } from "@/components/magnitai/AccountActionPanel";
import { api, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";
import { loadSavedJourney } from "@/lib/journey-storage";

/**
 * The landing page for the link in the confirmation email.
 *
 * Verification is not a form: the customer already acted by clicking the link,
 * so this screen confirms the token immediately and its only job is to say
 * whether it worked and hand them back to whatever they were doing. The token
 * is single-use, which is why the request is fired exactly once even though
 * React mounts effects twice in development.
 */
const searchSchema = z.object({
  token: z.string().min(1).max(512).optional().catch(undefined),
});

export const Route = createFileRoute("/verify-email")({
  validateSearch: searchSchema,
  head: () => ({ meta: [{ title: "Confirm your email · Magnitai" }] }),
  component: VerifyEmailPage,
});

type State = "checking" | "confirmed" | "failed" | "missing";

function VerifyEmailPage() {
  const { token } = Route.useSearch();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isAuthenticated } = useAuth();

  const [state, setState] = useState<State>(token ? "checking" : "missing");
  const [reason, setReason] = useState<string | null>(null);
  const [resent, setResent] = useState<"idle" | "sending" | "sent" | "failed">("idle");
  const attempted = useRef(false);

  useEffect(() => {
    if (!token || attempted.current) return;
    attempted.current = true;

    void (async () => {
      try {
        await api.post("/api/auth/verify-email", { token }, { anonymous: true });
        // The signed-in user's `email_verified` flag just changed, and the build
        // and checkout gates read it — so the cached session has to be re-read
        // before we send them onward, or they hit the gate they just cleared.
        await queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
        setState("confirmed");
      } catch (error) {
        setReason(
          error instanceof ApiError && error.isOffline
            ? error.message
            : "This link has expired or has already been used.",
        );
        setState("failed");
      }
    })();
  }, [token, queryClient]);

  /** Back to the tool they were building, if there is one. */
  const destination = loadSavedJourney() ? "/build" : "/dashboard";

  async function resend() {
    setResent("sending");
    try {
      await api.post("/api/auth/resend-verification");
      setResent("sent");
    } catch {
      setResent("failed");
    }
  }

  if (state === "checking") {
    return <AccountActionPanel tone="working" title="Confirming…" message="This takes a moment." />;
  }

  if (state === "confirmed") {
    return (
      <AccountActionPanel
        tone="done"
        title="Email confirmed"
        message="Your account is fully active. You can build and publish."
      >
        <button
          type="button"
          onClick={() => navigate({ to: destination, replace: true })}
          className="group flex h-11 w-full items-center justify-between rounded-xl bg-foreground px-5 text-sm font-semibold text-background transition duration-200 hover:-translate-y-0.5 hover:bg-ink-soft hover:shadow-card"
        >
          <span>{destination === "/build" ? "Back to your tool" : "Open your workspace"}</span>
          <ArrowRight
            className="size-4 transition-transform group-hover:translate-x-0.5"
            aria-hidden="true"
          />
        </button>
      </AccountActionPanel>
    );
  }

  return (
    <AccountActionPanel
      tone="problem"
      title={state === "missing" ? "Incomplete link" : "Link no longer valid"}
      message={
        state === "missing"
          ? "Open the link from your inbox directly — this one is missing its token."
          : (reason ?? "This link has expired or has already been used.")
      }
    >
      {isAuthenticated ? (
        <button
          type="button"
          onClick={resend}
          disabled={resent === "sending" || resent === "sent"}
          className="flex h-11 w-full items-center justify-center rounded-xl bg-foreground px-5 text-sm font-semibold text-background transition hover:bg-ink-soft disabled:pointer-events-none disabled:opacity-55"
        >
          {resent === "sent" ? "New link sent" : "Send a new link"}
        </button>
      ) : (
        <Link
          to="/login"
          className="flex h-11 w-full items-center justify-center rounded-xl bg-foreground px-5 text-sm font-semibold text-background transition hover:bg-ink-soft"
        >
          Sign in to resend
        </Link>
      )}
      {resent === "failed" && (
        <p role="alert" className="mt-3 text-xs text-destructive">
          We couldn&rsquo;t send that. Try again in a moment.
        </p>
      )}
    </AccountActionPanel>
  );
}
