import { createFileRoute, Link } from "@tanstack/react-router";
import { Loader2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { AccountActionPanel } from "@/components/magnitai/AccountActionPanel";
import { api } from "@/lib/api-client";

export const Route = createFileRoute("/forgot-password")({
  head: () => ({ meta: [{ title: "Reset your password · Magnitai" }] }),
  component: ForgotPasswordPage,
});

/**
 * Requesting a reset link.
 *
 * The acknowledgement is deliberately identical whether or not the address has
 * an account — the backend answers that way so this endpoint cannot be used to
 * discover who has one, and the screen has to keep that promise rather than
 * leak the difference through its copy.
 */
function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "failed">("idle");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim()) return;
    setState("sending");
    try {
      await api.post("/api/auth/forgot-password", { email: email.trim() }, { anonymous: true });
      setState("sent");
    } catch {
      setState("failed");
    }
  }

  if (state === "sent") {
    return (
      <AccountActionPanel
        tone="done"
        title="Check your inbox"
        message={`If ${email.trim()} has an account, a reset link is on its way. It expires shortly.`}
      >
        <Link
          to="/login"
          className="flex h-11 w-full items-center justify-center rounded-xl border border-border-strong px-5 text-sm font-semibold text-foreground transition hover:bg-muted"
        >
          Back to sign in
        </Link>
      </AccountActionPanel>
    );
  }

  return (
    <AccountActionPanel
      tone="idle"
      title="Reset your password"
      message="Enter the address on your account and we'll send a link."
    >
      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div className="space-y-2">
          <label htmlFor="forgot-email" className="text-sm font-medium text-foreground">
            Email address
          </label>
          <input
            id="forgot-email"
            name="email"
            type="email"
            autoComplete="email"
            required
            autoFocus
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="h-11 w-full rounded-xl border border-border-strong bg-background px-4 text-sm text-foreground outline-none transition focus:border-foreground/50 focus:bg-card focus:ring-4 focus:ring-foreground/[0.04]"
          />
        </div>

        {state === "failed" && (
          <p role="alert" className="text-xs text-destructive">
            We couldn&rsquo;t send that link. Try again in a moment.
          </p>
        )}

        <button
          type="submit"
          disabled={state === "sending"}
          className="flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-foreground px-5 text-sm font-semibold text-background transition hover:bg-ink-soft disabled:pointer-events-none disabled:opacity-55"
        >
          {state === "sending" && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
          Send reset link
        </button>

        <Link
          to="/login"
          className="block text-center text-sm text-muted-foreground underline decoration-border-strong underline-offset-4 hover:text-foreground"
        >
          Back to sign in
        </Link>
      </form>
    </AccountActionPanel>
  );
}
