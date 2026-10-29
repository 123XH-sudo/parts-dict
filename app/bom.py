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
REQUIRED_FIELDS = ("designator", "name", "footprint")
HEADER_SCAN_ROWS = 10

# 立创EDA 导出的是 Name，嘉立创下单/贴片用的 BOM 是 Comment。
HEADER_ALIASES = {
    "designator": (
        "designator",
        "designators",
        "reference",
        "references",
        "refdes",
        "part reference",
        "位号",
        "标号",
        "元件标号",
        "器件标号",
        "器件位号",
        "元件位号",
    ),
    "name": (
        "name",
        "comment",
        "value",
        "device",
        "规格",
        "规格型号",
        "型号",
        "名称",
        "器件名称",
        "值",
    ),
    "footprint": ("footprint", "package", "封装", "封装形式", "器件封装"),
    "supplier": (
        "supplier",
        "supplier part",
        "supplier part #",
        "supplier part number",
        "lcsc",
        "lcsc part",
        "lcsc part #",
        "lcsc part number",
        "lcsc part no",
        "供应商编号",
        "供应商料号",
        "立创编号",
        "嘉立创编号",
        "商品编号",
    ),
    "quantity": ("quantity", "qty", "数量"),
    "mpn": (
        "manufacturer part",
        "manufacturer part #",
        "manufacturer part number",
        "manufacturer p/n",
        "mpn",
        "厂商型号",
        "厂家型号",
        "制造商型号",
    ),
}


def _header_key(cell: object) -> str:
    text = str(cell).strip().lstrip("\ufeff").lower() if cell is not None else ""
    return re.sub(r"[\s_:：]+", "", text).replace("＃", "#")


_ALIAS_KEYS = {
    field: frozenset(_header_key(alias) for alias in aliases)
    for field, aliases in HEADER_ALIASES.items()
}

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
    mpn: str = ""


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
    for item in re.split(r"[,，;；\s]+", designators.strip()):
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


def _header_map(header: tuple | list) -> dict[str, list[int]] | None:
    found: dict[str, list[int]] = {}
    for index, cell in enumerate(header):
        key = _header_key(cell)
        if not key:
            continue
        for field, keys in _ALIAS_KEYS.items():
            if key in keys:
                found.setdefault(field, []).append(index)
                break
    if all(field in found for field in REQUIRED_FIELDS):
        return found
    return None


