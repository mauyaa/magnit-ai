/// <reference types="vitest" />
// Kept separate from vite.config.ts: that file is produced by
// @lovable.dev/vite-tanstack-config, which owns the app's plugin list. Tests only
// need path resolution and a DOM, not the full Start/Nitro pipeline.
import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    // Vitest defaults to 5s. Several specs drive real typing through
    // userEvent, which dispatches a full event sequence per character and is
    // slow under jsdom — slow enough that adding v8 coverage instrumentation
    // alone pushed GuidedBuilder past the limit. The work is legitimate, so the
    // budget is raised rather than the interaction faked, and CI runners are
    // slower than a dev machine.
    testTimeout: 15_000,
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      // `src/routes/**` is included deliberately. It used to be omitted, which
      // reported healthy coverage while every screen in the product sat at zero
      // — and that is where the leads page shipped a crash. Generated and
      // third-party-shaped files stay out: they are not ours to test.
      include: ["src/lib/**", "src/components/magnitai/**", "src/routes/**"],
      exclude: ["src/routeTree.gen.ts"],
    },
  },
});
