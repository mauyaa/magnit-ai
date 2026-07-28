"""The workspace's house style, and how it reaches a generated tool.

The pipeline reads a brand off the target site, which is right for a business
whose site already looks the way they want. This module exists for everyone
else: the agency running tools across five client sites, and the owner whose
website is two redesigns behind the identity they actually use.

Whatever is set here overrides what was extracted. Whatever is left blank keeps
deferring to the site — so a half-filled brand kit is a normal state, not an
incomplete one.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import WorkspaceBrand
from app.platform.pipeline.schemas import BrandExtraction

_HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


@dataclass(frozen=True)
class FontPairing:
    """A heading/body pair the generated widget can genuinely load.

    Named pairings rather than two free-text font fields: the widget requests its
    fonts from Google Fonts at build time, so a family we cannot request silently
    falls back to a system face — which looks like a bug in the generator rather
    than a typo in a settings field.
    """

    id: str
    label: str
    heading: str
    body: str
    note: str


FONT_PAIRINGS: tuple[FontPairing, ...] = (
    FontPairing("inter_fraunces", "Inter + Fraunces", "Fraunces", "Inter", "Clean and modern"),
    FontPairing("dmsans_source", "DM Sans + Source Serif", "Source Serif 4", "DM Sans", "Friendly"),
    FontPairing(
        "grotesk_lora", "Space Grotesk + Lora", "Space Grotesk", "Lora", "Bold and editorial"
    ),
    FontPairing("inter_inter", "Inter", "Inter", "Inter", "Neutral, gets out of the way"),
    FontPairing("playfair_lato", "Playfair + Lato", "Playfair Display", "Lato", "Classic"),
)

FONT_PAIRINGS_BY_ID = {pairing.id: pairing for pairing in FONT_PAIRINGS}

# How the tone choice moves the generated surface. These are the same three words
# the brand screen offers, resolved to something the Stitcher can act on.
TONE_BACKGROUNDS = {
    "light": "#FFFFFF",
    "soft": "#FAF7F2",
    "deep": "#12151A",
}


def is_configured(brand: WorkspaceBrand | None) -> bool:
    """Whether anything has actually been set. An empty row is not a brand kit."""
    if brand is None:
        return False
    return any(
        (
            brand.accent_color,
            brand.background_color,
            brand.font_pairing,
            brand.corner_radius is not None,
            brand.tone,
            brand.logo_url,
            brand.brand_personality,
        )
    )


async def get_brand(db: AsyncSession, user_id: uuid.UUID) -> WorkspaceBrand | None:
    result = await db.execute(select(WorkspaceBrand).where(WorkspaceBrand.user_id == user_id))
    return result.scalar_one_or_none()


async def upsert_brand(db: AsyncSession, user_id: uuid.UUID, values: dict) -> WorkspaceBrand:
    """Create or update the workspace brand.

    Only keys present in ``values`` are written, so clearing one field does not
    silently reset the others — an omitted key means "leave it", an explicit
    ``None`` means "go back to reading this from the site".
    """
    brand = await get_brand(db, user_id)
    if brand is None:
        brand = WorkspaceBrand(user_id=user_id)
        db.add(brand)

    for field_name in (
        "accent_color",
        "background_color",
        "font_pairing",
        "corner_radius",
        "tone",
        "logo_url",
        "brand_personality",
    ):
        if field_name in values:
            setattr(brand, field_name, values[field_name])

    await db.flush()
    return brand


def apply_to_extraction(
    extraction: BrandExtraction, brand: WorkspaceBrand | None
) -> BrandExtraction:
    """Layer the workspace brand over what was read from the site.

    Applied at build time rather than baked into the extraction itself, so the
    site-derived brand stays intact underneath: turning the kit off restores what
    was actually on the page instead of leaving the tool stuck on the override.
    """
    if not is_configured(brand) or brand is None:
        return extraction

    updates: dict[str, str] = {}
    if brand.accent_color and _HEX_COLOR.match(brand.accent_color):
        updates["accent_color"] = brand.accent_color
        updates["primary_color"] = brand.accent_color
    if brand.background_color and _HEX_COLOR.match(brand.background_color):
        updates["background_color"] = brand.background_color
    elif brand.tone in TONE_BACKGROUNDS:
        updates["background_color"] = TONE_BACKGROUNDS[brand.tone]

    pairing = FONT_PAIRINGS_BY_ID.get(str(brand.font_pairing or ""))
    if pairing is not None:
        updates["font_headings"] = pairing.heading
        updates["font_body"] = pairing.body

    if brand.brand_personality:
        updates["tone"] = brand.brand_personality
    if brand.logo_url:
        updates["logo_url"] = brand.logo_url

    return extraction.model_copy(update=updates)


def design_token_overrides(brand: WorkspaceBrand | None) -> dict[str, str]:
    """Extra CSS variables the Stitcher should emit for this workspace.

    Corner radius has no home on ``BrandExtraction`` — it is a shape decision,
    not a colour or a typeface — so it travels as a token override instead of
    being forced into the wrong model.
    """
    if not is_configured(brand) or brand is None:
        return {}
    overrides: dict[str, str] = {}
    if brand.corner_radius is not None:
        overrides["--radius"] = f"{int(brand.corner_radius)}px"
    return overrides
