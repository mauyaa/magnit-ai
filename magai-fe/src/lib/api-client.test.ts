import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, apiRequest } from "./api-client";
import { clearTokens, getAccessToken, setTokens } from "./auth-storage";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiRequest", () => {
  beforeEach(() => {
    clearTokens();
  });

  it("attaches the bearer token when signed in", async () => {
    setTokens({ accessToken: "access-1", refreshToken: "refresh-1" });
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await api.get("/api/widgets");

    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer access-1");
  });

  it("omits the token for anonymous requests", async () => {
    setTokens({ accessToken: "access-1", refreshToken: "refresh-1" });
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    // Login must not send a stale token, or a 401 there becomes ambiguous.
    await api.post("/api/auth/login", { email: "a@b.com" }, { anonymous: true });

    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get("Authorization")).toBeNull();
  });

  it("translates API error codes into readable messages", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse({ detail: "invalid_credentials", request_id: "req-9" }, 401),
        ),
    );

    await expect(api.post("/api/auth/login", {}, { anonymous: true })).rejects.toMatchObject({
      message: "That email and password don't match.",
      status: 401,
      requestId: "req-9",
    });
  });

  it("surfaces the request id so users can quote it in support", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(jsonResponse({ detail: "internal_error", request_id: "req-42" }, 500)),
    );

    const error = await api.get("/api/widgets").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).requestId).toBe("req-42");
  });

  it("refreshes once on 401 and replays the original request", async () => {
    setTokens({ accessToken: "expired", refreshToken: "refresh-1" });

    const fetchMock = vi
      .fn()
      // Original request rejected because the access token expired.
      .mockResolvedValueOnce(jsonResponse({ detail: "not_authenticated" }, 401))
      // Refresh succeeds with a rotated pair.
      .mockResolvedValueOnce(jsonResponse({ access_token: "fresh", refresh_token: "refresh-2" }))
      // Replay succeeds.
      .mockResolvedValueOnce(jsonResponse({ widgets: [] }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await api.get<{ widgets: unknown[] }>("/api/widgets");

    expect(result).toEqual({ widgets: [] });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(getAccessToken()).toBe("fresh");
  });

  it("clears tokens when the refresh itself fails", async () => {
    setTokens({ accessToken: "expired", refreshToken: "stale" });

    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse({ detail: "not_authenticated" }, 401))
        .mockResolvedValueOnce(jsonResponse({ detail: "invalid_credentials" }, 401)),
    );

    await expect(api.get("/api/widgets")).rejects.toBeInstanceOf(ApiError);
    // Session is unrecoverable, so local state must not claim otherwise.
    expect(getAccessToken()).toBeNull();
  });

  it("does not attempt a refresh when there is no refresh token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: "not_authenticated" }, 401));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.get("/api/widgets")).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("de-duplicates concurrent refreshes", async () => {
    setTokens({ accessToken: "expired", refreshToken: "refresh-1" });

    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.endsWith("/api/auth/refresh")) {
        return Promise.resolve(jsonResponse({ access_token: "fresh", refresh_token: "refresh-2" }));
      }
      // Every protected call 401s until a refresh lands.
      return Promise.resolve(
        getAccessToken() === "fresh"
          ? jsonResponse({ ok: true })
          : jsonResponse({ detail: "not_authenticated" }, 401),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    await Promise.all([api.get("/api/widgets"), api.get("/api/payments"), api.get("/api/auth/me")]);

    // Refresh tokens are single-use: more than one refresh would log the user out.
    const refreshCalls = fetchMock.mock.calls.filter(([url]) =>
      String(url).endsWith("/api/auth/refresh"),
    );
    expect(refreshCalls).toHaveLength(1);
  });

  it("handles a non-JSON error body without throwing a parse error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("<html>502 Bad Gateway</html>", { status: 502 })),
    );

    await expect(api.get("/api/widgets")).rejects.toBeInstanceOf(ApiError);
  });

  it("returns undefined for 204 responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    await expect(apiRequest("/api/thing", { method: "DELETE" })).resolves.toBeUndefined();
  });

  it("flags rate-limited responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "rate_limit_exceeded" }, 429)),
    );

    const error = (await api.post("/api/widgets/analyze", {}).catch((e) => e)) as ApiError;
    expect(error.isRateLimited).toBe(true);
    expect(error.message).toContain("limit");
  });
});
