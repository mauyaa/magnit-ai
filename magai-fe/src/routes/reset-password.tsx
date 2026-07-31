import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { Loader2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { z } from "zod";

import { AccountActionPanel } from "@/components/magnitai/AccountActionPanel";
import { api, ApiError } from "@/lib/api-client";
import { setTokens } from "@/lib/auth-storage";
import { MIN_PASSWORD_LENGTH, PASSWORD_HINT, passwordProblem } from "@/lib/password-policy";

const searchSchema = z.object({
  token: z.string().min(1).max(512).optional().catch(undefined),
});

export const Route = createFileRoute("/reset-password")({
  validateSearch: searchSchema,
  head: () => ({ meta: [{ title: "Set a new password · Magnitai" }] }),
  component: ResetPasswordPage,
});

interface TokenPair {
  access_token: string;
  refresh_token: string;
}

/**
 * Setting a new password from an emailed link.
 *
 * A successful reset returns a session, so the customer is signed straight in
 * rather than being handed back to a login form they have just proved they can
 * pass. The token is single-use: if it fails there is nothing to retry here, so
 * the failure offers a fresh link instead of the same form again.
 */
function ResetPasswordPage() {
  const { token } = Route.useSearch();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [password, setPassword] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (!token) {
    return (
      <AccountActionPanel
        tone="problem"
        title="Incomplete link"
        message="Open the link from your inbox directly — this one is missing its token."
      >
        <Link
          to="/forgot-password"
          className="flex h-11 w-full items-center justify-center rounded-xl bg-foreground px-5 text-sm font-semibold text-background transition hover:bg-ink-soft"
        >
          Request a new link
        </Link>
      </AccountActionPanel>
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);

    const problem = passwordProblem(password);
    setFieldError(problem);
    if (problem) return;

    setPending(true);
    try {
      const tokens = await api.post<TokenPair>(
        "/api/auth/reset-password",
        { token, new_password: password },
        { anonymous: true },
      );
      setTokens({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token });
      await queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      await navigate({ to: "/dashboard", replace: true });
    } catch (error) {
      setFormError(
        error instanceof ApiError && error.status === 400
          ? "This link has expired or has already been used."
          : error instanceof Error
            ? error.message
            : "We couldn't reset your password.",
      );
      setPending(false);
    }
  }

  return (
    <AccountActionPanel
      tone="idle"
      title="Set a new password"
      message="Choose something you haven't used here before."
    >
      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        {formError && (
          <p role="alert" className="text-xs text-destructive">
            {formError}{" "}
            <Link to="/forgot-password" className="underline underline-offset-4">
              Request a new link
            </Link>
            .
          </p>
        )}

        <div className="space-y-2">
          <label htmlFor="new-password" className="text-sm font-medium text-foreground">
            New password
          </label>
          <input
            id="new-password"
            name="new-password"
            type="password"
            autoComplete="new-password"
            required
            autoFocus
            minLength={MIN_PASSWORD_LENGTH}
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
              if (fieldError) setFieldError(null);
            }}
            aria-invalid={fieldError ? true : undefined}
            aria-describedby={fieldError ? "new-password-error" : "new-password-hint"}
            className={`h-11 w-full rounded-xl border bg-background px-4 text-sm text-foreground outline-none transition focus:bg-card focus:ring-4 focus:ring-foreground/[0.04] ${
              fieldError ? "border-destructive" : "border-border-strong focus:border-foreground/50"
            }`}
          />
          {fieldError ? (
            <p id="new-password-error" role="alert" className="text-xs text-destructive">
              {fieldError}
            </p>
          ) : (
            <p id="new-password-hint" className="text-xs leading-5 text-muted-foreground">
              {PASSWORD_HINT}
            </p>
          )}
        </div>

        <button
          type="submit"
          disabled={pending}
          className="flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-foreground px-5 text-sm font-semibold text-background transition hover:bg-ink-soft disabled:pointer-events-none disabled:opacity-55"
        >
          {pending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
          Save and sign in
        </button>
      </form>
    </AccountActionPanel>
  );
}
