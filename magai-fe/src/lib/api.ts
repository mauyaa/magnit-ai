/**
 * React Query hooks for the MagnetAI API.
 *
 * Every request goes through `api` in ./api-client, which attaches the bearer
 * token, refreshes it once on expiry, and normalizes errors.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, API_BASE } from "./api-client";
import { getAccessToken } from "./auth-storage";
import type { AuthUser } from "./auth";

// Re-exported so callers only ever need one import path for API access.
export { api, ApiError, API_BASE } from "./api-client";

// --- types -----------------------------------------------------------------

/**
 * Mirrors the backend's WidgetType enum. A union rather than `string` so a typo
 * in a request body fails at compile time instead of as a 422 at runtime.
 */
export type WidgetKind =
  | "roi_calculator"
  | "readiness_quiz"
  | "competitive_comparison"
  | "audit_tool"
  | "interactive_checklist";

export interface CreationBrief {
  mode: "autopilot" | "guided";
  /**
   * What the customer actually wants, in their own words.
   *
   * Every other field here is a choice between options we wrote down in
   * advance, which caps the product at what we thought of. This is the one
   * field that can describe a tool nobody anticipated, and the analyzer treats
   * it as the leading input rather than as a footnote.
   */
  intent: string;
  audience: string;
  goal:
    | "capture_qualified_leads"
    | "book_more_calls"
    | "educate_buyers"
    | "estimate_value"
    | "recommend_next_step";
  offer: string;
  visitor_question: string;
  preferred_type: WidgetKind | null;
  tone: "match_site" | "warm" | "direct" | "premium" | "technical" | "playful";
  result_style: "score" | "estimate" | "recommendation" | "comparison" | "action_plan";
  question_count: number;
  instructions: string;
}

export interface Blueprint {
  type: WidgetKind;
  title: string;
  description: string;
  rationale: string;
}

export interface WidgetData {
  id: string;
  title: string;
  widget_type: string;
  status: string;
  target_url: string;
  deployment_url: string | null;
  embed_code: string | null;
  leads_count: number;
  impressions_count: number;
  starts_count: number;
  completions_count: number;
  cta_clicks_count: number;
  /** Percentage, or null until the tool has been seen at least once. */
  conversion_rate: number | null;
  plan_tier: string;
  lead_cap: number;
  entitlement_status: "preview" | "checkout_pending" | "paid" | "complimentary";
  can_build: boolean;
  launch_settings: Record<string, unknown> | null;
  delivery_webhook_url: string | null;
  consent_text: string | null;
  creation_brief: CreationBrief | null;
  brand_tokens: Record<string, unknown> | null;
  visual_language: Record<string, unknown> | null;
  widget_logic: Record<string, unknown> | null;
  copywriting: Record<string, unknown> | null;
  design_tokens: Record<string, unknown> | null;
  build_stage: string | null;
  build_progress: number | null;
  build_error: string | null;
  created_at: string;
  deployed_at: string | null;
  last_heal_check_at: string | null;
  last_brand_check_at: string | null;
}

export interface LeadData {
  id: string;
  widget_id: string;
  email: string;
  name: string | null;
  score: number | null;
  answers: Record<string, unknown> | null;
  metadata: Record<string, unknown> | null;
  qualification_status: string | null;
  result_key: string | null;
  forwarded: boolean;
  forwarded_at: string | null;
  created_at: string;
  /** Owner-maintained follow-up state. See LeadStatus below. */
  status: "new" | "contacted" | "qualified" | "won" | "lost";
  tags: string[];
  contacted_at: string | null;
  note_count: number;
}

export interface HealEvent {
  id: string;
  check_type: "brand_drift" | "deploy_health";
  status: "detected" | "healing" | "healed" | "failed" | "no_drift";
  diff_summary: Record<string, { old: string; new: string }> | null;
  detected_at: string;
  healed_at: string | null;
}

export interface DeploymentRecord {
  id: string;
  deployment_url: string;
  trigger: string;
  is_current: boolean;
  created_at: string;
}

export interface BrandExtraction {
  primary_color: string;
  secondary_color: string;
  background_color: string;
  accent_color: string;
  font_headings: string;
  font_body: string;
  tone: string;
  logo_url: string | null;
}

export interface VisualLanguage {
  layout: string;
  spacing: string;
  card_style: string;
  border_radius: string;
  shadow_depth: string;
  button_style: string;
  decorative_elements: string;
  icon_style: string;
  visual_energy: string;
}

