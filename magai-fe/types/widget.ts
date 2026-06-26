export interface Blueprint {
  type: string
  title: string
  description: string
  rationale: string
}

export interface AnalyzeResponse {
  blueprints: Blueprint[]
}

export interface BuildRequest {
  url: string
  blueprint: Blueprint
}

export interface BuildResponse {
  widget_id: string
  iframe_url: string
  status: string
}

export interface WidgetStatus {
  widget_id: string
  status: string
  iframe_url: string | null
  embed_code: string | null
}
