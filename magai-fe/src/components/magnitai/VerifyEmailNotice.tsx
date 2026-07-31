import { MailCheck } from "lucide-react";
import { useState } from "react";

import { api } from "@/lib/api-client";

/**
 * The one blocker a customer cannot resolve on the screen they are on.
 *
 * Building and checkout both require a confirmed address. Stating that only
 * after the button is pressed leaves them holding an instruction with no
 * control attached — and if the original email never arrived, no way forward at
 * all. So the requirement is shown before it bites, and it carries the remedy.
 */
export function VerifyEmailNotice({ email }: { email: string }) {
  const [state, setState] = useState<"idle" | "sending" | "sent" | "failed">("idle");

  async function resend() {
    setState("sending");
    try {
      await api.post("/api/auth/resend-verification");
      setState("sent");
    } catch {
      setState("failed");
    }
  }

  return (
    <div className="mt-5 rounded-xl border border-border bg-secondary px-4 py-3">
      <div className="flex items-start gap-2.5">
        <MailCheck className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-foreground">Confirm {email} to publish</p>
          <p className="mt-0.5 text-xs leading-5 text-muted-foreground">
            {state === "sent"
              ? "New link sent. It can take a minute to arrive."
              : state === "failed"
                ? "We couldn't send that. Try again in a moment."
                : "Open the link we sent you. Everything here is saved."}
          </p>
        </div>
        <button
          type="button"
          onClick={resend}
          disabled={state === "sending" || state === "sent"}
          className="shrink-0 self-center rounded-lg border border-border-strong px-3 py-1.5 text-xs font-medium text-foreground transition hover:bg-card disabled:pointer-events-none disabled:opacity-55"
        >
          {state === "sending" ? "Sending" : state === "sent" ? "Sent" : "Resend"}
        </button>
      </div>
    </div>
  );
}