export interface ArchitectOutput {
  widget_type: WidgetKind;
  brand: BrandExtraction;
  visual_language: VisualLanguage;
  logic: {
    formula: string;
    variables: Array<Record<string, string>>;
    example_calculation: string;
  };
  copywriting: Record<string, unknown>;
  decision: DecisionSpec | null;
  claims: Array<{
    text: string;
    evidence_ref: string | null;
    requires_approval: boolean;
  }>;
}

export interface DecisionQuestion {
  id: string;
  label: string;
  help_text: string;
  input_type: "number" | "single_choice" | "boolean";
  required: boolean;
  options: string[];
  minimum: number | null;
  maximum: number | null;
  step: number | null;
  default: number | string | boolean | null;
  weight: number;
  option_scores: number[];
  true_score: number;
  evidence_ref: string | null;
}

export interface DecisionSpec {
  mechanism: "estimate" | "diagnose" | "advise";
  buyer_question: string;
  value_before_gate: string;
  qualification_goal: string;
  recommended_placement: string;
  questions: DecisionQuestion[];
  results: Array<{
    key: string;
    title: string;
    summary: string;
    recommendation: string;
    minimum_score: number | null;
    maximum_score: number | null;
  }>;
  calculation: {
    kind: "weighted_score" | "linear_estimate";
    output_label: string;
    output_format: "score" | "number" | "currency" | "percent";
    currency: string;
    decimals: number;
    constant: number;
    terms: Array<{ question_id: string; multiplier: number }>;
    clamp_min: number | null;
    clamp_max: number | null;
  };
  qualification_threshold: number;
  lead_gate: "after_value";
  primary_cta: string;
  evidence_refs: string[];
}

export interface AnalyzeResponse {
  widget_id: string;
  blueprints: Blueprint[];
}

export interface CuratedConcept {
  blueprint: Blueprint;
  architect: ArchitectOutput;
}

export interface GuestConceptsResponse {
  target_url: string;
  session_token: string;
  concepts: [CuratedConcept, CuratedConcept];
  brief: CreationBrief;
}

export interface ClaimGuestConceptResponse extends AnalyzeResponse {
  selected_index: number;
  selected_concept: ArchitectOutput;
  entitlement_status: string;
  can_build: boolean;
}

export interface FunnelData {
  views: number;
  starts: number;
  completions: number;
  results_viewed: number;
  cta_clicks: number;
  leads: number;
  start_rate: number | null;
  completion_rate: number | null;
  lead_rate: number | null;
  cta_rate: number | null;
  dropoff_by_step: Record<string, number>;
}

export interface PortfolioAnalytics {
  period_days: number;
  experiences: Array<{
    id: string;
    title: string;
    status: string;
    views: number;
    starts: number;
    completions: number;
    leads: number;
    conversion_rate: number | null;
  }>;
  daily: Array<{
    date: string;
    starts: number;
    completions: number;
    leads: number;
    cta_clicks: number;
  }>;
  sources: Array<{
    source: string;
    engaged_visitors: number;
    leads: number;
  }>;
  totals: Record<string, number>;
  rates: Record<string, number | null>;
  dropoff_by_step: Record<string, number>;
}

export interface BuildResponse {
  widget_id: string;
  iframe_url: string;
  status: string;
  embed_code: string;
}

export interface PaymentRecord {
  id: string;
  widget_id: string | null;
  amount: number;
  currency: string;
  status: string;
  created_at: string;
}

export interface SubscriptionData {
  plan: "free" | "studio" | "scale";
  status: "free" | "checkout_pending" | "active" | "past_due" | "canceled";
  active_experiences: number;
  experience_limit: number;
  monthly_price: number;
  currency: string;
  current_period_end: string | null;
}

// --- plans and entitlements ------------------------------------------------
//
// The server owns the plan catalogue. Nothing here restates a price, a limit or
// a feature list — the pricing page and the billing screen both render what the
// API says, which is what stops marketing and product drifting apart again.

/**
 * Mirrors the backend's `Feature` enum. A union rather than `string` so a
 * mistyped gate is a compile error instead of a permanently-locked screen that
 * nobody notices.
 */
export type PlanFeature =
  | "lead_capture"
  | "lead_notifications"
  | "lead_pipeline"
  | "csv_export"
  | "webhook_delivery"
  | "crm_integrations"
  | "brand_kit"
  | "outcome_editor"
  | "question_editor"
  | "advanced_analytics"
  | "self_healing"
  | "priority_support"
  | "custom_domains"
  | "api_access";

