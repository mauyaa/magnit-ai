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
 * Renders a single component inside a throwaway memory router.
 *
 * Components that use <Link> or useNavigate cannot be rendered bare, but
 * mounting the app's real route tree drags in auth, loaders, and the API — so a
 * failure anywhere would surface as a generic error boundary and quietly pass
 * assertions that only check for absent text. This gives the component the
 * router context it needs and nothing else.
 */
export function renderWithRouter(Component: FunctionComponent) {
  const rootRoute = createRootRoute();
  const indexRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/",
    component: Component,
  });
  // Every destination the components link to needs to exist, or the router
  // throws on an unmatched `to` before the assertion runs.
  const stubs = ["/build", "/how-it-works", "/examples", "/privacy", "/terms", "/dashboard"].map(
    (path) => createRoute({ getParentRoute: () => rootRoute, path, component: () => null }),
  );

  const router = createRouter({
    routeTree: rootRoute.addChildren([indexRoute, ...stubs]),
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });

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
