import { describe, expect, it } from "vitest";

import { Route } from "./login";

/**
 * The sign-in route's search contract.
 *
 * `redirect` is the only place in the app where a URL from the query string is
 * later navigated to, which makes it the app's one candidate for an open
 * redirect: a link like `/login?redirect=https://evil.example` would otherwise
 * bounce a freshly-authenticated user straight off-site, with the trust of
 * having just signed in on the real domain.
 *
 * The schema is asserted directly rather than through a mounted screen. It is a
 * pure function guarding a security property, and testing it at that level means
 * every hostile shape can be enumerated cheaply instead of two or three being
 * sampled through the UI.
 */
/**
 * The route hands TanStack a zod schema rather than a function, and the router
 * accepts either — so the stored value is the schema object itself. Calling
 * whichever shape is present keeps this test valid if that ever changes.
 */
const schema = Route.options.validateSearch as
  | ((s: Record<string, unknown>) => Record<string, unknown>)
  | { parse: (s: Record<string, unknown>) => Record<string, unknown> };

const validate = (search: Record<string, unknown>): Record<string, unknown> =>
  typeof schema === "function" ? schema(search) : schema.parse(search);

describe("login search params · redirect", () => {
  it("keeps a same-site absolute path", () => {
    expect(validate({ redirect: "/dashboard/settings" })).toMatchObject({
      redirect: "/dashboard/settings",
    });
  });

  it.each([
    ["an absolute http URL", "http://evil.example/steal"],
    ["an absolute https URL", "https://evil.example/steal"],
    ["a protocol-relative URL", "//evil.example/steal"],
    ["a scheme-relative URL with credentials", "//user:pass@evil.example"],
    ["a javascript: URL", "javascript:alert(1)"],
    ["a data: URL", "data:text/html,<script>alert(1)</script>"],
    ["a bare hostname", "evil.example"],
    ["a relative path", "dashboard"],
  ])("drops %s", (_label, hostile) => {
    // Dropped, not corrected: an unusable value must not become a usable one.
    expect(validate({ redirect: hostile }).redirect).toBeUndefined();
  });

  it("drops a non-string redirect instead of throwing", () => {
    expect(validate({ redirect: 42 }).redirect).toBeUndefined();
    expect(validate({ redirect: null }).redirect).toBeUndefined();
  });

  it("is absent when not supplied", () => {
    expect(validate({}).redirect).toBeUndefined();
  });
});

describe("login search params · mode", () => {
  it.each(["login", "signup"])("accepts %s", (mode) => {
    expect(validate({ mode }).mode).toBe(mode);
  });

  it("falls back to undefined for anything else, so the form opens on sign-in", () => {
    expect(validate({ mode: "admin" }).mode).toBeUndefined();
    expect(validate({ mode: 7 }).mode).toBeUndefined();
  });
});

describe("login route", () => {
  it("titles the page", () => {
    const head = Route.options.head as () => { meta: Array<{ title: string }> };
    expect(head().meta[0].title).toBe("Sign in · Magnitai");
  });
});