export interface PlanData {
  id: "free" | "studio" | "scale";
  name: string;
  tagline: string;
  monthly_price: number;
  currency: string;
  live_tool_limit: number;
  monthly_build_limit: number;
  lead_limit_per_tool: number;
  analytics_window_days: number;
  features: PlanFeature[];
  highlights: string[];
  purchasable: boolean;
}

export interface EntitlementsData {
  plan: PlanData;
  status: string;
  usage: { live_tools: number; total_tools: number; builds_this_period: number };
  allowance: {
    builds_remaining: number;
    live_tools_remaining: number;
    can_build: boolean;
    can_publish: boolean;
  };
  features: PlanFeature[];
  period_started_at: string;
  current_period_end: string | null;
  granted_widget_ids: string[];
}

// --- outcomes and questions -------------------------------------------------

export interface ScoreBand {
  key: string;
  label: string;
  minimum_score: number;
  maximum_score: number;
  importance: "high" | "medium" | "low";
  description: string;
  accent_color: string;
}

export interface AdviceBlock {
  text: string;
  band_key: string | null;
}

export interface EmailCapture {
  enabled: boolean;
  heading: string;
  subheading: string;
  button_label: string;
  placeholder: string;
  require_name: boolean;
  consent_text: string;
}

export interface NextStep {
  title: string;
  description: string;
  link_label: string;
  link_url: string;
}

export interface OutcomeConfig {
  bands: ScoreBand[];
  advice: AdviceBlock[];
  email_capture: EmailCapture;
  cta: { label: string; url: string; note: string };
  next_steps: NextStep[];
}

export interface ReadinessCheck {
  id: string;
  label: string;
  detail: string;
  done: boolean;
  action: string;
  blocking: boolean;
}

// --- integrations -----------------------------------------------------------

export interface ProviderField {
  name: string;
  label: string;
  help_text: string;
  kind: "text" | "secret" | "url";
  required: boolean;
  placeholder: string;
}

export interface IntegrationProvider {
  id: string;
  name: string;
  category: string;
  description: string;
  auth: "api_key" | "endpoint";
  setup_hint: string;
  docs_url: string;
  fields: ProviderField[];
  feature: PlanFeature;
  available: boolean;
}

export interface IntegrationData {
  id: string;
  provider: string;
  status: "connected" | "error" | "disabled";
  config: Record<string, string> | null;
  /** Never the credential — only enough of it to recognise. */
  credential_hint: string | null;
  endpoint_url: string | null;
  widget_ids: string[] | null;
  last_test_at: string | null;
  last_status_code: number | null;
  last_error: string | null;
  delivered_count: number;
  failed_count: number;
  created_at: string;
}

// --- lead follow-up ---------------------------------------------------------

export type LeadStatus = "new" | "contacted" | "qualified" | "won" | "lost";

export interface LeadNote {
  id: string;
  body: string;
  created_at: string;
}

export interface TimelineEntry {
  kind: string;
  title: string;
  detail: string;
  occurred_at: string;
  tone: "ok" | "pending" | "failed";
}

export interface LeadDetail {
  lead: LeadData;
  widget_title: string;
  widget_id: string;
  notes: LeadNote[];
  timeline: TimelineEntry[];
}

// --- workspace brand --------------------------------------------------------

export interface FontPairing {
  id: string;
  label: string;
  heading: string;
  body: string;
  note: string;
}

export interface WorkspaceBrand {
  accent_color: string | null;
  background_color: string | null;
  font_pairing: string | null;
  corner_radius: number | null;
  tone: "light" | "soft" | "deep" | null;
  logo_url: string | null;
  brand_personality: string | null;
  configured: boolean;
  font_pairings: FontPairing[];
}

export interface TeamMember {
  id: string;
  email: string;
  display_name: string | null;
  role: "owner" | "admin" | "member";
  joined_at: string;
  is_current_user: boolean;
}

export interface WorkspaceInvite {
  id: string;
  email: string;
  role: "admin" | "member";
  expires_at: string;
  created_at: string;
}

export interface TeamData {
  members: TeamMember[];
  invitations: WorkspaceInvite[];
  can_manage: boolean;
}

export interface WorkspaceApiKey {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
  expires_at: string | null;
}

export interface CreatedWorkspaceApiKey extends WorkspaceApiKey {
  /** Returned only once by the create endpoint. */
  key: string;
}

export interface CustomDomain {
  id: string;
  widget_id: string;
  hostname: string;
  status: "pending" | "verified" | "error";
  verification: Array<{
    type?: string;
    domain?: string;
    value?: string;
    reason?: string;
  }>;
  last_checked_at: string | null;
  last_error: string | null;
  created_at: string;
}

