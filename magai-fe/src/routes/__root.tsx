import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  useRouterState,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";
import React, { useEffect, type ReactNode } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

import appCss from "../styles.css?url";
import { reportLovableError } from "../lib/lovable-error-reporting";
import { MagnitaiLogo } from "@/components/magnitai/ui/MagnitaiLogo";

function NotFoundComponent() {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-background px-4 font-sans text-foreground">
      <div className="surface-grid pointer-events-none fixed inset-0 z-0" />
      <div className="grain-overlay pointer-events-none fixed inset-0 z-0" />
      <div className="relative z-10 flex flex-col items-center text-center">
        <MagnitaiLogo className="mb-10" />
        <p className="font-mono text-sm font-medium text-muted-foreground">error 404</p>
        <h1 className="mt-3 font-heading text-6xl font-normal leading-none tracking-[-0.03em] sm:text-7xl">
          This page <span className="hero-accent">healed itself</span> right out of existence.
        </h1>
        <p className="mt-5 max-w-sm text-base font-medium text-muted-foreground">
          Whatever used to live at this URL isn't here anymore. Let's get you back to something real.
        </p>
        <Link
          to="/"
          className="group mt-8 inline-flex h-14 items-center justify-center gap-3 rounded-xl bg-primary py-1.5 pl-7 pr-1.5 text-sm font-bold text-primary-foreground shadow-sm transition-transform hover:-translate-y-0.5 active:scale-[0.97] active:translate-y-0"
        >
          Back to Magnitai
          <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-white/15 transition-transform duration-300 group-hover:translate-x-0.5">
            →
          </span>
        </Link>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();
  useEffect(() => {
    reportLovableError(error, { boundary: "tanstack_root_error_component" });
  }, [error]);

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-background px-4 font-sans text-foreground">
      <div className="surface-grid pointer-events-none fixed inset-0 z-0" />
      <div className="relative z-10 flex flex-col items-center text-center">
        <MagnitaiLogo className="mb-10" />
        <h1 className="font-heading text-4xl font-normal tracking-[-0.03em] text-foreground sm:text-5xl">
          This page didn't load.
        </h1>
        <p className="mt-4 max-w-sm text-base font-medium text-muted-foreground">
          Something went wrong on our end — not yours. Try again, or head back home.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="inline-flex h-12 items-center justify-center rounded-xl bg-primary px-6 text-sm font-bold text-primary-foreground shadow-sm transition-transform hover:-translate-y-0.5 active:scale-[0.97]"
          >
            Try again
          </button>
          <a
            href="/"
            className="inline-flex h-12 items-center justify-center rounded-xl border border-border bg-card px-6 text-sm font-bold text-foreground transition-colors hover:bg-secondary"
          >
            Go home
          </a>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "Magnitai · Self-Healing AI Widgets for Small Business" },
      {
        name: "description",
        content:
          "Magnitai builds, deploys, and self-heals on-brand interactive widgets — calculators, quizzes, and AI tools — so your site keeps converting even as it evolves.",
      },
      { name: "author", content: "Magnitai" },
      {
        property: "og:title",
        content: "Magnitai · Self-Healing AI Widgets for Small Business",
      },
      {
        property: "og:description",
        content:
          "Magnitai builds, deploys, and self-heals on-brand interactive widgets — calculators, quizzes, and AI tools — so your site keeps converting even as it evolves.",
      },
      { property: "og:type", content: "website" },
      { property: "og:image", content: "/new-logo.jpg?v=3" },
      { name: "twitter:card", content: "summary_large_image" },
      { name: "twitter:site", content: "@magnitai" },
      { name: "twitter:title", content: "Magnitai · Self-Healing AI Widgets" },
      {
        name: "twitter:description",
        content: "AI widgets that build themselves, stay on-brand, and self-heal.",
      },
      { name: "twitter:image", content: "/new-logo.jpg?v=3" },
      { name: "theme-color", content: "#fffaeb" },
    ],
    links: [
      { rel: "stylesheet", href: appCss },
      { rel: "icon", type: "image/jpeg", href: "/new-logo.jpg?v=3" },
      { rel: "apple-touch-icon", href: "/new-logo.jpg?v=3" },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootShell({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const shouldReduceMotion = useReducedMotion();

  return (
    <QueryClientProvider client={queryClient}>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={pathname}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: shouldReduceMotion ? 0 : 0.18, ease: [0.16, 1, 0.3, 1] }}
        >
          {/* Required: nested routes render here. Removing <Outlet /> breaks all child routes. */}
          <Outlet />
        </motion.div>
      </AnimatePresence>
    </QueryClientProvider>
  );
}
