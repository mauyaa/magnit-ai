"""Controlled website evidence collection.

Models never browse a customer's site directly. This module fetches a small,
same-site set of public HTML pages, strips executable and hidden content, and
returns a bounded, attributable evidence record. The record is both safer
against indirect prompt injection and much easier to inspect than a model's
unverifiable claim that it "read the website".
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import ClassVar
from urllib.parse import urljoin, urlsplit

import httpx

from app.platform.pipeline.schemas import (
    EvidenceReference,
    SiteBrandEvidence,
    SiteEvidence,
    SitePageEvidence,
)
from app.platform.security.url_guard import validate_target_url

MAX_PAGES = 5
MAX_HTML_BYTES = 1_500_000
REQUEST_TIMEOUT_SECONDS = 12.0
MAX_REDIRECTS = 5

_SPACE = re.compile(r"\s+")
_HEX_COLOR = re.compile(r"(?<![\w-])#[0-9a-fA-F]{3,8}\b")
_FONT_FAMILY = re.compile(r"font-family\s*:\s*([^;}]+)", re.IGNORECASE)
_PRICE = re.compile(
    r"(?:[$€£]\s?\d[\d,.]*(?:\s?(?:/|per\s+)(?:month|year|mo|yr))?)"
    r"|(?:\b\d+(?:\.\d+)?\s?%(?!\w))",
    re.IGNORECASE,
)
_PROOF_WORDS = re.compile(
    r"\b(customers?|clients?|teams?|companies|results?|saved|increased|reduced|years?)\b",
    re.IGNORECASE,
)
_USEFUL_PATH = re.compile(
    r"/(?:services?|solutions?|pricing|about|case-stud(?:y|ies)|customers?|work|"
    r"industries|platform|product)(?:/|$)",
    re.IGNORECASE,
)
_GENERIC_HEADINGS = {
    "home",
    "welcome",
    "learn more",
    "get started",
    "contact us",
    "our services",
    "services",
}


class EvidenceCollectionError(RuntimeError):
    """The target did not provide usable public HTML."""


def _clean(value: str, limit: int = 500) -> str:
    return _SPACE.sub(" ", value).strip()[:limit]


def _dedupe(values: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = _clean(value)
        key = clean.casefold()
        if not clean or key in seen:
            continue
        seen.add(key)
        result.append(clean)
        if len(result) >= limit:
            break
    return result


@dataclass
class _Capture:
    tag: str
    attrs: dict[str, str]
    chunks: list[str]


class _EvidenceHTMLParser(HTMLParser):
    """Extract visible editorial signals without preserving page instructions."""

    _CAPTURE_TAGS: ClassVar[set[str]] = {
        "title",
        "h1",
        "h2",
        "h3",
        "a",
        "button",
        "p",
        "li",
        "style",
    }
    _SUPPRESSED_TAGS: ClassVar[set[str]] = {"script", "noscript", "template", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self.site_name = ""
        self.headings: list[str] = []
        self.calls_to_action: list[str] = []
        self.blocks: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.styles: list[str] = []
        self.inline_styles: list[str] = []
        self.logo_url: str | None = None
        self.icon_url: str | None = None
        self._captures: list[_Capture] = []
        self._suppressed_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr_map = {key.lower(): value or "" for key, value in attrs}
        if tag in self._SUPPRESSED_TAGS:
            self._suppressed_depth += 1
            return
        if self._suppressed_depth:
            return

        inline_style = attr_map.get("style")
        if inline_style:
            self.inline_styles.append(inline_style[:2_000])

        if tag == "meta":
            name = (attr_map.get("name") or attr_map.get("property") or "").casefold()
            content = _clean(attr_map.get("content", ""), 600)
            if name in {"description", "og:description", "twitter:description"}:
                if not self.description:
                    self.description = content
            elif name == "og:site_name" and not self.site_name:
                self.site_name = content

        if tag == "img":
            marker = " ".join(
                [
                    attr_map.get("alt", ""),
                    attr_map.get("class", ""),
                    attr_map.get("id", ""),
                    attr_map.get("src", ""),
                ]
            ).casefold()
            if "logo" in marker and not self.logo_url:
                self.logo_url = attr_map.get("src") or None

        if tag == "link":
            rel = attr_map.get("rel", "").casefold()
            if ("icon" in rel or "apple-touch-icon" in rel) and not self.icon_url:
                self.icon_url = attr_map.get("href") or None

        if tag in self._CAPTURE_TAGS:
            self._captures.append(_Capture(tag=tag, attrs=attr_map, chunks=[]))

    def handle_data(self, data: str) -> None:
        if self._suppressed_depth or not data.strip():
            return
        for capture in self._captures:
            capture.chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self._SUPPRESSED_TAGS:
            self._suppressed_depth = max(0, self._suppressed_depth - 1)
            return
        if self._suppressed_depth:
            return

        index = next(
            (i for i in range(len(self._captures) - 1, -1, -1) if self._captures[i].tag == tag),
            None,
        )
        if index is None:
            return
        capture = self._captures.pop(index)
        text = _clean(" ".join(capture.chunks), 1_000)
        if not text:
            return

        if tag == "title" and not self.title:
            self.title = text[:300]
        elif tag in {"h1", "h2", "h3"}:
            self.headings.append(text[:300])
        elif tag in {"a", "button"}:
            if 1 < len(text) <= 100:
                self.calls_to_action.append(text)
            href = capture.attrs.get("href")
            if tag == "a" and href:
                self.links.append((href, text[:150]))
        elif tag in {"p", "li"}:
            if 15 <= len(text) <= 800:
                self.blocks.append(text)
        elif tag == "style":
            self.styles.append(text[:20_000])


@dataclass
class _ParsedDocument:
    page: SitePageEvidence
    parser: _EvidenceHTMLParser
    final_url: str


def _decode_html(payload: bytes, encoding: str | None) -> str:
    try:
        return payload.decode(encoding or "utf-8", errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


async def _fetch_html(client: httpx.AsyncClient, url: str) -> tuple[str, str]:
    current = validate_target_url(url)
    for _ in range(MAX_REDIRECTS + 1):
        async with client.stream(
            "GET",
            current,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": "MagnitEvidenceBot/1.0 (+https://magnit.ai)",
            },
        ) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise EvidenceCollectionError("website returned an invalid redirect")
                current = validate_target_url(str(httpx.URL(current).join(location)))
                continue

            if response.status_code >= 400:
                raise EvidenceCollectionError(f"website returned HTTP {response.status_code}")

            content_type = response.headers.get("content-type", "").casefold()
            if content_type and "html" not in content_type:
                raise EvidenceCollectionError("website did not return HTML")

            declared = response.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > MAX_HTML_BYTES:
                raise EvidenceCollectionError("website page is too large to analyze safely")

            chunks: list[bytes] = []
            size = 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > MAX_HTML_BYTES:
                    raise EvidenceCollectionError("website page is too large to analyze safely")
                chunks.append(chunk)

            html = _decode_html(b"".join(chunks), response.encoding)
            return current, html

    raise EvidenceCollectionError("website redirected too many times")


def _page_from_html(url: str, html: str) -> _ParsedDocument:
    parser = _EvidenceHTMLParser()
    try:
        parser.feed(html)
    except Exception as exc:
        raise EvidenceCollectionError("website HTML could not be analyzed") from exc

    price_signals: list[str] = []
    for block in [*parser.headings, *parser.blocks]:
        if _PRICE.search(block):
            price_signals.append(block)

    page = SitePageEvidence(
        url=url,
        title=_clean(parser.title, 300),
        description=_clean(parser.description, 600),
        headings=_dedupe(parser.headings, 30),
        calls_to_action=_dedupe(parser.calls_to_action, 20),
        pricing_signals=_dedupe(price_signals, 20),
    )
    return _ParsedDocument(page=page, parser=parser, final_url=url)


def _absolute_asset(page_url: str, value: str | None) -> str | None:
    if not value:
        return None
    candidate = urljoin(page_url, value)
    parts = urlsplit(candidate)
    if parts.scheme not in {"http", "https"}:
        return None
    return candidate[:2048]


def _normalize_color(value: str) -> str:
    color = value.lower()
    if len(color) == 4:
        return "#" + "".join(character * 2 for character in color[1:])
    return color


def _brand_from_documents(documents: list[_ParsedDocument]) -> SiteBrandEvidence:
    css = "\n".join(
        style
        for document in documents
        for style in [*document.parser.styles, *document.parser.inline_styles]
    )
    colors = _dedupe([_normalize_color(value) for value in _HEX_COLOR.findall(css)], 20)

    fonts: list[str] = []
    for raw in _FONT_FAMILY.findall(css):
        first = raw.split(",")[0].strip().strip("\"'")
        if (
            first
            and not first.startswith("var(")
            and first.casefold()
            not in {"inherit", "initial", "sans-serif", "serif", "system-ui", "monospace"}
        ):
            fonts.append(first[:80])

    home = documents[0]
    logo = _absolute_asset(
        home.final_url,
        home.parser.logo_url or home.parser.icon_url,
    )
    return SiteBrandEvidence(colors=colors, fonts=_dedupe(fonts, 12), logo_url=logo)


def _fingerprint(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _business_name(parser: _EvidenceHTMLParser) -> str:
    if parser.site_name:
        return _clean(parser.site_name, 200)
    title = _clean(parser.title, 200)
    if not title:
        return ""
    return _clean(re.split(r"\s+[|\u2013\u2014-]\s+", title, maxsplit=1)[0], 200)


def _references(documents: list[_ParsedDocument]) -> list[EvidenceReference]:
    references: list[EvidenceReference] = []
    counts: dict[str, int] = {}

    def add(kind: str, text: str, source_url: str) -> None:
        clean = _clean(text)
        if not clean:
            return
        if any(
            item.kind == kind and item.text.casefold() == clean.casefold() for item in references
        ):
            return
        counts[kind] = counts.get(kind, 0) + 1
        references.append(
            EvidenceReference(
                id=f"{kind}_{counts[kind]}",
                kind=kind,
                text=clean,
                source_url=source_url,
            )
        )

    for document in documents:
        page = document.page
        if page.description:
            add("description", page.description, page.url)
        for heading in page.headings:
            add("heading", heading, page.url)
            if heading.casefold() not in _GENERIC_HEADINGS:
                add("offer", heading, page.url)
        for price in page.pricing_signals:
            add("price", price, page.url)
        for cta in page.calls_to_action:
            add("cta", cta, page.url)
        for block in document.parser.blocks:
            if _PROOF_WORDS.search(block) and re.search(r"\d", block):
                add("proof", block, page.url)
        if len(references) >= 80:
            break
    return references[:80]


def _candidate_links(home: _ParsedDocument) -> list[str]:
    root = urlsplit(home.final_url)
    candidates: list[tuple[int, str]] = []
    seen: set[str] = {home.final_url.rstrip("/")}
    for href, label in home.parser.links:
        absolute = urljoin(home.final_url, href)
        parsed = urlsplit(absolute)
        if parsed.scheme not in {"http", "https"} or parsed.hostname != root.hostname:
            continue
        clean = parsed._replace(fragment="", query="").geturl().rstrip("/")
        if not clean or clean in seen:
            continue
        seen.add(clean)
        marker = f"{parsed.path} {label}"
        if not _USEFUL_PATH.search(parsed.path) and not re.search(
            r"\b(services?|solutions?|pricing|about|customers?|work|product)\b",
            label,
            re.IGNORECASE,
        ):
            continue
        priority = 0 if re.search(r"pricing|services?|solutions?", marker, re.I) else 1
        candidates.append((priority, clean))
    candidates.sort(key=lambda item: (item[0], len(urlsplit(item[1]).path), item[1]))
    return [url for _, url in candidates[: MAX_PAGES - 1]]


async def collect_site_evidence(url: str) -> SiteEvidence:
    """Collect a source-grounded, same-site record suitable for model input."""
    safe_url = validate_target_url(url)
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
        follow_redirects=False,
    ) as client:
        try:
            home_url, home_html = await _fetch_html(client, safe_url)
        except httpx.HTTPError as exc:
            raise EvidenceCollectionError("website could not be reached") from exc
        home = _page_from_html(home_url, home_html)
        documents = [home]

        for candidate in _candidate_links(home):
            try:
                final_url, html = await _fetch_html(client, candidate)
                if urlsplit(final_url).hostname != urlsplit(home_url).hostname:
                    continue
                document = _page_from_html(final_url, html)
                if document.page.headings or document.page.description:
                    documents.append(document)
            except (EvidenceCollectionError, httpx.HTTPError, ValueError):
                # Secondary pages improve grounding but must not make an otherwise
                # readable website fail its first look.
                continue

    if not home.page.title and not home.page.headings and not home.page.description:
        raise EvidenceCollectionError("website did not expose enough readable content")

    brand = _brand_from_documents(documents)
    references = _references(documents)
    pages = [document.page for document in documents]
    content_payload = {
        "pages": [page.model_dump(mode="json") for page in pages],
        "references": [reference.model_dump(mode="json") for reference in references],
    }
    brand_payload = brand.model_dump(mode="json")

    return SiteEvidence(
        target_url=home_url,
        domain=urlsplit(home_url).hostname or urlsplit(safe_url).hostname or "unknown",
        business_name=_business_name(home.parser),
        summary=home.page.description or (home.page.headings[0] if home.page.headings else ""),
        pages=pages,
        references=references,
        brand=brand,
        content_fingerprint=_fingerprint(content_payload),
        brand_fingerprint=_fingerprint(brand_payload),
    )