// --- queries ---------------------------------------------------------------

export function useWidgets() {
  return useQuery<{ widgets: WidgetData[] }>({
    queryKey: ["widgets"],
    queryFn: () => api.get("/api/widgets"),
    refetchInterval: 15_000,
  });
}

export function useWidget(id: string) {
  return useQuery<WidgetData>({
    queryKey: ["widget", id],
    queryFn: () => api.get(`/api/widgets/${id}`),
    enabled: !!id,
    // Poll only while a build is in flight, then stop.
    refetchInterval: (query) =>
      query.state.data?.status === "building" ||
      query.state.data?.entitlement_status === "checkout_pending"
        ? 3_000
        : false,
  });
}

export function useLeads(widgetId: string) {
  return useQuery<LeadData[]>({
    queryKey: ["leads", widgetId],
    queryFn: () => api.get(`/api/widgets/${widgetId}/leads`),
    enabled: !!widgetId,
  });
}

export function useAllLeads(widgetIds: string[]) {
  return useQuery<LeadData[]>({
    queryKey: ["all-leads", widgetIds],
    queryFn: async () => {
      const results = await Promise.allSettled(
        widgetIds.map((id) => api.get<LeadData[]>(`/api/widgets/${id}/leads`)),
      );
      return results.filter((r) => r.status === "fulfilled").flatMap((r) => r.value);
    },
    enabled: widgetIds.length > 0,
  });
}

export function useHealEvents(widgetId: string) {
  return useQuery<HealEvent[]>({
    queryKey: ["heal-events", widgetId],
    queryFn: () => api.get(`/api/widgets/${widgetId}/heal-events`),
    enabled: !!widgetId,
    refetchInterval: 60_000,
  });
}

export function useDeployments(widgetId: string) {
  return useQuery<DeploymentRecord[]>({
    queryKey: ["deployments", widgetId],
    queryFn: () => api.get(`/api/widgets/${widgetId}/deployments`),
    enabled: !!widgetId,
  });
}

export function usePayments() {
  return useQuery<PaymentRecord[]>({
    queryKey: ["payments"],
    queryFn: () => api.get("/api/payments"),
  });
}

export function useSubscription() {
  return useQuery<SubscriptionData>({
    queryKey: ["subscription"],
    queryFn: () => api.get("/api/payments/subscription"),
  });
}

export function useWidgetFunnel(widgetId: string) {
  return useQuery<FunnelData>({
    queryKey: ["widget-funnel", widgetId],
    queryFn: () => api.get(`/api/widgets/${widgetId}/funnel`),
    enabled: !!widgetId,
    refetchInterval: 30_000,
  });
}

export function usePortfolioAnalytics(periodDays = 30) {
  return useQuery<PortfolioAnalytics>({
    queryKey: ["portfolio-analytics", periodDays],
    queryFn: () => api.get(`/api/widgets/portfolio/analytics?period_days=${periodDays}`),
    refetchInterval: 30_000,
  });
}

// --- mutations -------------------------------------------------------------

export function useAnalyzeUrl() {
  return useMutation({
    mutationFn: (url: string) => api.post<AnalyzeResponse>("/api/widgets/analyze", { url }),
  });
}

export interface SiteRead {
  target_url: string;
  domain: string;
  business_name: string;
  summary: string;
  pages_read: number;
  signals_found: number;
  colors: string[];
  fonts: string[];
  highlights: string[];
}

/**
 * The crawl on its own — about five seconds, against roughly sixty for the
 * directions that follow.
 *
 * Split out so the wait has something true in it. A minute of blank screen is
 * where a first-time visitor leaves, and a spinner does not tell them their site
 * was read; their own headline and their own brand colours do.
 */
export function useReadSite() {
  return useMutation({
    mutationFn: (url: string) =>
      api.post<SiteRead>("/api/widgets/read-site", { url }, { anonymous: true }),
  });
}

/** One anonymous first look: two complete, site-specific directions. */
export function useGuestConcepts() {
  return useMutation({
    mutationFn: ({ url, brief }: { url: string; brief: CreationBrief }) =>
      api.post<GuestConceptsResponse>(
        "/api/widgets/guest-concepts",
        { url, brief },
        { anonymous: true },
      ),
  });
}

/** Save the chosen anonymous direction after the visitor creates an account. */
export function useClaimGuestConcept() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      sessionToken,
      selectedIndex,
    }: {
      sessionToken: string;
      selectedIndex: number;
    }) =>
      api.post<ClaimGuestConceptResponse>("/api/widgets/claim-guest", {
        session_token: sessionToken,
        selected_index: selectedIndex,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["widgets"] });
    },
  });
}

