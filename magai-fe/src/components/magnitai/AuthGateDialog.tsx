import { AlertCircle, ArrowRight, Loader2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useAuth } from "@/lib/auth";
import { GoogleAuthButton } from "./GoogleAuthButton";

/** Mirrors the backend's MAGAI_PASSWORD_MIN_LENGTH default. */
const MIN_PASSWORD_LENGTH = 12;

/**
 * The account gate, taken in place.
 *
 * Choosing a direction used to navigate to /login, which threw away the one
 * thing that had just done the convincing: the concept on screen. The visitor
 * arrived at a generic sign-in form with no evidence of what they were signing
 * up for, and the back button took them out of the funnel rather than back to
 * the comparison.
 *
 * The gate itself is in the right place and stays there — it fires *after* the
 * work is visible and *before* anything is committed, which is the placement the
 * backend already names `value_before_gate`. What changes is that the value
 * stays on screen behind it, the chosen direction is named in the dialog, and
 * dismissing returns to the comparison with everything intact.
 */
export function AuthGateDialog({
  open,
  onOpenChange,
  conceptTitle,
  domain,
  intent = "concept",
  onAuthenticated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  conceptTitle: string | null;
  domain: string;
  onAuthenticated?: () => void;
  /**
   * Why the gate appeared, which decides what it says.
   *
   * "concept"   — they chose a direction and it needs somewhere to live.
   * "guided"    — they set a collaborative brief that needs a workspace before
   *               AI can build and save the result.
   * "autopilot" — they asked AI to make every decision, so the account is the
   *               destination where that result will appear.
   *
   * A gate that gives the same reason for both is the generic "please sign in"
   * that people bounce off, because it never says what they lose by leaving.
   */
  intent?: "concept" | "guided" | "autopilot";
}) {
  const { login, signup } = useAuth();
  const [mode, setMode] = useState<"signup" | "login">("signup");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = mode === "signup" ? signup : login;
  const isSignup = mode === "signup";

  function validate(): string | null {
    if (!email.trim()) return "Enter your email address.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return "That doesn't look like a valid email address.";
    }
    if (!password) return "Enter a password.";
    if (isSignup) {
      if (password.length < MIN_PASSWORD_LENGTH) {
        return `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
      }
      if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) {
        return "Include both letters and numbers.";
      }
    }
    return null;
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const invalid = validate();
    if (invalid) {
      setError(invalid);
      return;
    }
    setError(null);
    // `mutate` with callbacks, not an awaited `mutateAsync`: a rejected promise
    // in a bare submit handler is nobody's to catch.
    mutation.mutate(
      { email: email.trim(), password },
      {
        // The dialog does not navigate on success. The flow behind it notices
        // the session and claims the saved concept where it stands, so the
        // visitor lands back on their own direction rather than on a dashboard.
        onSuccess: () => {
          onOpenChange(false);
          onAuthenticated?.();
        },
        onError: (mutationError) =>
          setError(
            mutationError instanceof Error ? mutationError.message : "Something went wrong.",
          ),
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl font-normal tracking-[-0.035em]">
            {!isSignup
              ? "Welcome back"
              : intent === "guided"
                ? "Save your collaboration"
                : intent === "autopilot"
                  ? "Let Magnitai build it"
                  : "Save this direction"}
          </DialogTitle>
          <DialogDescription className="text-sm leading-6">
            {intent === "autopilot" ? (
              <>
                {isSignup ? "Create an account" : "Sign in"} and Magnitai will analyze{" "}
                {domain || "your website"}, choose the strongest direction, and add the result to
                your dashboard.
              </>
            ) : intent === "guided" ? (
              <>
                Your directions are ready. {isSignup ? "Create an account" : "Sign in"} and Magnitai
                will build them{domain ? <> for {domain}</> : null}. Your brief stays exactly as you
                set it.
              </>
            ) : conceptTitle ? (
              <>
                <span className="font-medium text-foreground">{conceptTitle}</span> for {domain} is
                ready. {isSignup ? "Create an account" : "Sign in"} to build and publish it.
              </>
            ) : (
              <>
                {isSignup ? "Create an account" : "Sign in"} to build and publish what we prepared
                for {domain}.
              </>
            )}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} noValidate className="grid gap-3">
          <GoogleAuthButton
            mode={mode}
            disabled={mutation.isPending}
            onSuccess={() => {
              onOpenChange(false);
              onAuthenticated?.();
            }}
            onError={setError}
          />

          <div className="flex items-center gap-3 py-1 text-[11px] text-muted-foreground">
            <span className="h-px flex-1 bg-border" />
            <span>or continue with email</span>
            <span className="h-px flex-1 bg-border" />
          </div>

          <label className="grid gap-1.5 text-sm font-medium text-foreground">
            Email
            <input
              type="email"
              autoComplete="email"
              autoFocus
              value={email}
              onChange={(event) => {
                setEmail(event.target.value);
                if (error) setError(null);
              }}
              className="h-11 w-full rounded-xl border border-border-strong bg-card px-3.5 text-sm font-normal text-foreground outline-none transition-[border-color] placeholder:text-n-400 focus:border-foreground/45"
              placeholder="you@company.com"
            />
          </label>

          <label className="grid gap-1.5 text-sm font-medium text-foreground">
            Password
            <input
              type="password"
              autoComplete={isSignup ? "new-password" : "current-password"}
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
                if (error) setError(null);
              }}
              className="h-11 w-full rounded-xl border border-border-strong bg-card px-3.5 text-sm font-normal text-foreground outline-none transition-[border-color] placeholder:text-n-400 focus:border-foreground/45"
              placeholder={isSignup ? `At least ${MIN_PASSWORD_LENGTH} characters` : ""}
            />
          </label>

          {error && (
            <p role="alert" className="flex items-start gap-2 text-sm text-destructive">
              <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={mutation.isPending}
            className="btn btn-primary mt-1 h-11 w-full text-sm"
          >
            {mutation.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            ) : null}
            {isSignup ? "Create account and continue" : "Sign in and continue"}
            <ArrowRight className="size-4" aria-hidden="true" />
          </button>

          <p className="text-center text-sm text-muted-foreground">
            {isSignup ? "Already have an account?" : "New to Magnitai?"}{" "}
            <button
              type="button"
              onClick={() => {
                setMode(isSignup ? "login" : "signup");
                setError(null);
              }}
              className="font-medium text-foreground underline underline-offset-4"
            >
              {isSignup ? "Sign in" : "Create one"}
            </button>
          </p>

          {/* Stated at the gate, where the hesitation actually is. */}
          <p className="text-center text-xs text-muted-foreground">
            {intent === "autopilot"
              ? "Nothing is published until you review and approve it."
              : intent === "guided"
                ? "Your brief stays intact. Nothing is published until you say so."
                : "Your direction is already saved. Nothing is published until you say so."}
          </p>
        </form>
      </DialogContent>
    </Dialog>
  );
}
