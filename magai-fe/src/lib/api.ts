import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface Blueprint {
  type: string;
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
  plan_tier: string;
  lead_cap: number;
  brand_tokens: Record<string, unknown> | null;
  widget_logic: Record<string, unknown> | null;
  copywriting: Record<string, unknown> | null;
  design_tokens: Record<string, unknown> | null;
  created_at: string;
  deployed_at: string | null;
}

export interface LeadData {
  id: string;
  widget_id: string;
  email: string;
  name: string | null;
  score: number | null;
  created_at: string;
}

export interface AnalyzeResponse {
  widget_id: string;
  blueprints: Blueprint[];
}

export interface BuildResponse {
  widget_id: string;
  iframe_url: string;
  status: string;
  embed_code: string;
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {}
    throw new Error(detail);
  }
  return res.json();
}

export function useWidgets() {
  return useQuery<{ widgets: WidgetData[] }>({
    queryKey: ["widgets"],
    queryFn: () => fetchJson(`${API_BASE}/api/widgets`),
    refetchInterval: 15_000,
  });
}

export function useWidget(id: string) {
  return useQuery<WidgetData>({
    queryKey: ["widget", id],
    queryFn: () => fetchJson(`${API_BASE}/api/widgets/${id}`),
    enabled: !!id,
    refetchInterval: (query) =>
      query.state.data?.status === "building" ? 3_000 : false,
  });
}

export function useLeads(widgetId: string) {
  return useQuery<LeadData[]>({
    queryKey: ["leads", widgetId],
    queryFn: () => fetchJson(`${API_BASE}/api/widgets/${widgetId}/leads`),
    enabled: !!widgetId,
  });
}

export function useAllLeads(widgetIds: string[]) {
  return useQuery<LeadData[]>({
    queryKey: ["all-leads", widgetIds],
    queryFn: async () => {
      const results = await Promise.allSettled(
        widgetIds.map((id) =>
          fetchJson<LeadData[]>(`${API_BASE}/api/widgets/${id}/leads`),
        ),
      );
      return results
        .filter((r) => r.status === "fulfilled")
        .flatMap((r) => r.value);
    },
    enabled: widgetIds.length > 0,
  });
}

export function useDeployWidget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (widgetId: string) =>
      fetchJson<{ iframe_url: string }>(
        `${API_BASE}/api/widgets/${widgetId}/deploy`,
        { method: "POST" },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["widgets"] });
    },
  });
}

export function useAnalyzeUrl() {
  return useMutation({
    mutationFn: (url: string) =>
      fetchJson<AnalyzeResponse>(`${API_BASE}/api/widgets/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      }),
  });
}

export function useBuildWidget() {
  return useMutation({
    mutationFn: ({
      widgetId,
      blueprintIndex,
      skipDeploy,
    }: {
      widgetId: string;
      blueprintIndex: number;
      skipDeploy?: boolean;
    }) =>
      fetchJson<BuildResponse>(`${API_BASE}/api/widgets/build`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          widget_id: widgetId,
          blueprint_index: blueprintIndex,
          skip_deploy: skipDeploy ?? false,
        }),
      }),
  });
}