/**
 * The named shapes an owner can pick outright, with the analyzer's picks
 * flagged. Not the limit of what the pipeline builds — a tool described in the
 * brief's `intent` is built as itself and never appears in this list.
 */
export interface ToolType {
  kind: WidgetKind;
  label: string;
  visitor_does: string;
  best_for: string;
  suggested: boolean;
}

export function useToolTypes(widgetId: string | null) {
  return useQuery({
    queryKey: ["tool-types", widgetId],
    queryFn: () => api.get<{ tool_types: ToolType[] }>(`/api/widgets/${widgetId}/tool-types`),
    enabled: Boolean(widgetId),
    // The catalogue is per-widget only because of the `suggested` flags, which
    // are fixed once the site has been analyzed.
    staleTime: Infinity,
  });
}

/**
 * `widgetType` names a tool outright; `blueprintIndex` picks one of the three
 * the analyzer proposed. Sending a type wins, so a stale index can't undo an
 * explicit choice.
 */
export function useArchitectPreview() {
  return useMutation({
    mutationFn: ({
      widgetId,
      blueprintIndex,
      widgetType,
    }: {
      widgetId: string;
      blueprintIndex?: number;
      widgetType?: WidgetKind;
    }) =>
      api.post<ArchitectOutput>(`/api/widgets/${widgetId}/architect-preview`, {
        blueprint_index: blueprintIndex ?? 0,
        widget_type: widgetType ?? null,
      }),
  });
}

export function useBuildWidget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      widgetId,
      blueprintIndex,
      widgetType,
      skipDeploy,
      architectOverride,
    }: {
      widgetId: string;
      blueprintIndex?: number;
      widgetType?: WidgetKind;
      skipDeploy?: boolean;
      architectOverride?: ArchitectOutput;
    }) =>
      api.post<BuildResponse>("/api/widgets/build", {
        widget_id: widgetId,
        blueprint_index: blueprintIndex ?? 0,
        widget_type: widgetType ?? null,
        skip_deploy: skipDeploy ?? false,
        architect_override: architectOverride ?? null,
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["widgets"] });
      queryClient.invalidateQueries({ queryKey: ["widget", variables.widgetId] });
    },
  });
}

export function useCreateCheckout() {
  return useMutation({
    mutationFn: ({
      widgetId,
      successUrl,
      cancelUrl,
    }: {
      widgetId: string;
      successUrl: string;
      cancelUrl: string;
    }) =>
      api.post<{ checkout_url: string; session_id: string }>("/api/payments/create-checkout", {
        widget_id: widgetId,
        success_url: successUrl,
        cancel_url: cancelUrl,
      }),
  });
}

export function useCreateSubscriptionCheckout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      plan,
      successUrl,
      cancelUrl,
    }: {
      plan: "studio" | "scale";
      successUrl: string;
      cancelUrl: string;
    }) =>
      api.post<{ checkout_url: string; session_id: string }>(
        "/api/payments/create-subscription-checkout",
        {
          plan,
          success_url: successUrl,
          cancel_url: cancelUrl,
        },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subscription"] });
      queryClient.invalidateQueries({ queryKey: ["widgets"] });
    },
  });
}

export function useConfigureLaunch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      widgetId,
      targetPageUrl,
      ctaUrl,
      ctaLabel,
      deliveryWebhookUrl,
      deliveryMode,
      consentText,
    }: {
      widgetId: string;
      targetPageUrl?: string;
      ctaUrl?: string;
      ctaLabel?: string;
      deliveryWebhookUrl?: string;
      deliveryMode?: "custom" | "zapier" | "make" | "n8n";
      consentText?: string;
    }) =>
      api.put<{
        launch_settings: Record<string, unknown>;
        delivery_webhook_url: string | null;
        webhook_signing_secret: string | null;
        consent_text: string | null;
      }>(`/api/widgets/${widgetId}/launch`, {
        target_page_url: targetPageUrl || null,
        cta_url: ctaUrl || null,
        cta_label: ctaLabel || null,
        lead_fields: ["email", "name"],
        delivery_webhook_url: deliveryWebhookUrl || null,
        delivery_mode: deliveryMode ?? "custom",
        consent_text: consentText || null,
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["widget", variables.widgetId] });
    },
  });
}

export function useTestLaunchConnection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (widgetId: string) =>
      api.post<{
        connected: boolean;
        status_code: number | null;
        checked_at: string;
        message: string;
      }>(`/api/widgets/${widgetId}/launch/test`),
    onSuccess: (_data, widgetId) => {
      queryClient.invalidateQueries({ queryKey: ["widget", widgetId] });
    },
  });
}

