import { describe, expect, it } from "vitest";

import { normalizeWebsiteUrl, websiteFieldValue } from "./website-url";

describe("website URL entry", () => {
  it("accepts the way a person normally types a website", () => {
    expect(normalizeWebsiteUrl("northsidedental.com/services")).toBe(
      "https://northsidedental.com/services",
    );
  });

  it("preserves a real protocol and removes fragments", () => {
    expect(normalizeWebsiteUrl("http://example.com/offer#pricing")).toBe(
      "http://example.com/offer",
    );
  });

  it("rejects incomplete or credential-bearing addresses", () => {
    expect(normalizeWebsiteUrl("localhost")).toBeNull();
    expect(normalizeWebsiteUrl("https://user:secret@example.com")).toBeNull();
  });

  it("keeps the visible field free of a duplicated protocol", () => {
    expect(websiteFieldValue("https://example.com/offer/")).toBe("example.com/offer");
  });
});
