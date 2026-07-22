from pydantic import BaseModel

from app.platform.pipeline.schemas import Blueprint, WidgetType


class AnalyzeRequest(BaseModel):
    url: str


class AnalyzeResponse(BaseModel):
    widget_id: str
    blueprints: list[Blueprint]


class BuildRequest(BaseModel):
    widget_id: str
    blueprint_index: int
    skip_deploy: bool = False


class BuildResponse(BaseModel):
    widget_id: str
    iframe_url: str
    status: str
    embed_code: str


class WidgetStatusResponse(BaseModel):
    id: str
    title: str
    widget_type: str
    status: str
    target_url: str
    deployment_url: str | None = None
    embed_code: str | None = None
    leads_count: int
    plan_tier: str
    lead_cap: int
    brand_tokens: dict | None = None
    visual_language: dict | None = None
    widget_logic: dict | None = None
    copywriting: dict | None = None
    design_tokens: dict | None = None
    build_stage: str | None = None
    build_progress: float | None = None
    build_error: str | None = None
    created_at: str
    deployed_at: str | None = None


class WidgetListResponse(BaseModel):
    widgets: list[WidgetStatusResponse]