/** Republish the current build to a fresh deployment. */
export function useDeployWidget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (widgetId: string) => api.post<BuildResponse>(`/api/widgets/${widgetId}/deploy`),
    onSuccess: (_data, widgetId) => {
      queryClient.invalidateQueries({ queryKey: ["widgets"] });
      queryClient.invalidateQueries({ queryKey: ["widget", widgetId] });
      queryClient.invalidateQueries({ queryKey: ["deployments", widgetId] });
    },
  });
}

/** Point the embed back at the previous deployment. Instant; no rebuild. */
export function useRollbackWidget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (widgetId: string) => api.post<BuildResponse>(`/api/widgets/${widgetId}/rollback`),
    onSuccess: (_data, widgetId) => {
      queryClient.invalidateQueries({ queryKey: ["widget", widgetId] });
      queryClient.invalidateQueries({ queryKey: ["deployments", widgetId] });
    },
  });
}

export function useRetryBuild() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (widgetId: string) => api.post<BuildResponse>(`/api/widgets/${widgetId}/retry`),
    onSuccess: (_data, widgetId) => {
      queryClient.invalidateQueries({ queryKey: ["widget", widgetId] });
    },
  });
}

/**
 * SSE URL for live build progress.
 *
 * `EventSource` cannot set headers, so the access token is passed as a query
 * parameter. The endpoint validates it and checks widget ownership before
 * streaming anything.
 */
export function buildEventsUrl(widgetId: string): string | null {
  const token = getAccessToken();
  if (!token) return null;
  return `${API_BASE}/api/widgets/${widgetId}/events?access_token=${encodeURIComponent(token)}`;
}

// --- plans, entitlements and gating ----------------------------------------

/** The public plan catalogue. Cached hard: it changes on a deploy, not per user. */
export function usePlans() {
  return useQuery<{ plans: PlanData[]; currency: string }>({
    queryKey: ["plans"],
    queryFn: () => api.get("/api/billing/plans", { anonymous: true }),
    staleTime: 10 * 60_000,
    // The public pricing page should recover quickly into its honest unavailable
    // state instead of hiding behind the default multi-retry delay.
    retry: 1,
  });
}

/**
 * What this workspace may do right now.
 *
 * Every gate in the app reads this one query, so a screen never has to work out
 * for itself what a plan includes — and an upgrade taking effect invalidates a
 * single cache entry rather than each screen's private idea of the plan.
 */
export function useEntitlements() {
  return useQuery<EntitlementsData>({
    queryKey: ["entitlements"],
    queryFn: () => api.get("/api/billing/entitlements"),
    staleTime: 30_000,
  });
}

// --- outcomes and question flow ---------------------------------------------

export function useOutcomes(widgetId: string) {
  return useQuery<{ config: OutcomeConfig; customised: boolean }>({
    queryKey: ["outcomes", widgetId],
    queryFn: () => api.get(`/api/widgets/${widgetId}/outcomes`),
    enabled: !!widgetId,
  });
}

export function useSaveOutcomes(widgetId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (config: OutcomeConfig) =>
      api.put<{ config: OutcomeConfig; customised: boolean }>(`/api/widgets/${widgetId}/outcomes`, {
        config,
      }),
    onSuccess: (data) => {
      // Written straight into the cache rather than refetched: the editor is a
      // controlled form, and a refetch round trip would let it flash back to the
      // previous values between the save landing and the response arriving.
      queryClient.setQueryData(["outcomes", widgetId], data);
      queryClient.invalidateQueries({ queryKey: ["readiness", widgetId] });
    },
  });
}

export function useResetOutcomes(widgetId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      api.delete<{ config: OutcomeConfig; customised: boolean }>(
        `/api/widgets/${widgetId}/outcomes`,
      ),
    onSuccess: (data) => queryClient.setQueryData(["outcomes", widgetId], data),
  });
}

export function useDecision(widgetId: string) {
  return useQuery<{ decision: DecisionSpec | null; editable: boolean }>({
    queryKey: ["decision", widgetId],
    queryFn: () => api.get(`/api/widgets/${widgetId}/decision`),
    enabled: !!widgetId,
  });
}

