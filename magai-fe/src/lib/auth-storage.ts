/**
 * Token storage and refresh coordination.
 *
 * Tokens live in `sessionStorage`, not `localStorage`: a token in localStorage
 * survives indefinitely on a shared machine, whereas sessionStorage is scoped to
 * the tab and cleared when it closes. httpOnly cookies would be stronger still,
 * but the API is a separate origin from the SPA, so cookie-based auth would need
 * cross-site cookies plus CSRF tokens — deliberately out of scope here, and
 * revisited in SECURITY.md.
 *
 * All access goes through this module so the storage mechanism can be swapped in
 * one place.
 */

const ACCESS_TOKEN_KEY = "magnitai.access_token";
const REFRESH_TOKEN_KEY = "magnitai.refresh_token";

export interface TokenPair {
  accessToken: string;
  refreshToken: string;
}

/** SSR and privacy-mode browsers can both make storage unavailable. */
function storage(): Storage | null {
  try {
    if (typeof window === "undefined") return null;
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function getAccessToken(): string | null {
  return storage()?.getItem(ACCESS_TOKEN_KEY) ?? null;
}

export function getRefreshToken(): string | null {
  return storage()?.getItem(REFRESH_TOKEN_KEY) ?? null;
}

export function setTokens({ accessToken, refreshToken }: TokenPair): void {
  const store = storage();
  if (!store) return;
  store.setItem(ACCESS_TOKEN_KEY, accessToken);
  store.setItem(REFRESH_TOKEN_KEY, refreshToken);
  notify();
}

export function clearTokens(): void {
  const store = storage();
  if (!store) return;
  store.removeItem(ACCESS_TOKEN_KEY);
  store.removeItem(REFRESH_TOKEN_KEY);
  notify();
}

export function isAuthenticated(): boolean {
  return getAccessToken() !== null;
}

// --- change notification ---------------------------------------------------
// Lets the auth context re-render when tokens change from anywhere, including
// the automatic refresh inside the API client.

type Listener = () => void;
const listeners = new Set<Listener>();

export function subscribeToTokenChanges(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function notify(): void {
  for (const listener of listeners) listener();
}
