from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass

from openpyxl import load_workbook

from app.models import Part
from app.search import normalize, parse_aliases


class BomError(ValueError):
    pass


MAX_BYTES = 2 * 1024 * 1024
REQUIRED_HEADERS = ("Designator", "Name", "Footprint")

SKIP_POLAR_TOKENS = ("test-point", "testpoint", "铜条", "wafer", "conn", "db2erc")
SKIP_PREFIXES = {"R", "C", "L", "TP", "CN", "SW", "X", "NTC"}
POLAR_PREFIXES = {"D", "LED", "Q", "EC"}
POLAR_NAME_TOKENS = ("1n", "ss34", "ss54", "smaj", "bzt", "led", "mos")
POLAR_FP_TOKENS = (
    "sod-",
    "sma_",
    "led",
    "to-220",
    "lqfp",
    "soic",
    "tssop",
    "sot-23",
    "powervdfn",
    "cap-th",
)


@dataclass
class ParsedLine:
    designators: str
    name: str
    footprint: str
    supplier: str
    quantity: int
    skip_bin: bool
    polarized_hint: bool
    warning: str


def name_variants(name: str) -> set[str]:
    base = normalize(name)
    variants = {base}
    if base.endswith("r") and base[:-1].replace(".", "").isdigit():
        variants.add(base[:-1])
    if re.fullmatch(r"[0-9.]+", base):
        variants.add(base + "r")
    return {item for item in variants if item}


def footprint_short(fp: str) -> str:
    compact = fp.strip().replace(" ", "")
    upper = compact.upper()
    matched = re.match(r"^(?:R|C|LED_)(\d{4})$", upper)
    if matched:
        return matched.group(1).lower()
    return normalize(compact)[:20]


def lcsc_code(supplier: str) -> str:
    if not supplier:
        return ""
    first = supplier.split(",")[0].strip()
    if re.fullmatch(r"C\d+", first, re.I):
        return first.lower()
    return ""


def designator_prefixes(designators: str) -> list[str]:
    prefixes = []
    for item in designators.split(","):
        text = item.strip().upper()
        matched = re.match(r"^([A-Z]+)", text)
        if matched:
            prefixes.append(matched.group(1))
    return prefixes


def is_skip_bin(name: str, footprint: str) -> bool:
    blob = f"{name} {footprint}".lower()
    if "test-point" in blob or "testpoint" in blob.replace("-", ""):
        return True
    if "铜条" in name or "铜条" in footprint:
        return True
    return False


def _blob(name: str, footprint: str) -> str:
    return f"{name} {footprint}".lower()


def polarized_hint(designators: str, name: str, footprint: str) -> bool:
    blob = _blob(name, footprint)
    if any(token in blob for token in SKIP_POLAR_TOKENS):
        return False
    prefixes = designator_prefixes(designators)
    if prefixes and all(prefix in SKIP_PREFIXES for prefix in prefixes):
        return False
    if any(prefix in POLAR_PREFIXES for prefix in prefixes):
        return True
    if any(token in blob for token in POLAR_NAME_TOKENS):
        return True
    if any(token in blob for token in POLAR_FP_TOKENS):
        return True
    if "U" in prefixes:
        return True
    return False


def polarity_warning(designators: str, name: str, footprint: str) -> str:
    prefixes = set(designator_prefixes(designators))
    blob = _blob(name, footprint)
    if "LED" in prefixes or "led" in blob:
        return "别贴反：看封装缺口或丝印极性标。"
    if "Q" in prefixes or "mos" in blob:
        return "别贴反：按封装方向，G/D/S 不要转 180°。"
    if "EC" in prefixes or "cap-th" in blob:
        return "别贴反：负极（壳体条纹/短脚）对丝印阴影；长脚一般是正极。"
    if "D" in prefixes or "1n" in blob or "sod-" in blob or "smaj" in blob or "bzt" in blob:
        return "别贴反：阴极有杠/斜角，对丝印。"
    return "别贴反：1 脚对丝印圆点或缺口。"


def _header_map(header: list[str]) -> dict[str, int]:
    mapping = {cell.strip(): index for index, cell in enumerate(header) if cell and str(cell).strip()}
    missing = [name for name in REQUIRED_HEADERS if name not in mapping]
    if missing:
        raise BomError("请用嘉立创导出的 BOM")
    return mapping


def _cell(row: tuple, index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    value = row[index]
    if value is None:
        return ""
    return str(value).strip()


def _as_lines(header: list[str], body: list[tuple]) -> list[ParsedLine]:
    mapping = _header_map(header)
    supplier_i = mapping.get("Supplier")
    qty_i = mapping.get("Quantity")
    lines: list[ParsedLine] = []
    for row in body:
        if not row or all(cell is None or str(cell).strip() == "" for cell in row):
            continue
        designators = _cell(row, mapping["Designator"])
        name = _cell(row, mapping["Name"])
        footprint = _cell(row, mapping["Footprint"])
        if not designators or not name:
            continue
        qty_raw = _cell(row, qty_i) if qty_i is not None else "1"
        try:
            quantity = int(float(qty_raw)) if qty_raw else 1
        except ValueError:
            quantity = 1
        skip = is_skip_bin(name, footprint)
        polar = False if skip else polarized_hint(designators, name, footprint)
        lines.append(
            ParsedLine(
                designators=designators,
                name=name,
                footprint=footprint,
                supplier=_cell(row, supplier_i) if supplier_i is not None else "",
                quantity=quantity,
                skip_bin=skip,
                polarized_hint=polar,
                warning=polarity_warning(designators, name, footprint) if polar else "",
            )
        )
    if not lines:
        raise BomError("请用嘉立创导出的 BOM")
    return lines


def parse_bom(content: bytes, filename: str) -> list[ParsedLine]:
    if len(content) > MAX_BYTES:
        raise BomError("文件不能超过 2 MB")
    lower = filename.lower()
    if lower.endswith(".csv"):
        text = content.decode("utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(text))
        rows = [tuple(item.strip() for item in row) for row in reader]
        if not rows:
            raise BomError("请用嘉立创导出的 BOM")
        return _as_lines([str(item) for item in rows[0]], rows[1:])
    if not lower.endswith(".xlsx"):
        raise BomError("请用嘉立创导出的 BOM")
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        raise BomError("请用嘉立创导出的 BOM") from exc
    sheet = workbook[workbook.sheetnames[0]]
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise BomError("请用嘉立创导出的 BOM")
    header = [str(cell).strip() if cell is not None else "" for cell in rows[0]]
    return _as_lines(header, rows[1:])


def _part_keys(part: Part) -> set[str]:
    keys = {normalize(part.name)}
    keys.update(normalize(item) for item in parse_aliases(part.aliases))
    keys.update(part.aliases_norm.split(","))
    return {item for item in keys if item}


def _package_ok(part: Part, short: str) -> bool:
    if not short:
        return True
    haystack = f"{part.name_norm} {part.aliases_norm} {normalize(part.name)} {normalize(part.aliases)}"
    return short in haystack.replace(",", " ")


def match_part(line: ParsedLine, parts: list[Part]) -> Part | None:
    if line.skip_bin:
        return None
    variants = name_variants(line.name)
    short = footprint_short(line.footprint)
    code = lcsc_code(line.supplier)
    named: list[Part] = []
    for part in parts:
        if not part.active:
            continue
        keys = _part_keys(part)
        if keys & variants:
            named.append(part)
            if _package_ok(part, short):
                return part
    if code:
        for part in parts:
            if not part.active:
                continue
            if code in _part_keys(part):
                return part
    if len(named) == 1:
        return named[0]
    return None
