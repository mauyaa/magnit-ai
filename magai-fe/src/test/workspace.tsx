import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { render } from "@testing-library/react";
import type { FunctionComponent } from "react";

/**
 * Renders a signed-in workspace screen at its real path.
 *
 * Separate from `renderWithRouter`, which mounts a component at "/" and is
 * enough for marketing pages. Workspace screens need more: `WorkspaceSidebar`
 * highlights the active destination by reading the current pathname, so a page
 * rendered at "/" lights up nothing and any assertion about the rail is
 * meaningless. This mounts the component at the path it actually lives on.
 *
 * Every destination the shell links to has to exist as a route or the router
 * throws on an unmatched `to` before a single assertion runs. `/login` is
 * included because `RequireAuth` redirects there.
 */
const WORKSPACE_PATHS = [
  "/dashboard",
  "/dashboard/leads",
  "/dashboard/leads_/$leadId",
  "/dashboard/settings",
  "/dashboard/brand",
  "/dashboard/integrations",
  "/dashboard/help",
  "/dashboard/widgets/$widgetId",
  "/analytics",
  "/build",
  "/login",
];

export function renderWorkspaceRoute(Component: FunctionComponent, at: string) {
  const rootRoute = createRootRoute();

  const routes = WORKSPACE_PATHS.map((path) =>
    createRoute({
      getParentRoute: () => rootRoute,
      path,
      component: path === at ? Component : () => null,
    }),
  );

  const router = createRouter({
    routeTree: rootRoute.addChildren(routes),
    history: createMemoryHistory({ initialEntries: [at] }),
  });

  // retry:false so a rejected query surfaces as an error state immediately
  // rather than the test timing out behind three silent retries.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      {/* The generated route tree's types don't describe this ad-hoc tree. */}
      <RouterProvider router={router as never} />
    </QueryClientProvider>,
  );
}
