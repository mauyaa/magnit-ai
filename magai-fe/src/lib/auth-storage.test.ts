import { describe, expect, it, vi } from "vitest";

import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  isAuthenticated,
  setTokens,
  subscribeToTokenChanges,
} from "./auth-storage";

describe("auth-storage", () => {
  it("round-trips a token pair", () => {
    setTokens({ accessToken: "a", refreshToken: "r" });
    expect(getAccessToken()).toBe("a");
    expect(getRefreshToken()).toBe("r");
    expect(isAuthenticated()).toBe(true);
  });

  it("reports signed out before any token is stored", () => {
    expect(getAccessToken()).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });

  it("clears both tokens", () => {
    setTokens({ accessToken: "a", refreshToken: "r" });
    clearTokens();
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });

  it("uses sessionStorage rather than localStorage", () => {
    setTokens({ accessToken: "a", refreshToken: "r" });
    // localStorage would persist the token indefinitely on a shared machine.
    expect(sessionStorage.length).toBeGreaterThan(0);
    expect(localStorage.length).toBe(0);
  });

  it("notifies subscribers when tokens change", () => {
    const listener = vi.fn();
    const unsubscribe = subscribeToTokenChanges(listener);

    setTokens({ accessToken: "a", refreshToken: "r" });
    expect(listener).toHaveBeenCalledTimes(1);

    clearTokens();
    expect(listener).toHaveBeenCalledTimes(2);

    unsubscribe();
    setTokens({ accessToken: "b", refreshToken: "r2" });
    expect(listener).toHaveBeenCalledTimes(2);
  });
});