export function useSaveDecision(widgetId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (decision: DecisionSpec) =>
      api.put<{ decision: DecisionSpec; editable: boolean }>(`/api/widgets/${widgetId}/decision`, {
        decision,
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(["decision", widgetId], data);
      queryClient.invalidateQueries({ queryKey: ["widget", widgetId] });
      queryClient.invalidateQueries({ queryKey: ["readiness", widgetId] });
      // The result screen derives its bands from the questions, so a flow edit
      // can change what the outcomes editor should be showing.
      queryClient.invalidateQueries({ queryKey: ["outcomes", widgetId] });
    },
  });
}

export function useReadiness(widgetId: string) {
  return useQuery<{
    ready: boolean;
    completed: number;
    total: number;
    checks: ReadinessCheck[];
  }>({
    queryKey: ["readiness", widgetId],
    queryFn: () => api.get(`/api/widgets/${widgetId}/readiness`),
    enabled: !!widgetId,
  });
}

// --- integrations -----------------------------------------------------------

export function useIntegrationCatalog() {
  return useQuery<{ providers: IntegrationProvider[] }>({
    queryKey: ["integration-catalog"],
    queryFn: () => api.get("/api/integrations/catalog"),
    staleTime: 5 * 60_000,
  });
}

export function useIntegrations() {
  return useQuery<{ integrations: IntegrationData[] }>({
    queryKey: ["integrations"],
    queryFn: () => api.get("/api/integrations"),
  });
}

export function useConnectIntegration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      provider: string;
      values: Record<string, string>;
      widgetIds?: string[] | null;
    }) =>
      api.post<IntegrationData>("/api/integrations", {
        provider: input.provider,
        values: input.values,
        widget_ids: input.widgetIds ?? null,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["integrations"] }),
  });
}

export function useUpdateIntegration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: string; enabled?: boolean; widgetIds?: string[] | null }) => {
      const body: Record<string, unknown> = {};
      if (input.enabled !== undefined) body.enabled = input.enabled;
      // Only sent when the caller means to change the scope: the server treats a
      // present-but-null value as "every tool", which is a real instruction and
      // not the same as leaving the scope alone.
      if ("widgetIds" in input) body.widget_ids = input.widgetIds ?? null;
      return api.patch<IntegrationData>(`/api/integrations/${input.id}`, body);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["integrations"] }),
  });
}

export function useTestIntegration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.post<{ ok: boolean; status_code: number | null; message: string; checked_at: string }>(
        `/api/integrations/${id}/test`,
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["integrations"] }),
  });
}

export function useDisconnectIntegration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/api/integrations/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["integrations"] }),
  });
}

// --- lead follow-up ---------------------------------------------------------

export function useLeadDetail(leadId: string) {
  return useQuery<LeadDetail>({
    queryKey: ["lead", leadId],
    queryFn: () => api.get(`/api/leads/${leadId}/detail`),
    enabled: !!leadId,
  });
}

export function useUpdateLead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { leadId: string; status?: LeadStatus; tags?: string[] }) =>
      api.patch<LeadData>(`/api/leads/${input.leadId}`, {
        status: input.status,
        tags: input.tags,
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["lead", variables.leadId] });
      queryClient.invalidateQueries({ queryKey: ["all-leads"] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useAddLeadNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { leadId: string; body: string }) =>
      api.post<LeadNote>(`/api/leads/${input.leadId}/notes`, { body: input.body }),
    onSuccess: (_data, variables) =>
      queryClient.invalidateQueries({ queryKey: ["lead", variables.leadId] }),
  });
}

export function useDeleteLeadNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { leadId: string; noteId: string }) =>
      api.delete<void>(`/api/leads/${input.leadId}/notes/${input.noteId}`),
    onSuccess: (_data, variables) =>
      queryClient.invalidateQueries({ queryKey: ["lead", variables.leadId] }),
  });
}

// --- workspace brand --------------------------------------------------------

export function useWorkspaceBrand() {
  return useQuery<WorkspaceBrand>({
    queryKey: ["workspace-brand"],
    queryFn: () => api.get("/api/users/me/brand"),
  });
}

export function useSaveWorkspaceBrand() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: Partial<Omit<WorkspaceBrand, "configured" | "font_pairings">>) =>
      api.put<WorkspaceBrand>("/api/users/me/brand", values),
    onSuccess: (data) => queryClient.setQueryData(["workspace-brand"], data),
  });
}

// --- workspace settings ----------------------------------------------------

function useUserSettingsMutation<TInput>(path: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: TInput) => api.patch<AuthUser>(path, values),
    onSuccess: (data) => queryClient.setQueryData(["auth", "me"], data),
  });
}

export function useUpdateProfile() {
  return useUserSettingsMutation<{ display_name: string | null }>("/api/users/me/profile");
}

