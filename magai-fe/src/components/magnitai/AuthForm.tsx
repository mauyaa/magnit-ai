import { AlertCircle, ArrowRight, Check, Loader2, LockKeyhole } from "lucide-react";
import { useState, type FormEvent } from "react";

import { useAuth } from "@/lib/auth";
import { GoogleAuthButton } from "./GoogleAuthButton";

/** Mirrors the backend's MAGAI_PASSWORD_MIN_LENGTH default. */
const MIN_PASSWORD_LENGTH = 12;

type Mode = "login" | "signup";

export interface AuthHandoff {
  domain: string;
  title: string;
  kind: string;
  primaryColor: string;
  backgroundColor: string;
  accentColor: string;
}

export function AuthForm({
  mode,
  onSuccess,
  onSwitchMode,
  contextMessage,
  handoff,
}: {
  mode: Mode;
  onSuccess: () => void;
  onSwitchMode: () => void;
  contextMessage?: string;
  handoff?: AuthHandoff | null;
}) {
  const { login, signup } = useAuth();
  const mutation = mode === "login" ? login : signup;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});
  const [formError, setFormError] = useState<string | null>(null);

  const validate = (): boolean => {
    const errors: { email?: string; password?: string } = {};

    if (!email.trim()) {
      errors.email = "Enter your email address.";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errors.email = "That doesn't look like a valid email address.";
    }

    if (!password) {
      errors.password = "Enter your password.";
    } else if (mode === "signup") {
      if (password.length < MIN_PASSWORD_LENGTH) {
        errors.password = `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
      } else if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) {
        errors.password = "Include both letters and numbers.";
      }
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    if (!validate()) return;

    try {
      await mutation.mutateAsync({ email: email.trim(), password });
      onSuccess();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Something went wrong.");
    }
  };

  const isSignup = mode === "signup";
  const handoffMessage = handoff
    ? `${handoff.domain} is ready. Continue to ${handoff.title}.`
    : contextMessage;

  return (
    <div className="flex min-h-[100svh] items-center px-5 pb-12 pt-24 sm:px-6">
      <section className="mx-auto w-full max-w-[29rem]" aria-labelledby="auth-title">
        <div className="text-center">
          <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
            Magnitai workspace
          </span>
          <h1
            id="auth-title"
            className="mt-4 font-heading text-[clamp(2.5rem,7vw,3.5rem)] font-medium leading-[0.98] tracking-[-0.055em] text-foreground"
          >
            {isSignup ? "Create your account" : "Welcome back"}
          </h1>
          <p className="mx-auto mt-3 max-w-sm text-sm leading-6 text-muted-foreground">
            {isSignup
              ? "Save your tools, publish when you are ready and keep every response in one place."
              : "Sign in to continue to your Magnitai workspace."}
          </p>
        </div>

        <div className="mt-6 rounded-2xl border border-border bg-card p-5 shadow-card">
          {handoffMessage && (
            <div className="mb-6 flex items-start gap-3 rounded-xl border border-brand-solid/15 bg-brand-wash px-4 py-3 text-xs leading-5 text-foreground">
              <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-brand text-foreground">
                <Check className="size-3" aria-hidden="true" />
              </span>
              <span>{handoffMessage}</span>
            </div>
          )}

          <GoogleAuthButton mode={mode} onSuccess={onSuccess} onError={setFormError} />
          <div className="my-4 flex items-center gap-3 text-[11px] text-muted-foreground">
            <span className="h-px flex-1 bg-border" />
            <span>or continue with email</span>
            <span className="h-px flex-1 bg-border" />
          </div>

          <form onSubmit={handleSubmit} noValidate className="space-y-4">
            {formError && (
              <div
                role="alert"
                className="flex items-start gap-2 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
              >
                <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                <span>{formError}</span>
              </div>
            )}

            <div className="space-y-2">
              <label htmlFor="auth-email" className="text-sm font-medium text-foreground">
                Email address
              </label>
              <input
                id="auth-email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value);
                  if (fieldErrors.email) {
                    setFieldErrors((current) => ({ ...current, email: undefined }));
                  }
                }}
                aria-invalid={fieldErrors.email ? true : undefined}
                aria-describedby={fieldErrors.email ? "auth-email-error" : undefined}
                className={`h-11 w-full rounded-xl border bg-background px-4 text-sm text-foreground outline-none transition focus:bg-card focus:ring-4 focus:ring-foreground/[0.04] ${
                  fieldErrors.email
                    ? "border-destructive"
                    : "border-border-strong focus:border-foreground/50"
                }`}
              />
              {fieldErrors.email && (
                <p id="auth-email-error" role="alert" className="text-xs text-destructive">
                  {fieldErrors.email}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <label htmlFor="auth-password" className="text-sm font-medium text-foreground">
                Password
              </label>
              <input
                id="auth-password"
                name="password"
                type="password"
                autoComplete={isSignup ? "new-password" : "current-password"}
                required
                value={password}
                onChange={(event) => {
                  setPassword(event.target.value);
                  if (fieldErrors.password) {
                    setFieldErrors((current) => ({ ...current, password: undefined }));
                  }
                }}
                aria-invalid={fieldErrors.password ? true : undefined}
                aria-describedby={
                  fieldErrors.password
                    ? "auth-password-error"
                    : isSignup
                      ? "auth-password-hint"
                      : undefined
                }
                className={`h-11 w-full rounded-xl border bg-background px-4 text-sm text-foreground outline-none transition focus:bg-card focus:ring-4 focus:ring-foreground/[0.04] ${
                  fieldErrors.password
                    ? "border-destructive"
                    : "border-border-strong focus:border-foreground/50"
                }`}
              />
              {fieldErrors.password ? (
                <p id="auth-password-error" role="alert" className="text-xs text-destructive">
                  {fieldErrors.password}
                </p>
              ) : (
                isSignup && (
                  <p id="auth-password-hint" className="text-xs leading-5 text-muted-foreground">
                    At least {MIN_PASSWORD_LENGTH} characters, including a number.
                  </p>
                )
              )}
            </div>

            <button
              type="submit"
              disabled={mutation.isPending}
              className="group flex h-11 w-full items-center justify-between rounded-xl bg-foreground px-5 text-sm font-semibold text-background transition duration-200 hover:-translate-y-0.5 hover:bg-ink-soft hover:shadow-card disabled:pointer-events-none disabled:opacity-55"
            >
              {mutation.isPending ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  {isSignup ? "Creating account…" : "Signing in…"}
                </span>
              ) : (
                <>
                  <span>{isSignup ? "Create account" : "Sign in"}</span>
                  <ArrowRight
                    className="size-4 transition-transform group-hover:translate-x-0.5"
                    aria-hidden="true"
                  />
                </>
              )}
            </button>
          </form>

          <div className="mt-5 flex items-center justify-center gap-2 border-t border-border pt-4 text-[11px] text-muted-foreground">
            <LockKeyhole className="size-3.5" aria-hidden="true" />
            Secure access to your private workspace
          </div>
        </div>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          {isSignup ? "Already have an account?" : "New to Magnitai?"}{" "}
          <button
            type="button"
            onClick={onSwitchMode}
            className="font-semibold text-foreground underline decoration-border-strong underline-offset-4 hover:decoration-foreground"
          >
            {isSignup ? "Sign in" : "Create an account"}
          </button>
        </p>

        {isSignup && (
          <p className="mx-auto mt-5 max-w-sm text-center text-[11px] leading-5 text-muted-foreground">
            By creating an account, you agree to the{" "}
            <a className="underline underline-offset-3 hover:text-foreground" href="/terms">
              Terms
            </a>{" "}
            and acknowledge the{" "}
            <a className="underline underline-offset-3 hover:text-foreground" href="/privacy">
              Privacy Policy
            </a>
            .
          </p>
        )}
      </section>
    </div>
  );
}
