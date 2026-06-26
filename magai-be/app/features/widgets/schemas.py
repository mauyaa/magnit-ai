from pydantic import BaseModel

from app.platform.pipeline.schemas import Blueprint, BlueprintList, WidgetType


class AnalyzeRequest(BaseModel):
    url: str


class AnalyzeResponse(BaseModel):
    blueprints: list[Blueprint]


class BuildRequest(BaseModel):
    url: str
    blueprint: Blueprint


class BuildResponse(BaseModel):
    widget_id: str
    iframe_url: str
    status: str


class WidgetStatusResponse(BaseModel):
    widget_id: str
    status: str
    iframe_url: str | None = None
    embed_code: str | None = None


class WidgetTypeList(BaseModel):
    types: list[WidgetType]
