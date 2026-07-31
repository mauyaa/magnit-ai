import { AlertCircle, Check, Loader2 } from "lucide-react";
import type { ReactNode } from "react";

import { MagnitaiLogo } from "./ui/MagnitaiLogo";

/**
 * The frame every out-of-band account action shares.
 *
 * Verifying an address, asking for a reset link and setting a new password are
 * three different jobs, but from the customer's side they are the same moment:
 * they clicked something in an inbox and want to know, immediately, whether it
 * worked and what happens next. One frame, one status, one action — so the
 * answer is in the same place each time rather than being re-designed per page.
 */
export type AccountActionTone = "working" | "done" | "problem" | "idle";

const TONE_ICON: Record<AccountActionTone, ReactNode> = {
  working: <Loader2 className="size-4 animate-spin" aria-hidden="true" />,
  done: <Check className="size-4" aria-hidden="true" />,
  problem: <AlertCircle className="size-4" aria-hidden="true" />,
  idle: null,
};

const TONE_CLASS: Record<AccountActionTone, string> = {
  working: "bg-muted text-muted-foreground",
  done: "bg-brand text-foreground",
  problem: "bg-destructive/10 text-destructive",
  idle: "",
};

export function AccountActionPanel({
  tone,
  title,
  message,
  children,
}: {
  tone: AccountActionTone;
  title: string;
  /** One sentence. Anything longer belongs in the action, not the copy. */
  message: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex min-h-[100svh] items-center px-5 pb-12 pt-24 sm:px-6">
      <section className="mx-auto w-full max-w-[27rem]" aria-labelledby="account-action-title">
        <div className="flex justify-center">
          <MagnitaiLogo size="sm" showWordmark={false} />
        </div>

        <div className="mt-6 rounded-2xl border border-border bg-card p-6 shadow-card">
          {tone !== "idle" && (
            <span
              className={`grid size-9 place-items-center rounded-full ${TONE_CLASS[tone]}`}
              role={tone === "problem" ? "alert" : undefined}
            >
              {TONE_ICON[tone]}
            </span>
          )}

          <h1
            id="account-action-title"
            className={`font-heading text-[1.75rem] font-medium leading-[1.05] tracking-[-0.04em] text-foreground ${
              tone === "idle" ? "" : "mt-4"
            }`}
          >
            {title}
          </h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{message}</p>

          {children && <div className="mt-6">{children}</div>}
        </div>
      </section>
    </div>
  );
}