def _cell(row: tuple, index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    value = row[index]
    if value is None:
        return ""
    return str(value).strip()


def _first_cell(row: tuple, indices: list[int]) -> str:
    for index in indices:
        value = _cell(row, index)
        if value:
            return value
    return ""


def _supplier_cell(row: tuple, indices: list[int]) -> str:
    values = [value for value in (_cell(row, index) for index in indices) if value]
    for value in values:
        if lcsc_code(value):
            return value
    return values[0] if values else ""


def _designator_count(designators: str) -> int:
    items = [item for item in re.split(r"[,，;；\s]+", designators.strip()) if item]
    return len(items) or 1


def _header_error(rows: list[tuple]) -> BomError:
    header = next((row for row in rows if row and any(str(cell).strip() for cell in row if cell is not None)), ())
    shown = "、".join(str(cell).strip() for cell in header if cell is not None and str(cell).strip())
    message = "没认出 BOM 表头：需要位号（Designator）、规格（Name 或 Comment）、封装（Footprint）三列。"
    if shown:
        message += f"这个文件的表头是：{shown}。"
    return BomError(message)


def _as_lines(mapping: dict[str, list[int]], body: list[tuple]) -> list[ParsedLine]:
    designator_i = mapping["designator"][0]
    name_i = mapping["name"][0]
    footprint_i = mapping["footprint"][0]
    supplier_is = mapping.get("supplier", [])
    mpn_is = mapping.get("mpn", [])
    qty_i = mapping.get("quantity", [None])[0]
    lines: list[ParsedLine] = []
    for row in body:
        if not row or all(cell is None or str(cell).strip() == "" for cell in row):
            continue
        designators = _cell(row, designator_i)
        name = _cell(row, name_i)
        footprint = _cell(row, footprint_i)
        if not designators or not name:
            continue
        quantity = _designator_count(designators)
        if qty_i is not None:
            qty_raw = _cell(row, qty_i)
            try:
                quantity = int(float(qty_raw)) if qty_raw else quantity
            except ValueError:
                pass
        skip = is_skip_bin(name, footprint)
        polar = False if skip else polarized_hint(designators, name, footprint)
        lines.append(
            ParsedLine(
                designators=designators,
                name=name,
                footprint=footprint,
                supplier=_supplier_cell(row, supplier_is),
                quantity=quantity,
                skip_bin=skip,
                polarized_hint=polar,
                warning=polarity_warning(designators, name, footprint) if polar else "",
                mpn=_first_cell(row, mpn_is),
            )
        )
    if not lines:
        raise BomError("这个 BOM 里没有可用的料，请确认表头和内容后再导出一次。")
    return lines


def _split_rows(rows: list[tuple]) -> list[ParsedLine]:
    for index, row in enumerate(rows[:HEADER_SCAN_ROWS]):
        mapping = _header_map(row)
        if mapping is not None:
            return _as_lines(mapping, rows[index + 1 :])
    raise _header_error(rows)


def parse_bom(content: bytes, filename: str) -> list[ParsedLine]:
    if len(content) > MAX_BYTES:
        raise BomError("文件不能超过 2 MB")
    lower = filename.lower()
    if lower.endswith(".csv"):
        text = content.decode("utf-8-sig", errors="replace")
        rows = [tuple(item.strip() for item in row) for row in csv.reader(io.StringIO(text))]
        if not rows:
            raise BomError("这个文件是空的，请用嘉立创导出的 BOM。")
        return _split_rows(rows)
    if not lower.endswith(".xlsx"):
        raise BomError("只支持嘉立创导出的 xlsx 或 csv BOM，请重新导出后再上传。")
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        raise BomError("这个 xlsx 打不开，请重新从嘉立创导出 BOM。") from exc
    first_error: BomError | None = None
    for name in workbook.sheetnames:
        rows = list(workbook[name].iter_rows(values_only=True))
        if not rows:
            continue
        try:
            return _split_rows(rows)
        except BomError as exc:
            first_error = first_error or exc
    raise first_error or BomError("这个文件里没有表，请用嘉立创导出的 BOM。")


_PKG_CODES = ("0201", "0402", "0603", "0805", "1206", "1210", "1812", "2010", "2512", "0602", "0508")
_PKG_RE = re.compile(r"(?<!\d)(" + "|".join(_PKG_CODES) + r")(?!\d)")


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


def _loose_text(text: str) -> str:
    return (
        text.replace("Ω", "")
        .replace("ω", "")
        .replace("µ", "u")
        .replace("μ", "u")
        .lower()
    )


def _pieces(text: str) -> list[str]:
    return [item for item in re.split(r"[\s,，()（）/]+", _loose_text(text)) if item]


def _res_values(text: str) -> set[str]:
    blob = _loose_text(text)
    found: set[str] = set()
    for match in re.finditer(r"(?<![0-9.])(\d+)([kmg])(\d+)r?(?![a-z0-9.])", blob):
        found.add(f"{match.group(1)}.{match.group(3)}{match.group(2)}")
    for match in re.finditer(r"(?<![0-9.])(\d+\.?\d*)([kmg])r?(?![a-z0-9.])", blob):
        found.add(match.group(1) + match.group(2))
    for match in re.finditer(r"(?<![0-9.])(\d+\.?\d*)r(?![a-z0-9.])", blob):
        found.add(match.group(1))
    return found


def _cap_values(text: str) -> set[str]:
    blob = _loose_text(text)
    return {
        match.group(1) + match.group(2) + "f"
        for match in re.finditer(r"(?<![0-9.])(\d+\.?\d*)([pnu])f(?![a-z0-9.])", blob)
    }


_VOLT_RE = re.compile(r"(?<![a-z0-9.])(\d+(?:\.\d+)?)\s*v(?:dc|ac)?(?![a-z0-9])")


def is_capacitor(text: str) -> bool:
    return bool(_cap_values(text))


def _volt_values(text: str) -> set[str]:
    return {match.group(1) for match in _VOLT_RE.finditer(_loose_text(text))}


def _max_volt(text: str) -> float | None:
    return max((float(value) for value in _volt_values(text)), default=None)


def voltage_label(text: str) -> str:
    value = _max_volt(text)
    return "" if value is None else f"{value:g}V"


def _package_codes(text: str) -> set[str]:
    return set(_PKG_RE.findall(_loose_text(text)))


def _tolerance_percent(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if match:
        return float(match.group(1))
    match = re.search(r"(\d+(?:\.\d+)?)\s*‰", text)
    if match:
        return float(match.group(1)) / 10
    return None


# 厂家型号里的精度位号：RT0603B…、PTFR0603B…、ERA…B… 等为 ±0.1%。
_PRECISION_MPN_RE = re.compile(
    r"^(?:RT\d{4}B|PTFR\d{4}B|ERA[0-9A-Z]{2,3}B|RG\d{4}[PB])",
    re.I,
)


def precision_label(text: str) -> str:
    if "高精" in text or "精密" in text:
        return "高精"
    tolerance = _tolerance_percent(text)
    if tolerance is not None and tolerance <= 0.5:
        return f"{tolerance:g}%"
    if any(_PRECISION_MPN_RE.match(piece) for piece in _pieces(text)):
        return "0.1%"
    return ""


def _is_precision(text: str) -> bool:
    return bool(precision_label(text))


def bom_is_precision(line: ParsedLine) -> bool:
    return bool(precision_label(f"{line.name} {line.mpn}"))


def _packages_conflict(part: Part, short: str) -> bool:
    if not re.fullmatch(r"\d{4}", short or ""):
        return False
    pkgs = _package_codes(f"{part.name} {part.aliases}")
    return bool(pkgs) and short not in pkgs


def _mpn_tokens(text: str) -> set[str]:
    found: set[str] = set()
    for piece in _pieces(text):
        if len(piece) < 6 or piece in _PKG_CODES:
            continue
        if re.search(r"[\u4e00-\u9fff]", piece):
            continue
        if not re.search(r"[a-z]", piece) or not re.search(r"\d", piece):
            continue
        if re.fullmatch(r"[0-9.]+[kmg]?r?", piece) or re.fullmatch(r"[0-9.]+[pnu]f", piece):
            continue
        if re.fullmatch(r"[0-9.]+v", piece):
            continue
        found.add(piece)
    return found


def _passive_hits(line: ParsedLine, parts: list[Part], short: str) -> list[Part]:
    bom_res = _res_values(line.name)
    bom_caps = _cap_values(line.name)
    if bool(bom_res) == bool(bom_caps):
        return []
    kind = "cap" if bom_caps else "res"
    bom_required = _max_volt(line.name)
    bom_precise = bom_is_precision(line)
    pkg = short if re.fullmatch(r"\d{4}", short or "") else ""
    strong: list[Part] = []
    weak: list[Part] = []
    for part in parts:
        if not part.active:
            continue
        text = f"{part.name} {part.aliases}"
        if bom_precise and not _is_precision(text):
            continue
        if kind == "res":
            if not (_res_values(text) & bom_res):
                continue
            if re.search(r"ntc|热敏", text, re.I) and not re.search(r"ntc|热敏", line.name, re.I):
                continue
        else:
            if not (_cap_values(text) & bom_caps):
                continue
            rated = _max_volt(text)
            if bom_required is not None:
                if rated is None or rated < bom_required:
                    continue
        pkgs = _package_codes(text)
        if pkg and pkgs and pkg not in pkgs:
            continue
        if pkg and pkg in pkgs:
            strong.append(part)
        else:
            weak.append(part)
    chosen = strong or weak
    if not bom_precise and kind == "res" and chosen:
        ordinary = [
            part for part in chosen if not _is_precision(f"{part.name} {part.aliases}")
        ]
        if ordinary:
            chosen = ordinary
    if kind == "cap":
        if bom_required is not None and chosen:
            rated = [
                (_max_volt(f"{part.name} {part.aliases}"), part) for part in chosen
            ]
            known = [(value, part) for value, part in rated if value is not None]
            if known:
                closest = min(value for value, _ in known)
                best = [part for value, part in known if value == closest]
                return best if len(best) == 1 else []
            return []
        if bom_required is None and len(chosen) > 1:
            signatures = {
                frozenset(_volt_values(f"{part.name} {part.aliases}")) for part in chosen
            }
            if len(signatures) > 1:
                return []
    if len(chosen) == 1:
        return chosen
    return []


def _mpn_hits(line: ParsedLine, parts: list[Part]) -> list[Part]:
    bom_tokens = _mpn_tokens(f"{line.name} {line.mpn}")
    bom_whole = re.sub(r"\s+", "", _loose_text(line.name))
    precise = bom_is_precision(line)
    hits: list[Part] = []
    for part in parts:
        if not part.active:
            continue
        if precise and not _is_precision(f"{part.name} {part.aliases}"):
            continue
        matched = False
        for token in _mpn_tokens(f"{part.name} {part.aliases}"):
            if token in bom_tokens or token == bom_whole:
                matched = True
                break
            if bom_whole.startswith(token) and re.fullmatch(r"[a-z]{1,4}", bom_whole[len(token) :]):
                matched = True
                break
            targets = bom_tokens | {bom_whole}
            if any(
                token.startswith(bom) and re.fullmatch(r"-[a-z0-9]+", token[len(bom) :])
                for bom in targets
            ):
                matched = True
                break
        if matched:
            hits.append(part)
    if len(hits) == 1:
        return hits
    return []


def match_part(line: ParsedLine, parts: list[Part]) -> Part | None:
    if line.skip_bin:
        return None
    variants = name_variants(line.name)
    if line.mpn:
        variants.add(normalize(line.mpn))
    short = footprint_short(line.footprint)
    code = lcsc_code(line.supplier)
    precise = bom_is_precision(line)
    named: list[Part] = []
    named_ok: list[Part] = []
    for part in parts:
        if not part.active:
            continue
        if precise and not _is_precision(f"{part.name} {part.aliases}"):
            continue
        if _packages_conflict(part, short):
            continue
        keys = _part_keys(part)
        if keys & variants:
            named.append(part)
            if _package_ok(part, short):
                named_ok.append(part)
    pool = named_ok or named
    if pool:
        if precise:
            if len(pool) == 1:
                return pool[0]
        else:
            ordinary = [
                part for part in pool if not _is_precision(f"{part.name} {part.aliases}")
            ]
            preferred = ordinary or pool
            if len(preferred) == 1:
                return preferred[0]
    if code:
        for part in parts:
            if not part.active:
                continue
            if precise and not _is_precision(f"{part.name} {part.aliases}"):
                continue
            if code in _part_keys(part):
                return part
    passive = _passive_hits(line, parts, short)
    if len(passive) == 1:
        return passive[0]
    mpn = _mpn_hits(line, parts)
    if len(mpn) == 1:
        return mpn[0]
    return None
