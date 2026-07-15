from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, List

import mwparserfromhell


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")


@dataclass(frozen=True)
class ParsedImage:
    name: str
    role: str


@dataclass(frozen=True)
class ParsedInfobox:
    name: str
    params: Dict[str, str]


@dataclass(frozen=True)
class ParsedPage:
    title: str
    kind: str
    summary: str
    infoboxes: List[ParsedInfobox]
    attributes: Dict[str, str]
    images: List[ParsedImage]
    categories: List[str]
    links: List[str]


def parse_page(title: str, wikitext: str) -> ParsedPage:
    code = mwparserfromhell.parse(wikitext or "")
    categories = _extract_categories(code)
    links = _extract_links(code)
    infoboxes = _extract_infoboxes(code)
    attributes: Dict[str, str] = {}
    images: List[ParsedImage] = []

    for infobox in infoboxes:
        attributes.update(infobox.params)
        for key, value in infobox.params.items():
            if "image" in key.lower():
                image_name = _clean_image_name(value)
                if image_name:
                    images.append(ParsedImage(name=image_name, role=key))

    kind = _classify_kind(infoboxes, categories)
    summary = _extract_summary(code)

    return ParsedPage(
        title=title,
        kind=kind,
        summary=summary,
        infoboxes=infoboxes,
        attributes=attributes,
        images=_dedupe_images(images),
        categories=categories,
        links=links,
    )


def _extract_infoboxes(code: mwparserfromhell.wikicode.Wikicode) -> List[ParsedInfobox]:
    infoboxes: List[ParsedInfobox] = []
    for template in code.filter_templates(recursive=False):
        name = str(template.name).strip()
        if "infobox" not in name.lower():
            continue
        params: Dict[str, str] = {}
        for param in template.params:
            key = str(param.name).strip()
            value = _strip_markup(str(param.value)).strip()
            if key and value:
                params[key] = value
        infoboxes.append(ParsedInfobox(name=name, params=params))
    return infoboxes


def _extract_categories(code: mwparserfromhell.wikicode.Wikicode) -> List[str]:
    categories: List[str] = []
    for link in code.filter_wikilinks():
        title = str(link.title).strip()
        if not title.lower().startswith("category:"):
            continue
        category = title.split(":", 1)[1].strip()
        if category and category not in categories:
            categories.append(category)
    return categories


def _extract_links(code: mwparserfromhell.wikicode.Wikicode) -> List[str]:
    links: List[str] = []
    for link in code.filter_wikilinks():
        title = str(link.title).strip()
        lowered = title.lower()
        if not title or lowered.startswith(("category:", "file:", "image:")):
            continue
        if title not in links:
            links.append(title)
    return links


def _classify_kind(infoboxes: List[ParsedInfobox], categories: List[str]) -> str:
    infobox_text = " ".join(infobox.name for infobox in infoboxes).lower()
    category_text = " ".join(categories).lower()
    haystack = f"{infobox_text} {category_text}"
    if any(needle in haystack for needle in ("boss", "giant")):
        return "boss"

    infobox_checks = [
        ("character", ("character infobox",)),
        ("mob", ("mob infobox",)),
        ("food", ("food infobox",)),
        ("plant", ("plant infobox",)),
        ("biome", ("biome infobox",)),
        ("item", ("item infobox", "craft infobox", "turf infobox")),
        ("structure", ("structure infobox",)),
    ]
    for kind, needles in infobox_checks:
        if any(needle in infobox_text for needle in needles):
            return kind

    checks = [
        ("boss", ("boss", "giant")),
        ("character", ("character", "survivor")),
        ("plant", ("plant", "flora", "crop", "farm plant")),
        ("mob", ("mob", "animal", "creature", "monster")),
        ("item", ("item", "tool", "weapon", "armor", "clothing")),
        ("structure", ("structure", "building")),
        ("biome", ("biome",)),
        ("food", ("food", "dish", "crock pot")),
        ("skin", ("skin", "clothes")),
    ]
    for kind, needles in checks:
        if any(needle in haystack for needle in needles):
            return kind
    return "page"


def _clean_image_name(value: str) -> str:
    candidate = value.strip()
    candidate = re.sub(r"^(?:File|Image):", "", candidate, flags=re.IGNORECASE)
    candidate = candidate.split("|", 1)[0].strip()
    if not candidate:
        return ""
    if any(candidate.lower().endswith(extension) for extension in IMAGE_EXTENSIONS):
        return candidate.replace(" ", "_") if candidate.startswith(("File:", "Image:")) else candidate
    return ""


def _dedupe_images(images: List[ParsedImage]) -> List[ParsedImage]:
    seen = set()
    result: List[ParsedImage] = []
    for image in images:
        key = (image.name, image.role)
        if key in seen:
            continue
        seen.add(key)
        result.append(image)
    return result


def _extract_summary(code: mwparserfromhell.wikicode.Wikicode) -> str:
    without_templates = code.strip_code(normalize=True, collapse=True)
    lines = []
    for raw_line in without_templates.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("Category:"):
            continue
        if line.startswith(("*", "|", "{", "}")):
            continue
        lines.append(line)
    text = " ".join(lines)
    text = re.sub(r"\s+", " ", text).strip()
    match = re.search(r"(.+?[.!?])(?:\s|$)", text)
    if match:
        return match.group(1).strip()
    return text[:500]


def _strip_markup(value: str) -> str:
    return mwparserfromhell.parse(value).strip_code(normalize=True, collapse=True)