export function useUpdateWorkspace() {
  return useUserSettingsMutation<{ name: string; timezone: string }>("/api/users/me/workspace");
}

export function useUpdateNotifications() {
  return useUserSettingsMutation<{
    notify_on_lead?: boolean;
    notify_weekly_summary?: boolean;
    notify_product_updates?: boolean;
  }>("/api/users/me/notifications");
}

export function useUpdateLabs() {
  return useUserSettingsMutation<{ enabled: boolean }>("/api/users/me/labs");
}

export function useTeam() {
  return useQuery<TeamData>({
    queryKey: ["workspace", "team"],
    queryFn: () => api.get<TeamData>("/api/users/me/team"),
  });
}

export function useInviteTeamMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { email: string; role: "admin" | "member" }) =>
      api.post<WorkspaceInvite>("/api/users/me/team/invitations", input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspace", "team"] }),
  });
}

export function useAcceptTeamInvitation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (token: string) =>
      api.post<AuthUser>("/api/users/me/team/invitations/accept", { token }),
    onSuccess: (data) => {
      queryClient.setQueryData(["auth", "me"], data);
      // Joining changes the ownership boundary for tools, leads, plan, brand and
      // integrations at once. Refresh every active query so no data from the
      // invitee's former personal workspace remains on screen.
      queryClient.invalidateQueries();
    },
  });
}

export function useRemoveTeamMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/api/users/me/team/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspace", "team"] }),
  });
}

export function useRevokeTeamInvitation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/api/users/me/team/invitations/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspace", "team"] }),
  });
}

export function useApiKeys() {
  return useQuery<{ keys: WorkspaceApiKey[] }>({
    queryKey: ["workspace", "api-keys"],
    queryFn: () => api.get("/api/users/me/api-keys"),
  });
}

export function useCreateApiKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { name: string; expires_in_days: number | null }) =>
      api.post<CreatedWorkspaceApiKey>("/api/users/me/api-keys", input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspace", "api-keys"] }),
  });
}

export function useRevokeApiKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/api/users/me/api-keys/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspace", "api-keys"] }),
  });
}

export function useCustomDomains() {
  return useQuery<{ domains: CustomDomain[] }>({
    queryKey: ["workspace", "domains"],
    queryFn: () => api.get("/api/users/me/domains"),
  });
}

export function useCreateCustomDomain() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { widget_id: string; hostname: string }) =>
      api.post<CustomDomain>("/api/users/me/domains", input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspace", "domains"] }),
  });
}

export function useVerifyCustomDomain() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<CustomDomain>(`/api/users/me/domains/${id}/verify`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspace", "domains"] }),
  });
}

export function useDeleteCustomDomain() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/api/users/me/domains/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspace", "domains"] }),
  });
}

// --- account and security --------------------------------------------------
//
// The server has shipped password changes, account deletion and full TOTP
// enrolment since the auth work landed; none of it had a client. `mfa_enabled`
// was on the user object and read by nothing, so the only way to turn on
// two-factor was to call the API by hand.

export interface MfaStatus {
  enabled: boolean;
  recovery_codes_remaining: number;
}

export interface MfaEnrollment {
  secret: string;
  /** otpauth:// URI, for an authenticator app to consume as a QR code. */
  provisioning_uri: string;
}

export interface MfaConfirmation {
  enabled: boolean;
  /** Shown exactly once — the server only keeps hashes. */
  recovery_codes: string[];
}

export function useMfaStatus() {
  return useQuery<MfaStatus>({
    queryKey: ["auth", "mfa"],
    queryFn: () => api.get<MfaStatus>("/api/auth/mfa"),
  });
}

export function useEnrollMfa() {
  return useMutation({
    mutationFn: () => api.post<MfaEnrollment>("/api/auth/mfa/enroll"),
  });
}

export function useConfirmMfa() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (code: string) => api.post<MfaConfirmation>("/api/auth/mfa/confirm", { code }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auth", "mfa"] });
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
    },
  });
}

export function useDisableMfa() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (code: string) => api.post<MfaStatus>("/api/auth/mfa/disable", { code }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auth", "mfa"] });
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (input: { currentPassword: string; newPassword: string }) =>
      api.patch<{ changed: boolean }>("/api/users/me/password", {
        current_password: input.currentPassword,
        new_password: input.newPassword,
      }),
  });
}

export function useDeleteAccount() {
  return useMutation({
    mutationFn: (currentPassword: string) =>
      api.delete<{ deleted: boolean }>("/api/users/me", { current_password: currentPassword }),
  });
}
