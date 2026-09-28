from app.bom import ParsedLine, match_part
from app.models import Part
from app.search import aliases_norm, normalize


def _part(name: str, aliases: str, box: int = 1, slot: int = 1) -> Part:
    alias_list = [item.strip() for item in aliases.split(",") if item.strip()]
    return Part(
        name=name,
        aliases=",".join(alias_list),
        aliases_norm=aliases_norm(alias_list),
        name_norm=normalize(name),
        box=box,
        slot=slot,
        qty_kind="few",
        polarized=False,
        active=True,
        created_by=1,
        note="",
    )


def _line(name: str, footprint: str = "R0603", supplier: str = "") -> ParsedLine:
    return ParsedLine(
        designators="R1",
        name=name,
        footprint=footprint,
        supplier=supplier,
        quantity=1,
        skip_bin=False,
        polarized_hint=False,
        warning="",
    )


def test_ohm_forms_match_0603_not_precision_or_other_package():
    ordinary = _part("10KR电阻0603", "10K 0603")
    precision = _part("10k 0.1% 0603", "10k 0.1% 0603", slot=2)
    big = _part("10KR电阻0805", "10KR 0805", slot=3)
    ntc = _part("NTC", "10K1N", slot=4)
    parts = [precision, big, ntc, ordinary]
    assert match_part(_line("10K"), parts) is ordinary
    assert match_part(_line("10kΩ"), parts) is ordinary
    assert match_part(_line("10K", "R0805"), parts) is big
    assert match_part(_line("10K1N"), parts) is ntc


def test_resistor_r_suffix_and_capacitor_words_match_value_and_package():
    res = _part("33KR电阻0603", "33KR")
    cap = _part("220pf 0603 暂无电压", "220pf 0603 暂无电压", slot=2)
    other = _part("220pf 50v 0402", "220pf 0402", slot=3)
    parts = [res, other, cap]
    assert match_part(_line("33kΩ"), parts) is res
    assert match_part(_line("3.3K"), [_part("3.3kR 电阻0603", "3.3kR")]) is not None
    assert match_part(_line("220pF", "C0603"), parts) is cap
    assert match_part(_line("220pF", "C0402"), parts) is other


def test_same_capacitance_with_different_voltage_stays_unmatched():
    low = _part("10uf 10v 0603", "10uf 10v 0603")
    high = _part("10uf 50v 0603", "10uf 50v 0603", slot=2)
    parts = [low, high]
    assert match_part(_line("10uF", "C0603"), parts) is None
    assert match_part(_line("10uF", "C0603", "C19702,10uF"), parts) is None
    low.aliases = "10uf 10v 0603,C19702"
    low.aliases_norm = aliases_norm(["10uf 10v 0603", "C19702"])
    assert match_part(_line("10uF", "C0603", "C19702,10uF"), parts) is low


def test_model_token_ignores_extra_words_and_ordering_suffix():
    diode = _part("1N4148WS 开关二极管", "1N4148WS(更小)")
    other = _part("1N4148W-T4 开关二极管", "1N4148W-T4", slot=2)
    opamp = _part("TI TLV9002 双路运放", "TLV9002", slot=3)
    parts = [diode, other, opamp]
    assert match_part(_line("1N4148WS", "SOD-323_L1.8-W1.3-LS2.5-RD"), parts) is diode
    assert match_part(_line("1N4148W", "SOD-123_L2.7-W1.6-LS3.7-FD"), parts) is other
    assert match_part(_line("TLV9002IDR", "SOIC-8_L4.9-W3.9-P1.27-LS6.0-BL"), parts) is opamp


def test_exact_alias_does_not_cross_package():
    big = _part("10KR电阻0805", "10K")
    assert match_part(_line("10K", "R0603"), [big]) is None
