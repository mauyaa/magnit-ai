import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { z } from "zod";

import { AppShell } from "@/components/magnitai/AppShell";
import { AuthForm, type AuthHandoff } from "@/components/magnitai/AuthForm";
import { useAuth } from "@/lib/auth";
import { journeyDomain, loadSavedJourney } from "@/lib/journey-storage";

/**
 * `redirect` carries where the user was heading before the guard bounced them.
 * It is validated as a same-site absolute path so it cannot be used as an
 * open-redirect into another origin.
 */
const searchSchema = z.object({
  redirect: z
    .string()
    .refine((value) => value.startsWith("/") && !value.startsWith("//"), {
      message: "redirect must be a same-site path",
    })
    .optional()
    .catch(undefined),
  mode: z.enum(["login", "signup"]).optional().catch(undefined),
});

export const Route = createFileRoute("/login")({
  validateSearch: searchSchema,
  head: () => ({ meta: [{ title: "Sign in · Magnitai" }] }),
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const { redirect, mode: initialMode } = Route.useSearch();
  const { isAuthenticated } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">(initialMode ?? "login");
  const [handoff, setHandoff] = useState<AuthHandoff | null>(null);

  const destination = redirect ?? "/dashboard";

  // Already signed in (or just signed in): don't leave them on the form.
  useEffect(() => {
    if (isAuthenticated) {
      navigate({ to: destination, replace: true });
    }
  }, [isAuthenticated, destination, navigate]);

  useEffect(() => {
    if (destination !== "/build") return;
    const saved = loadSavedJourney();
    if (!saved || saved.selectedIndex === null) return;
    const selected = saved.concepts[saved.selectedIndex];
    setHandoff({
      domain: journeyDomain(saved.target_url),
      title: selected.blueprint.title,
      kind: selected.blueprint.type.replaceAll("_", " "),
      primaryColor: selected.architect.brand.primary_color,
      backgroundColor: selected.architect.brand.background_color,
      accentColor: selected.architect.brand.accent_color,
    });
  }, [destination]);

  return (
    <AppShell activeSection="dashboard">
      <AuthForm
        mode={mode}
        onSuccess={() => navigate({ to: destination, replace: true })}
        onSwitchMode={() => setMode((current) => (current === "login" ? "signup" : "login"))}
        contextMessage={
          destination === "/build" ? "Your lead magnet is ready. Sign in to continue." : undefined
        }
        handoff={handoff}
      />
    </AppShell>
  );
}
