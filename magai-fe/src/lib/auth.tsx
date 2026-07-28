/**
 * Auth context: current user, sign-in/up/out, and session state.
 *
 * The signed-in user is fetched from `/api/auth/me` rather than decoded from the
 * JWT, so a token for a deleted or deactivated account resolves to "signed out"
 * instead of appearing valid client-side.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
} from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, ApiError } from "./api-client";
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens,
  subscribeToTokenChanges,
} from "./auth-storage";

export interface AuthUser {
  id: string;
  email: string;
  role: string;
  created_at: string;
  email_verified: boolean;
  mfa_enabled: boolean;
  /** Email me when one of my tools captures a lead. */
  notify_on_lead: boolean;
  display_name: string | null;
  workspace_name: string;
  workspace_timezone: string;
  workspace_id: string;
  notify_weekly_summary: boolean;
  notify_product_updates: boolean;
  labs_enabled: boolean;
}

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

interface Credentials {
  email: string;
  password: string;
}

interface GoogleCredential {
  credential: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  /** True until the initial session check resolves. */
  isLoading: boolean;
  isAuthenticated: boolean;
  login: UseMutationResult<TokenResponse, Error, Credentials>;
  signup: UseMutationResult<TokenResponse, Error, Credentials>;
  googleLogin: UseMutationResult<TokenResponse, Error, GoogleCredential>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** Tracks token presence so React re-renders when it changes. */
function useHasToken(): boolean {
  const [hasToken, setHasToken] = useState(false);

  useEffect(() => {
    const sync = () => setHasToken(getAccessToken() !== null);
    sync(); // Runs after hydration, so SSR and client markup agree.
    return subscribeToTokenChanges(sync);
  }, []);

  return hasToken;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const hasToken = useHasToken();

  const {
    data: user,
    isLoading,
    isFetched,
  } = useQuery<AuthUser | null>({
    queryKey: ["auth", "me"],
    queryFn: async () => {
      try {
        return await api.get<AuthUser>("/api/auth/me");
      } catch (error) {
        // A rejected token means signed out, not an application error.
        if (error instanceof ApiError && error.isAuthError) return null;
        throw error;
      }
    },
    enabled: hasToken,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const onAuthenticated = useCallback(
    async (tokens: TokenResponse) => {
      setTokens({
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
      });
      await queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
    },
    [queryClient],
  );

  const login = useMutation<TokenResponse, Error, Credentials>({
    mutationFn: (credentials) =>
      api.post<TokenResponse>("/api/auth/login", credentials, { anonymous: true }),
    onSuccess: onAuthenticated,
  });

  const signup = useMutation<TokenResponse, Error, Credentials>({
    mutationFn: (credentials) =>
      api.post<TokenResponse>("/api/auth/signup", credentials, { anonymous: true }),
    onSuccess: onAuthenticated,
  });

  const googleLogin = useMutation<TokenResponse, Error, GoogleCredential>({
    mutationFn: (credential) =>
      api.post<TokenResponse>("/api/auth/google", credential, { anonymous: true }),
    onSuccess: onAuthenticated,
  });

  const logout = useCallback(async () => {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      try {
        // Best effort: revoke server-side so the refresh token dies immediately.
        await api.post("/api/auth/logout", { refresh_token: refreshToken });
      } catch {
        // Network failure must still clear local state.
      }
    }
    clearTokens();
    // Drop every cached query: they may hold the previous tenant's data.
    queryClient.clear();
  }, [queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user: user ?? null,
      isLoading: hasToken && !isFetched && isLoading,
      isAuthenticated: Boolean(user),
      login,
      signup,
      googleLogin,
      logout,
    }),
    [user, hasToken, isFetched, isLoading, login, signup, googleLogin, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return context;
}
