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
import type { ReactNode } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

import appCss from "../styles.css?url";
import { MagnitaiLogo } from "@/components/magnitai/ui/MagnitaiLogo";
import { AuthProvider } from "@/lib/auth";

function NotFoundComponent() {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-background px-4 font-sans text-foreground">
      <div className="surface-grid pointer-events-none fixed inset-0 z-0" />
      <div className="grain-overlay pointer-events-none fixed inset-0 z-0" />
      <div className="relative z-10 flex flex-col items-center text-center">
        <MagnitaiLogo className="mb-10" />
        <p className="font-mono text-sm text-muted-foreground">error 404</p>
        <h1 className="text-display mt-3">There's nothing at this address.</h1>
        <p className="text-body mt-5 max-w-sm text-muted-foreground">
          Whatever used to live here isn't here anymore. Let's get you back to something real.
        </p>
        <Link to="/" className="btn btn-accent mt-8">
          Back to Magnitai
        </Link>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  // Left in place deliberately: this is the last stop before a blank page, and
  // the browser console is the only reporter this app has on the client.
  console.error(error);
  const router = useRouter();

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-background px-4 font-sans text-foreground">
      <div className="surface-grid pointer-events-none fixed inset-0 z-0" />
      <div className="relative z-10 flex flex-col items-center text-center">
        <MagnitaiLogo className="mb-10" />
        <h1 className="text-title text-foreground">This page didn't load.</h1>
        <p className="text-body mt-4 max-w-sm text-muted-foreground">
          Something went wrong on our end — not yours. Try again, or head back home.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="btn btn-accent"
          >
            Try again
          </button>
          <a href="/" className="btn btn-secondary">
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
      { property: "og:image", content: "/magnit-logo-cropped.png" },
      { property: "og:image:width", content: "934" },
      { property: "og:image:height", content: "690" },
      { name: "twitter:card", content: "summary_large_image" },
      { name: "twitter:site", content: "@magnitai" },
      { name: "twitter:title", content: "Magnitai · Self-Healing AI Widgets" },
      {
        name: "twitter:description",
        content: "AI widgets that build themselves, stay on-brand, and self-heal.",
      },
      { name: "twitter:image", content: "/magnit-logo-cropped.png" },
      { name: "theme-color", content: "#fffaeb" },
    ],
    links: [
      { rel: "stylesheet", href: appCss },
      {
        rel: "icon",
        type: "image/png",
        sizes: "1254x1254",
        href: "/magnit-logo.png?v=2",
      },
      { rel: "apple-touch-icon", href: "/magnit-logo.png" },
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
      {/* Inside the query provider: the auth context uses React Query for /me. */}
      <AuthProvider>
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
      </AuthProvider>
    </QueryClientProvider>
  );
}
