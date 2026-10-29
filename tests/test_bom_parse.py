from io import BytesIO

import pytest
from openpyxl import Workbook

from app.bom import BomError, parse_bom


def _xlsx(sheets: list[list[list]]) -> bytes:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for rows in sheets:
        sheet = workbook.create_sheet()
        for row in rows:
            sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_jlcpcb_order_bom_with_comment_header():
    content = (
        "Comment,Designator,Footprint,LCSC Part #\r\n"
        '10K,"R251,R42",R0603,C25804\r\n'
        "100nF,C312,C0603,\r\n"
    ).encode("utf-8-sig")

    lines = parse_bom(content, "bom.csv")

    assert [line.name for line in lines] == ["10K", "100nF"]
    assert lines[0].footprint == "R0603"
    assert lines[0].supplier == "C25804"
    assert lines[0].quantity == 2
    assert lines[1].quantity == 1


def test_xlsx_skips_title_rows_and_reads_supplier_part():
    content = _xlsx(
        [
            [
                ["无刷驱动 BOM"],
                ["Designator", "Comment", "Footprint", "Quantity", "Supplier Part"],
                ["R1 R2", "10K", "R0603", 2, "C25804"],
            ]
        ]
    )

    lines = parse_bom(content, "BOM.xlsx")

    assert len(lines) == 1
    assert lines[0].designators == "R1 R2"
    assert lines[0].name == "10K"
    assert lines[0].supplier == "C25804"
    assert lines[0].quantity == 2


def test_xlsx_uses_first_sheet_that_looks_like_a_bom():
    content = _xlsx(
        [
            [["说明"], ["这里不是表头"]],
            [
                ["ID", "Designator", "Name", "Footprint", "Supplier", "Quantity"],
                [1, "C312", "100nF", "C0603", None, 1],
            ],
        ]
    )

    lines = parse_bom(content, "BOM.xlsx")

    assert [line.name for line in lines] == ["100nF"]
    assert lines[0].quantity == 1


def test_quantity_falls_back_to_designator_count():
    content = b"Designator,Name,Footprint\nR1 R2 R3,10K,R0603\n"

    lines = parse_bom(content, "bom.csv")

    assert lines[0].quantity == 3


def test_unknown_headers_report_the_actual_columns():
    with pytest.raises(BomError) as excinfo:
        parse_bom(b"Foo,Bar\n1,2\n", "bom.csv")

    message = str(excinfo.value)
    assert "Designator" in message
    assert "Foo" in message


def test_old_excel_format_is_rejected_clearly():
    with pytest.raises(BomError) as excinfo:
        parse_bom(b"whatever", "bom.xls")

    assert "xlsx" in str(excinfo.value)
