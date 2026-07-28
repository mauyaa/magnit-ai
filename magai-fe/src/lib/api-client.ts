/**
 * HTTP client for the MagnetAI API.
 *
 * Responsibilities that would otherwise be duplicated in every hook:
 *  - attach the bearer token
 *  - transparently refresh once on a 401 and replay the original request
 *  - de-duplicate concurrent refreshes so a burst of 401s triggers one refresh
 *  - surface the API's `detail` field as a readable Error, with the request id
 */

import { clearTokens, getAccessToken, getRefreshToken, setTokens } from "./auth-storage";

export const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

/**
 * What the API sends with a 402: the capability that is locked and the cheapest
 * plan that unlocks it. Carried on the error so a screen can render a real
 * upgrade prompt instead of a dead end.
 */
export interface UpgradeRequirement {
  feature?: string;
  limit?: string;
  limitValue?: number;
  plan?: string;
  planName?: string;
  monthlyPrice?: number;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly requestId?: string,
    readonly upgrade?: UpgradeRequirement,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** True when the caller should be sent back to the login screen. */
  get isAuthError(): boolean {
    return this.status === 401;
  }

  /** The request never reached the server. */
  get isOffline(): boolean {
    return this.status === 0;
  }

  get isRateLimited(): boolean {
    return this.status === 429;
  }

  /** The plan does not cover this, but a higher one would. */
  get needsUpgrade(): boolean {
    return this.status === 402 && this.upgrade !== undefined;
  }
}

/** Human-readable text for the error codes the API returns. */
const ERROR_MESSAGES: Record<string, string> = {
  not_authenticated: "Please sign in to continue.",
  invalid_credentials: "That email and password don't match.",
  account_disabled: "This account has been disabled.",
  email_already_registered: "An account with that email already exists.",
  google_auth_not_configured: "Google sign-in is not available yet.",
  invalid_google_credential: "Google could not verify that sign-in. Please try again.",
  google_identity_conflict: "That email is linked to a different Google account.",
  incorrect_password: "That password is incorrect.",
  widget_not_found: "We couldn't find that widget.",
  widget_not_ready: "This widget isn't ready to build yet.",
  widget_not_failed: "Only a failed build can be retried.",
  widget_build_not_found: "There's no saved build to deploy. Build it first.",
  no_previous_deployment: "There's no earlier deployment to roll back to.",
  invalid_blueprint_index: "That widget option is no longer available.",
  lead_cap_reached: "This widget has reached its lead limit.",
  rate_limit_exceeded: "You've hit the limit for now — please try again shortly.",
  build_queue_unavailable: "The build queue is temporarily unavailable. Try again soon.",
  database_unavailable: "We're having trouble reaching our database. Try again shortly.",
  internal_error: "Something went wrong on our end. Please try again.",
  request_body_too_large: "That request was too large.",
  validation_error: "Please check the highlighted fields and try again.",
  guest_session_invalid: "That saved concept has expired. Start a fresh first look.",
  concept_generation_incomplete: "We couldn't complete both directions. Please try again.",
  generation_unavailable:
    "AI generation is at capacity right now. Please wait a moment and try again.",
  email_verification_required: "Check your inbox and verify your email before building.",
  payment_required: "Complete checkout before launching this tool.",
  payment_provider_error: "Secure checkout is temporarily unavailable.",
  subscription_already_active: "This workspace already has an active plan.",
  owner_required: "Only the workspace owner can make this change.",
  admin_required: "Only an owner or admin can make this change.",
  already_a_member: "That person is already part of this workspace.",
  already_in_a_workspace: "That account already belongs to another workspace.",
  invalid_or_expired_invite: "This invitation is invalid or has expired.",
  invite_email_mismatch: "Sign in with the email address that received this invitation.",
  email_delivery_failed: "We couldn't send the invitation. Please try again.",
  api_key_not_found: "That API key no longer exists.",
  invalid_api_key: "That API key is invalid or has expired.",
  invalid_domain: "Enter a valid hostname, such as tools.example.com.",
  domain_in_use: "That domain is already connected.",
  domain_not_found: "That domain no longer exists.",
  widget_not_deployed: "Publish this tool before connecting a custom domain.",
  domain_provider_error: "The domain provider couldn't complete that request. Please try again.",
};

/** The shape the 402 handler sends. Structured, so it can be acted on. */
interface UpgradeDetail {
  error: "upgrade_required";
  feature?: string;
  limit?: string;
  limit_value?: number;
  upgrade_to?: { plan: string; name: string; monthly_price: number } | null;
}

interface ErrorBody {
  detail?: string | UpgradeDetail | { msg?: string }[];
  request_id?: string;
  errors?: { field: string; message: string }[];
}

