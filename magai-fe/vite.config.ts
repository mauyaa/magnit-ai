// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - tanstackStart, viteReact, tailwindcss, tsConfigPaths, nitro (build-only using cloudflare as a default target),
//     componentTagger (dev-only), VITE_* env injection, @ path alias, React/TanStack dedupe,
//     error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

export default defineConfig({
  tanstackStart: {
    server: { entry: "server" },
    // Route tests live beside the routes they cover. Without this the router
    // plugin treats each one as a route file, fails to find a Route export, and
    // prints a nine-line warning per test file on every single dev start.
    router: { routeFileIgnorePattern: "\\.(test|spec)\\.[jt]sx?$" },
  },
  nitro: {
    // Vercel by default; the Docker image builds a standalone Node server.
    preset: process.env.NITRO_PRESET ?? "vercel",
  },
  vite: {
    server: { port: 5173 },
  },
});
