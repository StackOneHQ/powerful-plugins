"""The workday-flex-credits XLSX writer produces valid, deterministic, values-only workbooks."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

SCRIPTS = Path(__file__).resolve().parents[1] / (
    "plugins/calculators/workday-flex-credits/skills/flex-credit-forecast/scripts"
)
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REQUIRED = {
    "[Content_Types].xml", "_rels/.rels", "xl/workbook.xml", "xl/_rels/workbook.xml.rels", "xl/styles.xml",
}


sys.dont_write_bytecode = True  # keep __pycache__ out of the plugin folder


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


wfc_xlsx = _load("wfc_xlsx", SCRIPTS / "xlsx_writer.py")
sys.modules["xlsx_writer"] = wfc_xlsx
forecast = _load("wfc_forecast", SCRIPTS / "forecast.py")


class XlsxWriterTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def _write(
        self, name: str, sheets: Sequence[tuple[str, Sequence[Sequence[object]]]], widths: dict[str, list[float]] | None = None
    ) -> Path:
        return Path(wfc_xlsx.write_xlsx(self.root / name, sheets, widths))

    def test_valid_zip_with_required_parts_and_parseable_sheets(self) -> None:
        cell = wfc_xlsx.StyledCell
        path = self._write("a.xlsx", [
            ("Summary", [[cell("Label", "text", True), cell(1234.5, "credits")], ["Share", cell(0.25, "pct")]]),
            ("Second", [[1, 2.5, None, True]]),
        ], {"Summary": [30, 12]})
        with zipfile.ZipFile(path) as archive:
            self.assertIsNone(archive.testzip())
            names = set(archive.namelist())
            self.assertTrue(REQUIRED <= names, names)
            self.assertIn("xl/worksheets/sheet1.xml", names)
            self.assertIn("xl/worksheets/sheet2.xml", names)
            self.assertNotIn("xl/sharedStrings.xml", names)
            for name in names:
                ET.fromstring(archive.read(name))
            sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        values = [v.text for v in sheet.iterfind(".//m:c/m:v", NS)]
        self.assertEqual(values, ["1234.5", "0.25"])
        self.assertIsNone(sheet.find(".//m:f", NS))

    def test_text_survives_escaping_and_never_becomes_a_formula(self) -> None:
        tricky = ["A & B", "x < y > z", "=SUM(A1)", '"quoted"', "+1", "-2", "@cmd", "bell\x07gone"]
        path = self._write("t.xlsx", [("Text", [tricky])])
        with zipfile.ZipFile(path) as archive:
            sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        cells = sheet.findall(".//m:c", NS)
        self.assertTrue(all(c.get("t") == "inlineStr" for c in cells))
        texts = [t.text for t in sheet.iterfind(".//m:is/m:t", NS)]
        self.assertEqual(texts, ["A & B", "x < y > z", "=SUM(A1)", '"quoted"', "+1", "-2", "@cmd", "bellgone"])
        self.assertIsNone(sheet.find(".//m:f", NS))

    def test_sheet_names_are_sanitized_capped_and_unique(self) -> None:
        long_name = "A very long sheet name that goes past thirty-one characters"
        path = self._write("n.xlsx", [(long_name, [[1]]), ("Bad[]:*?/\\Name", [[2]]), ("bad name", [[3]]),
                                      ("Bad Name", [[4]]), ("", [[5]])])
        with zipfile.ZipFile(path) as archive:
            book = ET.fromstring(archive.read("xl/workbook.xml"))
        names = [s.get("name") for s in book.iterfind(".//m:sheet", NS)]
        self.assertEqual(names[0], long_name[:31])
        self.assertEqual(names[1], "BadName")
        self.assertEqual(names[2], "bad name")
        self.assertEqual(names[3], "Bad Name (2)")
        self.assertEqual(names[4], "Sheet5")
        for name in names:
            assert name is not None
            self.assertLessEqual(len(name), 31)
            self.assertFalse(set(name) & set("[]:*?/\\"))

    def test_two_writes_give_identical_bytes(self) -> None:
        sheets = [("S", [["x", 1.5, wfc_xlsx.StyledCell(3, "usd", True)]])]
        first = self._write("1.xlsx", sheets).read_bytes()
        second = self._write("2.xlsx", sheets).read_bytes()
        self.assertEqual(first, second)
        with zipfile.ZipFile(self.root / "1.xlsx") as archive:
            self.assertTrue(all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in archive.infolist()))
            self.assertTrue(all(i.compress_type == zipfile.ZIP_DEFLATED for i in archive.infolist()))

    def test_money_formats_and_long_text(self) -> None:
        cell = wfc_xlsx.StyledCell
        path = self._write("m.xlsx", [("S", [[cell(25500.0, "usd_whole"), cell(0.4, "usd"), "x" * 40000]])])
        with zipfile.ZipFile(path) as archive:
            styles = archive.read("xl/styles.xml").decode()
            sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        self.assertIn('formatCode="&quot;$&quot;#,##0"', styles)
        text = sheet.find(".//m:is/m:t", NS)
        assert text is not None and text.text is not None
        self.assertEqual(len(text.text), 32767)

    def test_unknown_format_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._write("bad.xlsx", [("S", [[wfc_xlsx.StyledCell(1, "euros")]])])

    def test_forecast_workbook_has_the_seven_sheets(self) -> None:
        example = json.loads((SCRIPTS / "example_input.json").read_text())
        res = forecast.build_result(example)
        # The writer forecast.py imported, so its StyledCell class matches the cells it built.
        path = forecast.xlsx_writer.write_xlsx(self.root / "f.xlsx", forecast.build_sheets(res), forecast.COL_WIDTHS, forecast.FREEZE_ROWS)
        with zipfile.ZipFile(path) as archive:
            self.assertIsNone(archive.testzip())
            book = ET.fromstring(archive.read("xl/workbook.xml"))
            names = [s.get("name") for s in book.iterfind(".//m:sheet", NS)]
            self.assertEqual(names, ["Summary", "By month", "By year", "Inputs", "Agents", "Assumptions",
                                     "Open questions"])
            by_month = ET.fromstring(archive.read("xl/worksheets/sheet2.xml"))
            summary = archive.read("xl/worksheets/sheet1.xml").decode()
        pane = by_month.find(".//m:sheetView/m:pane", NS)
        assert pane is not None
        self.assertEqual((pane.get("ySplit"), pane.get("state")), ("1", "frozen"))
        rows = by_month.findall(".//m:sheetData/m:row", NS)
        self.assertGreaterEqual(len(rows), 1 + 24 + 1)
        self.assertIn("not produced or endorsed by Workday", summary)


if __name__ == "__main__":
    unittest.main()
