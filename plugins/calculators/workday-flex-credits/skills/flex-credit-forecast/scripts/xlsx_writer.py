#!/usr/bin/env python3
"""Write a minimal, values-only XLSX workbook with the Python standard library.

Cells are str, int, float, bool or None, or a StyledCell(value, fmt, bold) where fmt is
"credits", "usd" (cents), "usd_whole", "pct" or "text". Strings are written inline (no shared strings table)
and nothing is ever a formula, so text such as "=SUM(A1)" stays text. The same input
always produces the same bytes.
"""

from __future__ import annotations

import math
import re
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import NamedTuple, Union
from xml.sax.saxutils import escape


class StyledCell(NamedTuple):
    value: Union[str, int, float, bool, None]  # noqa: UP007
    fmt: str = "text"
    bold: bool = False


Cell = Union[str, int, float, bool, None, StyledCell]  # noqa: UP007
Rows = Sequence[Sequence[Cell]]

FORMATS = ("general", "credits", "usd", "usd_whole", "pct", "text")
# Custom number formats start at id 164; "text" uses the built-in id 49 ("@").
NUM_FMT_IDS = {"general": 0, "credits": 164, "usd": 165, "usd_whole": 167, "pct": 166, "text": 49}
NUM_FMT_CODES = {164: "#,##0", 165: '"$"#,##0.00', 166: "0.0%", 167: '"$"#,##0'}
MAX_CELL_TEXT = 32767  # Excel's limit per cell
FIXED_DATE = (1980, 1, 1, 0, 0, 0)
_CONTROL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿\ud800-\udfff]")
_SHEET_BAD = re.compile(r"[\[\]:*?/\\]")


def clean_text(text: str) -> str:
    """Drop characters XML 1.0 can't carry, then escape markup and quotes."""
    return escape(_CONTROL.sub("", text), {'"': "&quot;"})


def sheet_name(name: str, index: int, used: set[str]) -> str:
    """Excel's rules: 31 characters at most, none of []:*?/\\, unique ignoring case."""
    base = _SHEET_BAD.sub("", _CONTROL.sub("", name)).strip().strip("'")[:31] or f"Sheet{index}"
    candidate = base
    n = 2
    while candidate.lower() in used:
        suffix = f" ({n})"
        candidate = base[: 31 - len(suffix)] + suffix
        n += 1
    used.add(candidate.lower())
    return candidate


def column_letter(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA."""
    letters = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _style_index(fmt: str, bold: bool) -> int:
    if fmt not in FORMATS:
        raise ValueError(f"unknown cell format {fmt!r}")
    return FORMATS.index(fmt) * 2 + (1 if bold else 0)


def _cell_xml(ref: str, cell: Cell) -> str:
    fmt, bold, value = "general", False, cell
    if isinstance(cell, StyledCell):
        fmt, bold, value = cell.fmt, cell.bold, cell.value
    style = _style_index(fmt, bold)
    attr = f' s="{style}"' if style else ""
    if value is None:
        return f'<c r="{ref}"{attr}/>' if style else ""
    if isinstance(value, bool):
        return f'<c r="{ref}"{attr} t="b"><v>{int(value)}</v></c>'
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return f'<c r="{ref}"{attr}/>' if style else ""
        return f'<c r="{ref}"{attr}><v>{value!r}</v></c>'
    text = clean_text(str(value)[:MAX_CELL_TEXT])
    return f'<c r="{ref}"{attr} t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def _sheet_xml(rows: Rows, widths: Sequence[float] | None, freeze: int = 0) -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    ]
    if freeze > 0:
        top = f"A{freeze + 1}"
        parts.append(
            '<sheetViews><sheetView workbookViewId="0">'
            f'<pane ySplit="{freeze}" topLeftCell="{top}" activePane="bottomLeft" state="frozen"/>'
            f'<selection pane="bottomLeft" activeCell="{top}" sqref="{top}"/>'
            "</sheetView></sheetViews>"
        )
    if widths:
        parts.append("<cols>")
        for i, width in enumerate(widths, 1):
            parts.append(f'<col min="{i}" max="{i}" width="{float(width)!r}" customWidth="1"/>')
        parts.append("</cols>")
    parts.append("<sheetData>")
    for r, row in enumerate(rows, 1):
        cells = "".join(_cell_xml(f"{column_letter(c)}{r}", cell) for c, cell in enumerate(row))
        parts.append(f'<row r="{r}">{cells}</row>' if cells else f'<row r="{r}"/>')
    parts.append("</sheetData></worksheet>")
    return "".join(parts)


def _styles_xml() -> str:
    num_fmts = "".join(
        f'<numFmt numFmtId="{i}" formatCode="{clean_text(code)}"/>'
        for i, code in NUM_FMT_CODES.items()
    )
    xfs = []
    for fmt in FORMATS:
        fmt_id = NUM_FMT_IDS[fmt]
        apply = ' applyNumberFormat="1"' if fmt_id else ""
        for bold in (0, 1):
            font = ' applyFont="1"' if bold else ""
            xfs.append(
                f'<xf numFmtId="{fmt_id}" fontId="{bold}" fillId="0" borderId="0" xfId="0"'
                f"{apply}{font}/>"
            )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<numFmts count="{len(NUM_FMT_CODES)}">{num_fmts}</numFmts>'
        '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        f'<cellXfs count="{len(xfs)}">{"".join(xfs)}</cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>"
    )


def _workbook_parts(names: Sequence[str]) -> dict[str, str]:
    head = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pkg_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    sheets = "".join(
        f'<sheet name="{clean_text(name)}" sheetId="{i}" r:id="rId{i}"/>'
        for i, name in enumerate(names, 1)
    )
    sheet_rels = "".join(
        f'<Relationship Id="rId{i}" Type="{rel_ns}/worksheet" Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, len(names) + 1)
    )
    styles_id = len(names) + 1
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/'
        'vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, len(names) + 1)
    )
    return {
        "[Content_Types].xml": head
        + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/'
        'vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/'
        'vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f"{overrides}</Types>",
        "_rels/.rels": head
        + f'<Relationships xmlns="{pkg_ns}">'
        f'<Relationship Id="rId1" Type="{rel_ns}/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>",
        "xl/workbook.xml": head
        + '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'xmlns:r="{rel_ns}"><sheets>{sheets}</sheets></workbook>',
        "xl/_rels/workbook.xml.rels": head
        + f'<Relationships xmlns="{pkg_ns}">{sheet_rels}'
        f'<Relationship Id="rId{styles_id}" Type="{rel_ns}/styles" Target="styles.xml"/>'
        "</Relationships>",
        "xl/styles.xml": _styles_xml(),
    }


def write_xlsx(
    path: str | Path,
    sheets: Sequence[tuple[str, Rows]],
    col_widths: Mapping[str, Sequence[float]] | None = None,
    freeze_rows: Mapping[str, int] | None = None,
) -> Path:
    """Write sheets, a list of (name, rows), to path. col_widths maps a sheet's given name
    to its column widths in characters; freeze_rows to how many top rows stay visible when
    scrolling. Returns the path written."""
    if not sheets:
        raise ValueError("a workbook needs at least one sheet")
    used: set[str] = set()
    names = [sheet_name(name, i, used) for i, (name, _) in enumerate(sheets, 1)]
    parts = _workbook_parts(names)
    for i, (given, rows) in enumerate(sheets, 1):
        widths = (col_widths or {}).get(given)
        parts[f"xl/worksheets/sheet{i}.xml"] = _sheet_xml(rows, widths, (freeze_rows or {}).get(given, 0))
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, body in parts.items():
            info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, body.encode("utf-8"))
    return out
