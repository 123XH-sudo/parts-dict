from __future__ import annotations

import re

from app.models import Part

_PKG_CODES = (
    "0201",
    "0402",
    "0603",
    "0805",
    "1206",
    "1210",
    "1812",
    "2010",
    "2512",
    "0602",
    "0508",
)


def normalize(text: str) -> str:
    return (
        text.replace("Ω", "")
        .replace("ω", "")
        .replace(" ", "")
        .strip()
        .lower()
    )


def _search_text(text: str) -> str:
    return text.replace("Ω", "").replace("ω", "").strip().lower()


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


def _matches_text(text: str, key: str) -> bool:
    """按数字边界匹配，10K 不会命中 100K/10K1N，4.7K 不会命中 47K。"""
    start = 0
    while True:
        pos = text.find(key, start)
        if pos < 0:
            return False
        before = text[pos - 1] if pos else ""
        after_at = pos + len(key)
        after = text[after_at] if after_at < len(text) else ""
        rest = text[after_at:]
        if not before.isdigit() and not after.isdigit():
            return True
        if after.isdigit() and (
            rest.startswith(_PKG_CODES)
            or re.match(r"\d+\.?\d*v", rest)
            or re.match(r"\d*\.?\d+%", rest)
        ):
            return True
        start = pos + 1


def part_matches(part: Part, keyword: str) -> bool:
    key = _search_text(keyword)
    if not key:
        return True
    if key == normalize(f"{part.box}号盒"):
        return True
    if key == normalize(f"第{part.slot}格"):
        return True
    if key.isdigit() and key in {str(part.box), str(part.slot)}:
        return True
    if _matches_text(_search_text(part.name), key):
        return True
    return any(_matches_text(_search_text(alias), key) for alias in parse_aliases(part.aliases))


def _texts(part: Part) -> list[str]:
    return [_search_text(part.name)] + [
        _search_text(alias) for alias in parse_aliases(part.aliases)
    ]


def rank(part: Part, keywords: list[str]) -> tuple:
    first = _search_text(keywords[0]) if keywords else ""
    texts = _texts(part)
    if first and any(text == first for text in texts):
        quality = 0
    elif first and any(text.startswith(first) for text in texts):
        quality = 1
    else:
        quality = 2
    return (quality, part.box, part.slot, part.id)


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
