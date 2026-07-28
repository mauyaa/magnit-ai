import "@testing-library/jest-dom/vitest";

import { afterEach, beforeEach, vi } from "vitest";

// jsdom has no layout, so scroll restoration throws "Not implemented" on every
// router render. The stack traces are long enough to bury a real failure, and
// nothing under test depends on scrolling.
window.scrollTo = () => {};

beforeEach(() => {
  // Tokens live in sessionStorage; a leaked token between tests would make
  // assertions about signed-in vs signed-out state unreliable.
  sessionStorage.clear();
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
