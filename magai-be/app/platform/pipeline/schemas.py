from pydantic import BaseModel
from typing import Any
from enum import StrEnum


class WidgetType(StrEnum):
    ROI_CALCULATOR = "roi_calculator"
    READINESS_QUIZ = "readiness_quiz"
    COMPETITIVE_COMPARISON = "competitive_comparison"
    AUDIT_TOOL = "audit_tool"
    INTERACTIVE_CHECKLIST = "interactive_checklist"


class Blueprint(BaseModel):
    type: WidgetType
    title: str
    description: str
    rationale: str


class BlueprintList(BaseModel):
    blueprints: list[Blueprint]


class BrandExtraction(BaseModel):
    primary_color: str
    secondary_color: str
    background_color: str
    accent_color: str
    font_headings: str
    font_body: str
    tone: str
    logo_url: str | None = None


class MathLogic(BaseModel):
    formula: str
    variables: list[dict[str, str]]
    example_calculation: str


class VisualLanguage(BaseModel):
    layout: str = "centered-single-column"
    spacing: str = "comfortable"
    card_style: str = "solid-white"
    border_radius: str = "rounded"
    shadow_depth: str = "subtle"
    button_style: str = "filled-solid"
    decorative_elements: str = "none"
    icon_style: str = "outlined"
    visual_energy: str = "balanced"


class ArchitectOutput(BaseModel):
    widget_type: WidgetType
    brand: BrandExtraction
    visual_language: VisualLanguage = VisualLanguage()
    logic: MathLogic
    copywriting: dict[str, Any]


class DesignTokens(BaseModel):
    css_variables: dict[str, str]
    component_theme: dict[str, str]


class DeploymentResult(BaseModel):
    url: str
    widget_id: str


class ProjectFile(BaseModel):
    path: str
    content: str


class WidgetCode(BaseModel):
    files: list[ProjectFile]
    design_tokens: DesignTokens
    entry_point: str = "src/App.jsx"


class PipelineStatus(BaseModel):
    state: str
    progress: float
    error: str | None = None
    blueprints: list[Blueprint] | None = None
    deployment_url: str | None = None
    iframe_html: str | None = None
