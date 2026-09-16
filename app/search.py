from __future__ import annotations

from app.models import Part


def normalize(text: str) -> str:
    return (
        text.replace("Ω", "")
        .replace("ω", "")
        .replace(" ", "")
        .strip()
        .lower()
    )


def parse_aliases(raw: str) -> list[str]:
    return [item.strip() for item in raw.replace("，", ",").split(",") if item.strip()]


def aliases_norm(aliases: list[str]) -> str:
    return ",".join(normalize(item) for item in aliases)


QTY_LABEL = {
    "empty": "没有",
    "few": "少量",
    "many": "大量",
    "exact": "具体数字",
}


def location_text(box: int, slot: int) -> str:
    return f"{box}号盒第{slot}格"


def part_matches(part: Part, keyword: str) -> bool:
    key = normalize(keyword)
    if not key:
        return True
    if key in part.name_norm:
        return True
    if key in part.aliases_norm.replace(",", " "):
        return True
    if key == normalize(f"{part.box}号盒"):
        return True
    if key == normalize(f"第{part.slot}格"):
        return True
    if key.isdigit() and key in {str(part.box), str(part.slot)}:
        return True
    return False


def rank(part: Part, keywords: list[str]) -> tuple:
    first = normalize(keywords[0]) if keywords else ""
    prefix = 0
    if first and (
        part.aliases_norm.split(",")[0].startswith(first) or part.name_norm.startswith(first)
    ):
        prefix = 0
    else:
        prefix = 1
    return (prefix, part.box, part.slot, part.id)


def search_parts(parts: list[Part], query: str) -> list[Part]:
    keywords = [item for item in query.strip().split() if item]
    if not keywords:
        return []
    matched = [
        part
        for part in parts
        if part.active and all(part_matches(part, key) for key in keywords)
    ]
    matched.sort(key=lambda part: rank(part, keywords))
    return matched