/** Readable copy for a locked capability, named after what it unlocks. */
const FEATURE_LABELS: Record<string, string> = {
  lead_capture: "capturing leads",
  lead_notifications: "lead notifications",
  lead_pipeline: "lead statuses and notes",
  csv_export: "exporting leads",
  webhook_delivery: "webhook delivery",
  crm_integrations: "CRM and marketing integrations",
  brand_kit: "the brand kit",
  outcome_editor: "editing results",
  question_editor: "editing questions",
  advanced_analytics: "advanced analytics",
  self_healing: "automatic repair",
  priority_support: "priority support",
  custom_domains: "custom domains",
  api_access: "API access",
};

const LIMIT_LABELS: Record<string, string> = {
  monthly_builds: "You've used every build on your plan this month.",
  live_tools: "Every live tool slot on your plan is in use.",
};

function isUpgradeDetail(detail: unknown): detail is UpgradeDetail {
  return (
    typeof detail === "object" &&
    detail !== null &&
    (detail as { error?: string }).error === "upgrade_required"
  );
}

function upgradeMessage(detail: UpgradeDetail): string {
  const target = detail.upgrade_to ? ` ${detail.upgrade_to.name} includes it.` : "";
  if (detail.limit) {
    return `${LIMIT_LABELS[detail.limit] ?? "You've reached a limit on your plan."}${target}`;
  }
  const capability = FEATURE_LABELS[detail.feature ?? ""] ?? "this feature";
  return `Your plan doesn't include ${capability}.${target}`;
}

async function toApiError(response: Response): Promise<ApiError> {
  let body: ErrorBody = {};
  try {
    body = (await response.json()) as ErrorBody;
  } catch {
    // Non-JSON error (proxy timeout, gateway page) — fall back to the status.
  }

  // A locked capability is not a failure to explain away: it is a state with a
  // named remedy, so the remedy travels with the error rather than being
  // reconstructed by whichever screen happens to catch it.
  if (isUpgradeDetail(body.detail)) {
    return new ApiError(upgradeMessage(body.detail), response.status, body.request_id, {
      feature: body.detail.feature,
      limit: body.detail.limit,
      limitValue: body.detail.limit_value,
      plan: body.detail.upgrade_to?.plan,
      planName: body.detail.upgrade_to?.name,
      monthlyPrice: body.detail.upgrade_to?.monthly_price,
    });
  }

  const code = typeof body.detail === "string" ? body.detail : "";
  let message = ERROR_MESSAGES[code] ?? code;

  if (!message && body.errors?.length) {
    message = body.errors.map((e) => e.message).join(", ");
  }
  if (!message) {
    message = response.statusText || `Request failed (${response.status})`;
  }

  return new ApiError(message, response.status, body.request_id);
}

// --- single-flight refresh -------------------------------------------------
// Several queries can 401 at the same moment; without this they would each
// POST /refresh, and because refresh tokens are single-use all but one would
// fail and log the user out.
let refreshInFlight: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  const response = await fetch(`${API_BASE}/api/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!response.ok) {
    clearTokens();
    return false;
  }

  const tokens = (await response.json()) as {
    access_token: string;
    refresh_token: string;
  };
  setTokens({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token });
  return true;
}

function refreshOnce(): Promise<boolean> {
  refreshInFlight ??= refreshAccessToken().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  /** Skip the bearer token (used by login/signup). */
  anonymous?: boolean;
}

async function send(path: string, options: RequestOptions): Promise<Response> {
  const { body, anonymous, headers, ...rest } = options;

  const finalHeaders = new Headers(headers);
  if (body !== undefined) finalHeaders.set("Content-Type", "application/json");

  if (!anonymous) {
    const token = getAccessToken();
    if (token) finalHeaders.set("Authorization", `Bearer ${token}`);
  }

  try {
    return await fetch(`${API_BASE}${path}`, {
      ...rest,
      headers: finalHeaders,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    // fetch rejects with a bare TypeError ("Failed to fetch") when the server
    // is unreachable, offline, or blocked by CORS. That string must never
    // reach a customer — status 0 marks it as a transport failure.
    throw new ApiError("We couldn't reach the server. Check your connection and try again.", 0);
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response = await send(path, options);

  // One refresh-and-replay attempt. `anonymous` requests are excluded: a 401
  // from /login means bad credentials, not an expired token.
  if (response.status === 401 && !options.anonymous && getRefreshToken()) {
    if (await refreshOnce()) {
      response = await send(path, options);
    }
  }

  if (!response.ok) {
    const error = await toApiError(response);
    if (error.isAuthError && !options.anonymous) clearTokens();
    throw error;
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string, options: RequestOptions = {}) =>
    apiRequest<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options: RequestOptions = {}) =>
    apiRequest<T>(path, { ...options, method: "POST", body }),
  put: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: "PUT", body }),
  patch: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: "PATCH", body }),
  delete: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: "DELETE", body }),
};
