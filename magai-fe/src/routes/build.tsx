import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { X } from "lucide-react";
import type { ReactNode } from "react";
import { z } from "zod";

import { CheckoutFlow } from "@/components/magnitai/CheckoutFlow";
import { Navigation } from "@/components/magnitai/Navigation";
import { MagnitaiLogo } from "@/components/magnitai/ui/MagnitaiLogo";
import { useAuth } from "@/lib/auth";

const searchSchema = z.object({
  site: z.string().max(2048).optional().catch(undefined),
});

export const Route = createFileRoute("/build")({
  validateSearch: searchSchema,
  head: () => ({ meta: [{ title: "New tool · Magnitai" }] }),
  // The first look is public; choosing and building are gated inside the flow.
  component: Build,
});

/**
 * Focused chrome for a customer who has already signed in.
 *
 * The flow is public up to the point of choosing, so a signed-out visitor
 * genuinely is on the marketing site and gets the marketing bar. Once someone
 * is signed in they are inside the product, and showing them "How it works" and
 * "Pricing" while they are building something is the same mistake the old
 * dashboard made — advertising to a customer who already bought.
 *
 * A wizard also should not offer the full rail: there is one job on this screen.
 * So the bar keeps only an unambiguous way out, which the flow otherwise lacks.
 */
function FocusedHeader() {
  return (
    <header className="fixed inset-x-0 top-0 z-50 flex h-16 items-center justify-between border-b border-border bg-background/85 px-4 backdrop-blur-xl sm:px-6 lg:px-8">
      <Link to="/dashboard" className="flex items-center gap-2.5" aria-label="Magnitai workspace">
        <MagnitaiLogo
          size="sm"
          showWordmark={false}
          variant="plain"
          className="isolate overflow-hidden rounded-[9px] bg-background [&_img]:mix-blend-multiply"
        />
        <span className="text-[15px] font-semibold tracking-[-0.02em]">magnitai</span>
      </Link>
      <Link to="/dashboard" className="btn btn-ghost h-9 px-3 text-sm">
        <X className="size-4" aria-hidden="true" />
        Exit
      </Link>
    </header>
  );
}

/**
 * Keep the flow mounted while authentication changes.
 *
 * The old route swapped between two different wrapper components after signup.
 * React correctly treated that as a new subtree, but the remount discarded the
 * pending website before the auth dialog could continue the build. The frame
 * and main slot now remain stable while only the header changes.
 */
export function BuildShell({
  isAuthenticated,
  children,
}: {
  isAuthenticated: boolean;
  children: ReactNode;
}) {
  return (
    <div
      className={`flex min-h-screen flex-col font-sans text-foreground ${
        isAuthenticated ? "bg-background" : "bg-cream"
      }`}
    >
      {isAuthenticated ? <FocusedHeader /> : <Navigation activeSection="checkout" />}
      <main className="flex-1">{children}</main>
    </div>
  );
}

function Build() {
  const navigate = useNavigate();
  const { site } = Route.useSearch();
  const { isAuthenticated } = useAuth();

  const flow = (
    <CheckoutFlow
      initialSite={site}
      onBuildStart={(widgetId) =>
        navigate({ to: "/build-story/$widgetId", params: { widgetId }, replace: true })
      }
      onBack={() => navigate({ to: isAuthenticated ? "/dashboard" : "/" })}
    />
  );

  return <BuildShell isAuthenticated={isAuthenticated}>{flow}</BuildShell>;
}
