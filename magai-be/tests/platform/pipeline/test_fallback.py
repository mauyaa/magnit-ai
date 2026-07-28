from app.platform.pipeline.fallback import grounded_architect, grounded_blueprints
from app.platform.pipeline.schemas import (
    CreationBrief,
    EvidenceReference,
    SiteBrandEvidence,
    SiteEvidence,
    SitePageEvidence,
    WidgetType,
)


def _evidence() -> SiteEvidence:
    return SiteEvidence(
        target_url="https://northside.example/",
        domain="northside.example",
        business_name="Northside Dental",
        summary="Dental care for local families.",
        pages=[
            SitePageEvidence(
                url="https://northside.example/",
                title="Northside Dental",
                headings=["Confident smiles start here"],
            )
        ],
        references=[
            EvidenceReference(
                id="heading_1",
                kind="heading",
                text="Confident smiles start here",
                source_url="https://northside.example/",
            )
        ],
        brand=SiteBrandEvidence(
            colors=["#112233", "#445566", "#88aa44"],
            fonts=["Lora", "Inter"],
            logo_url="https://northside.example/logo.svg",
        ),
        content_fingerprint="a" * 64,
        brand_fingerprint="b" * 64,
    )


def test_grounded_blueprints_honor_the_brief_and_stay_distinct():
    directions = grounded_blueprints(
        _evidence(),
        CreationBrief(
            mode="guided",
            preferred_type=WidgetType.INTERACTIVE_CHECKLIST,
            intent="Give families a personalised treatment preparation plan",
            goal="recommend_next_step",
        ),
    )

    assert len(directions.blueprints) == 3
    assert directions.blueprints[0].type is WidgetType.INTERACTIVE_CHECKLIST
    assert directions.blueprints[0].description.startswith("Give families")
    assert len({item.type for item in directions.blueprints}) == 3
    assert all(item.evidence_refs == ["heading_1"] for item in directions.blueprints)


def test_grounded_architect_uses_real_brand_evidence_and_a_working_decision():
    brief = CreationBrief(question_count=5, visitor_question="Which next step fits your situation?")
    blueprint = grounded_blueprints(_evidence(), brief).blueprints[0]

    architect = grounded_architect(blueprint, _evidence(), brief)

    assert architect.brand.primary_color == "#112233"
    assert architect.brand.accent_color == "#88aa44"
    assert architect.brand.font_headings == "Lora"
    assert architect.brand.logo_url == "https://northside.example/logo.svg"
    assert architect.decision is not None
    assert len(architect.decision.questions) == 5
    assert architect.decision.lead_gate == "after_value"
    assert architect.decision.evidence_refs == ["heading_1"]


def test_challenge_page_title_falls_back_to_a_clean_domain_name():
    evidence = _evidence().model_copy(
        update={
            "business_name": "One moment, please...",
            "domain": "northsidedental.com",
        }
    )

    direction = grounded_blueprints(evidence).blueprints[0]

    assert direction.title.startswith("Northside Dental ")
    assert "moment" not in direction.title.lower()
