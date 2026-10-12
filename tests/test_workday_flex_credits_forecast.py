"""Golden vectors and behaviour of the workday-flex-credits forecast script."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any

SCRIPTS = Path(__file__).resolve().parents[1] / (
    "plugins/calculators/workday-flex-credits/skills/flex-credit-forecast/scripts"
)
CONSTANTS_PATH = SCRIPTS / "model_constants.json"
EXAMPLE = SCRIPTS / "example_input.json"
VERSION = "2026-10-09-r2"
# The shared model file, byte for byte. A new constants version changes this hash on purpose.
CONSTANTS_SHA256 = "927a04391b06ff96326a42187def04422e811e35638be53aa22662faa7dd228d"


sys.dont_write_bytecode = True  # keep __pycache__ out of the plugin folder


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_load("xlsx_writer", SCRIPTS / "xlsx_writer.py")
forecast = _load("wfc_forecast", SCRIPTS / "forecast.py")
DATA: dict[str, Any] = json.loads(CONSTANTS_PATH.read_text())
TOL = DATA["constants"]["tolerance"]


def _tolerance(key: str) -> float:
    if "usd" in key:
        return float(TOL["usd"])
    if key in ("allowance_used_ratio", "pool_months_of_cover"):
        return float(TOL["ratio"]) * 10
    if "calls" in key:
        return float(TOL["calls"])
    return float(TOL["credits"])


class Comparison(unittest.TestCase):
    def assertClose(self, actual: Any, expected: Any, where: str) -> None:
        if isinstance(expected, dict):
            for key, value in expected.items():
                self.assertIn(key, actual, f"{where}.{key} missing")
                self.assertClose(actual[key], value, f"{where}.{key}")
        elif isinstance(expected, list):
            self.assertEqual(len(actual), len(expected), f"{where}: length")
            for i, value in enumerate(expected):
                self.assertClose(actual[i], value, f"{where}[{i}]")
        elif isinstance(expected, float) or (isinstance(expected, int) and not isinstance(expected, bool)):
            key = where.rsplit(".", 1)[-1].split("[")[0]
            self.assertIsInstance(actual, (int, float), where)
            self.assertAlmostEqual(actual, expected, delta=_tolerance(key), msg=where)
        else:
            self.assertEqual(actual, expected, where)


class GoldenVectorTests(Comparison):
    def test_there_are_18_compute_and_3_forecast_vectors(self) -> None:
        vectors = DATA["vectors"]
        self.assertEqual(len([v for v in vectors if "expected" in v]), 18)
        self.assertEqual(len([v for v in vectors if "expected_forecast" in v]), 3)

    def test_compute_vectors(self) -> None:
        for vec in DATA["vectors"]:
            if "expected" not in vec:
                continue
            with self.subTest(vector=vec["id"]):
                self.assertClose(forecast.compute(copy.deepcopy(vec["input"])), vec["expected"], vec["id"])

    def test_forecast_vectors_including_months_and_range(self) -> None:
        for vec in DATA["vectors"]:
            if "expected_forecast" not in vec:
                continue
            with self.subTest(vector=vec["id"]):
                result = forecast.run_forecast(copy.deepcopy(vec["input"]))
                self.assertClose(result, vec["expected_forecast"], vec["id"])

    def test_preset_workday_agents_needs_315000_and_buys_255000(self) -> None:
        preset = DATA["presets"]["workday_agents"]["input"]
        result = forecast.compute(copy.deepcopy(preset))
        self.assertAlmostEqual(result["credits"]["total"], 315000, delta=0.01)
        self.assertAlmostEqual(result["shortfall_credits"], 255000, delta=0.01)


class ConstantsTests(unittest.TestCase):
    def test_version(self) -> None:
        self.assertEqual(DATA["constants"]["version"], VERSION)
        self.assertEqual(forecast.load_constants()["version"], VERSION)

    def test_bundled_copy_is_the_shared_model_file(self) -> None:
        self.assertEqual(hashlib.sha256(CONSTANTS_PATH.read_bytes()).hexdigest(), CONSTANTS_SHA256)
        self.assertEqual(forecast.HERE / "model_constants.json", CONSTANTS_PATH)
        self.assertEqual(forecast.load_constants(), DATA["constants"])

    def test_unknown_version_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = copy.deepcopy(DATA)
            bad["constants"]["version"] = "1999-01-01"
            path = Path(tmp) / "c.json"
            path.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                forecast.load_constants(path)


class UnitTests(unittest.TestCase):
    def test_pattern_anchors_at_10000_employees(self) -> None:
        self.assertEqual(forecast.pattern_calls("typical", 10000), 876000)
        self.assertEqual(forecast.pattern_calls("heavy", 10000), 10512000)
        self.assertEqual(forecast.pattern_calls("efficient", 10000), 35612)

    def test_inventory_item_from_runs_records_and_page(self) -> None:
        items = [{"name": "Payroll sync", "runs_per_year": 8760, "records_per_run": 10000, "page_size": 100}]
        self.assertEqual(forecast.inventory_calls(items, 10000), 876000)

    def test_inventory_mixes_shapes(self) -> None:
        items = [
            {"name": "A", "calls_per_year": 1000},
            {"name": "B", "pattern": "typical"},
            {"name": "C", "runs_per_year": 365, "records_per_run": 250, "page_size": 100, "writes_per_year": 5},
        ]
        self.assertEqual(forecast.inventory_calls(items, 10000), 1000 + 876000 + 365 * 3 + 5)

    def test_inventory_mode_feeds_compute_as_measured_calls(self) -> None:
        inp = copy.deepcopy(DATA["presets"]["integrations"]["input"])
        inp["integrations"] = {"mode": "inventory", "items": [{"name": "A", "calls_per_year": 5000000}]}
        self.assertEqual(forecast.compute(inp)["integration_calls"], 5000000)

    def test_confidence_levels(self) -> None:
        self.assertEqual(forecast.confidence({"allowance": "console", "pool": "contract", "api_calls": "console"}), "high")
        self.assertEqual(forecast.confidence({"allowance": "console", "pool": "default", "api_calls": "user"}), "medium")
        self.assertEqual(forecast.confidence({}), "low")

    def test_validate_rejects_bad_input(self) -> None:
        inp = copy.deepcopy(DATA["presets"]["build"]["input"])
        inp["employees"] = -5
        inp["agents"][0]["path"] = "warp"
        inp["agents"][0]["advanced_share"] = 1.5
        errors = forecast.validate(inp)
        self.assertTrue(any(e.startswith("employees:") for e in errors), errors)
        self.assertTrue(any(e.startswith("agents[0].path:") for e in errors), errors)
        self.assertTrue(any(e.startswith("agents[0].advanced_share:") for e in errors), errors)

    def test_validate_accepts_presets_unsure_and_the_example(self) -> None:
        for key, preset in DATA["presets"].items():
            with self.subTest(preset=key):
                self.assertEqual(forecast.validate(preset["input"]), [])
        inp = copy.deepcopy(DATA["presets"]["buy"]["input"])
        inp["agents"][0]["path"] = "unsure"
        self.assertEqual(forecast.validate(inp), [])
        self.assertEqual(forecast.validate(json.loads(EXAMPLE.read_text())), [])

    def test_validate_rejects_bad_dates_and_months(self) -> None:
        inp = {"forecast": {"start": "2026-13", "months": 0,
                            "purchased_packages": [{"credits": 10, "from": "2027-05", "to": "2027-01"}]}}
        errors = forecast.validate(inp)
        self.assertTrue(any(e.startswith("forecast.start:") for e in errors), errors)
        self.assertTrue(any(e.startswith("forecast.months:") for e in errors), errors)
        self.assertTrue(any("'from' is after 'to'" in e for e in errors), errors)

    def test_unsure_path_reports_both_figures(self) -> None:
        inp = copy.deepcopy(DATA["presets"]["build"]["input"])
        inp["agents"][0]["path"] = "unsure"
        inp["forecast"] = {"start": "2027-02", "months": 12}
        res = forecast.build_result(inp)
        self.assertEqual(set(res["path_variants"]), {"api", "tools_external"})
        self.assertEqual(res["headline_path"], "tools_external")
        api = res["path_variants"]["api"]["totals"]
        tools = res["path_variants"]["tools_external"]["totals"]
        self.assertGreater(tools["credits_needed"], api["credits_needed"])
        report = forecast.render_report(res)
        self.assertIn("Through Workday APIs instead", report)
        self.assertIn(f"{round(api['credits_needed']):,} credits", report)

    def test_default_forecast_block_is_next_month_for_12_months(self) -> None:
        import datetime as dt

        settings = forecast.forecast_settings({}, today=dt.date(2026, 12, 15))
        self.assertEqual(settings["start"], "2027-01")
        self.assertEqual(settings["months"], 12)

    def test_report_has_sections_in_order_and_numbered_assumptions(self) -> None:
        res = forecast.build_result(json.loads(EXAMPLE.read_text()))
        report = forecast.render_report(res)
        self.assertTrue(report.startswith("# Workday Flex Credits forecast: Example Retail Co\n"))
        headings = [line for line in report.splitlines() if line.startswith("## ")]
        self.assertEqual(headings, [
            "## Assumptions", "## Month by month", "## Year by year", "## Where the credits go",
            "## Agents and the path comparison", "## Integrations", "## Inputs and sources",
            "## Questions to ask Workday", "## Levers",
        ])
        self.assertIn("1. Workday doesn't publish a price per credit.", report)
        self.assertIn("reset on 1 January", report)
        self.assertIn("not produced or endorsed by Workday", report)
        self.assertNotIn("—", report)
        self.assertNotIn("<!--", report)

    def test_headline_shape(self) -> None:
        res = forecast.build_result(json.loads(EXAMPLE.read_text()))
        self.assertRegex(
            res["headline"],
            r"^[\d,]+ credits in the next 24 months \(range [\d,]+ to [\d,]+, confidence low\)\. "
            r"[\d,]+ to buy, about \$[\d,]+ at \$0\.10 a credit\. Free credits run out in \w+ \d{4}\. "
            r"Biggest driver: .+\.$",
        )

    def test_levers_are_ordered_by_credits_saved(self) -> None:
        res = forecast.build_result(json.loads(EXAMPLE.read_text()))
        saved = [lever["credits_saved"] for lever in res["levers"]]
        self.assertEqual(saved, sorted(saved, reverse=True))
        self.assertTrue(res["levers"])

    def test_scripts_make_no_network_calls(self) -> None:
        banned = {"urllib", "http", "socket", "requests", "ftplib", "smtplib", "ssl", "subprocess"}
        for path in SCRIPTS.glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                for name in names:
                    self.assertNotIn(name.split(".")[0], banned, f"{path.name} imports {name}")


class CommandLineTests(unittest.TestCase):
    def test_example_writes_three_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = subprocess.run(
                [sys.executable, str(SCRIPTS / "forecast.py"), "--input", str(EXAMPLE), "--out-dir", tmp],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            names = sorted(p.name for p in Path(tmp).iterdir())
            self.assertEqual(names, ["forecast.xlsx", "report.md", "result.json"])
            out = run.stdout.strip().splitlines()
            result = json.loads((Path(tmp) / "result.json").read_text())
            self.assertLessEqual(len(out), 11)
            self.assertEqual(out[0], result["headline"])
            self.assertEqual(out[:-1], result["chat_summary"])
            self.assertTrue(out[-1].startswith("Files: "))
            self.assertEqual(out[-1].count(tmp), 3)
            self.assertEqual(result["confidence"], "low")

    def test_bad_input_exits_2_with_one_line_per_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text(json.dumps({"employees": -1, "skus": ["bogus"]}))
            run = subprocess.run(
                [sys.executable, str(SCRIPTS / "forecast.py"), "--input", str(bad), "--out-dir", tmp],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(run.returncode, 2)
            self.assertEqual(len(run.stderr.strip().splitlines()), 2, run.stderr)
            self.assertFalse((Path(tmp) / "result.json").exists())


def _with_forecast(key: str, **forecast_block: Any) -> dict[str, Any]:
    inp = copy.deepcopy(DATA["presets"][key]["input"])
    inp["forecast"] = {"start": "2026-11", "months": 12, **forecast_block}
    return inp


class ReviewFixTests(unittest.TestCase):
    def test_path_comparison_row_in_use_matches_the_first_forecast_year(self) -> None:
        for key, extra in (("build", {"purchased_packages": [{"credits": 50000, "from": "2026-11", "to": "2027-10"}]}),
                           ("buy", {})):
            with self.subTest(preset=key):
                inp = _with_forecast(key, **extra)
                inp["integrations"]["counts"] = {"efficient": 4, "typical": 4, "heavy": 1}
                res = forecast.build_result(inp)
                current = [r for r in res["agent_paths"] if r["current"]]
                self.assertEqual(len(current), 1)
                self.assertAlmostEqual(current[0]["to_buy"], res["years"][0]["to_buy"], delta=0.01)
                self.assertAlmostEqual(current[0]["credits_needed"], res["years"][0]["credits_needed"], delta=0.01)

    def test_clamped_values_are_reported_not_silent(self) -> None:
        inp = _with_forecast("workday_agents")
        inp["employees"] = 2_100_000
        inp["advanced"]["context_rereads"] = 10
        res = forecast.build_result(inp)
        self.assertTrue(any(a.startswith("Employees: 2,100,000 is above the model's 500,000 cap") for a in res["adjusted"]))
        self.assertTrue(any(a.startswith("Context re-reads: 10") for a in res["adjusted"]))
        self.assertEqual(res["assumed"][: len(res["adjusted"])], res["adjusted"])
        self.assertIn("Adjusted by the model", [r[0] for r in res["inputs"]])
        self.assertIn("is above the model's 500,000 cap", forecast.render_report(res))

    def test_impossible_minimums_are_rejected(self) -> None:
        inp = copy.deepcopy(DATA["presets"]["build"]["input"])
        inp.update(employees=50, price_per_credit=0)
        inp["agents"][0]["calls_per_task"] = 0
        errors = forecast.validate(inp)
        for key in ("employees:", "price_per_credit:", "agents[0].calls_per_task:"):
            self.assertTrue(any(e.startswith(key) for e in errors), (key, errors))

    def test_wrong_shapes_and_overflows_exit_2_without_a_traceback(self) -> None:
        cases: list[dict[str, Any]] = [
            {"skus": 5}, {"skills": 3}, {"agents": "x"}, {"integrations": "x"}, {"advanced": [1]},
            {"integrations": {"counts": [1]}}, {"forecast": {"growth": "fast"}}, {"sources": ["user"]},
            {"forecast": {"start": "0000-01"}}, {"forecast": {"start": "9999-12", "months": 60}},
            {"forecast": {"growth": {"agents": 1e200}}},
            {"integrations": {"mode": "inventory", "items": [{"name": "A", "runs_per_year": 1e308,
                                                             "records_per_run": 1e308, "page_size": 1e-300}]}},
            {"integrations": {"mode": "inventory", "items": [{"name": "A", "runs_per_year": 100}]}},
            {"contract_notes": "rollover"}, "not an object",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            for i, case in enumerate(cases):
                with self.subTest(case=case):
                    path = Path(tmp) / f"c{i}.json"
                    path.write_text(json.dumps(case))
                    run = subprocess.run(
                        [sys.executable, str(SCRIPTS / "forecast.py"), "--input", str(path), "--out-dir", tmp],
                        capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(run.returncode, 2, run.stderr)
                    self.assertNotIn("Traceback", run.stderr)

    def test_report_escapes_untrusted_names(self) -> None:
        inp = _with_forecast("integrations")
        inp["organization"] = "Acme\n# Injected heading"
        inp["integrations"] = {"mode": "inventory", "items": [
            {"name": "![img](http://example.invalid/p.png)", "calls_per_year": 1000},
            {"name": "<script>x</script>", "calls_per_year": 1000},
        ]}
        inp["contract_notes"] = ["Unused credits roll over [see](http://example.invalid)"]
        report = forecast.render_report(forecast.build_result(inp))
        self.assertFalse(any(line.startswith("# Injected") for line in report.splitlines()))
        self.assertTrue(report.startswith("# Workday Flex Credits forecast: Acme \\# Injected heading\n"))
        self.assertNotIn("![img](", report)
        self.assertNotIn("<script>", report)
        self.assertNotIn("[see](", report)

    def test_contract_notes_reach_report_workbook_and_questions(self) -> None:
        inp = _with_forecast("workday_agents")
        inp["contract_notes"] = ["Unused Flex Credits may be carried over once, up to 10%."]
        res = forecast.build_result(inp)
        self.assertIn(["Contract wording not modelled", inp["contract_notes"][0], "contract",
                       "Not in the numbers; listed in the questions for Workday"], res["inputs"])
        asked = [q["question"] for q in res["open_questions"] if q["applies"]]
        self.assertTrue(any("carried over once" in q for q in asked))
        self.assertIn("Contract wording not modelled", forecast.render_report(res))

    def test_small_prices_display_exactly(self) -> None:
        self.assertEqual(forecast.fmt_price(0.005), "$0.005")
        self.assertEqual(forecast.fmt_price(0.1), "$0.10")
        self.assertEqual(forecast.fmt_price(0.075), "$0.075")
        inp = _with_forecast("workday_agents")
        inp["price_per_credit"] = 0.005
        sheets = dict(forecast.build_sheets(forecast.build_result(inp)))
        self.assertIn(["Price per credit", "$0.005"], sheets["Summary"])

    def test_expiring_purchased_credits_are_surfaced(self) -> None:
        inp = _with_forecast("workday_agents", purchased_packages=[{"credits": 500000, "from": "2026-11", "to": "2027-10"}])
        res = forecast.build_result(inp)
        self.assertEqual(len(res["expiring_unused"]), 1)
        self.assertEqual(res["expiring_unused"][0]["month"], "2027-10")
        self.assertIn("purchased credits (about $", res["headline"])
        self.assertIn("expire unused in October 2027", res["headline"])
        self.assertIn("Nothing to buy: your free and purchased credits cover it.", res["headline"])
        self.assertNotIn("Free credits run out", res["headline"])
        self.assertIn("Package expires:", forecast.render_report(res))

    def test_buying_more_wording_when_packages_run_out(self) -> None:
        inp = _with_forecast("workday_agents", purchased_packages=[{"credits": 10000, "from": "2026-11", "to": "2027-10"}])
        res = forecast.build_result(inp)
        self.assertIn("You start buying more in", res["headline"])

    def test_confidence_follows_sources_not_values(self) -> None:
        firm = {"allowance": "console", "complimentary": "console", "api_calls": "contract"}
        self.assertEqual(forecast.confidence(firm, "api_overage"), "high")
        self.assertEqual(forecast.confidence({**firm, "workday_agents": "default"}, "workday_agents_ssa"), "low")
        self.assertEqual(forecast.confidence({"api_calls": "user", "allowance": "user"}, None), "low")
        inp = _with_forecast("workday_agents")
        inp["sources"] = {"pool": "contract"}
        inp["forecast"]["purchased_packages"] = [{"credits": 1000, "from": "2026-11", "to": "2027-10"}]
        src = forecast.effective_sources(inp)
        self.assertEqual((src["complimentary"], src["purchased"]), ("contract", "contract"))
        inp["sources"] = {"purchased": "contract"}
        src = forecast.effective_sources(inp)
        self.assertEqual((src["complimentary"], src["purchased"]), ("default", "contract"))
        inp["sources"] = {"api_calls": "default"}
        inp["integrations"] = {"mode": "measured", "calls_per_year": 1000}
        self.assertEqual(forecast.effective_sources(inp)["api_calls"], "default")

    def test_contracted_ten_cent_price_is_not_called_a_default(self) -> None:
        inp = _with_forecast("workday_agents")
        inp["sources"] = {"price_per_credit": "contract"}
        res = forecast.build_result(inp)
        self.assertIsNone(res["low_price_note"])
        self.assertFalse(any(a.startswith("Price per credit") for a in res["assumed"]))

    def test_assumed_names_the_extend_uplift_and_the_opening_balance(self) -> None:
        res = forecast.build_result(_with_forecast("buy"))
        allowance = next(a for a in res["assumed"] if a.startswith("API allowance"))
        self.assertIn("4,500,000", allowance)
        self.assertIn("x 1.5 for Extend = 6,750,000", allowance)
        self.assertIn("Extend assumed", allowance)
        self.assertTrue(any(a.startswith("Free credits left at the start: 10,000 (2/12 of the yearly 60,000")
                            for a in res["assumed"]))

    def test_unsure_note_gives_each_paths_allowance(self) -> None:
        inp = _with_forecast("buy")
        inp["agents"][0]["path"] = "unsure"
        note = forecast.build_result(inp)["path_note"]
        self.assertIn("allowance 6,750,000, with the Extend uplift", note)
        self.assertIn("allowance 4,500,000, no Extend uplift", note)

    def test_chat_summary_is_at_most_12_lines(self) -> None:
        inp = _with_forecast("buy", months=36, purchased_packages=[{"credits": 900000, "from": "2026-11", "to": "2027-10"}])
        inp["agents"][0]["path"] = "unsure"
        inp["employees"] = 900000
        res = forecast.build_result(inp)
        self.assertLessEqual(len(res["chat_summary"]) + 2, 12)
        self.assertEqual(res["chat_summary"][0], res["headline"])

    def test_skill_requires_the_injection_row_and_privacy_line_on_contract_reads(self) -> None:
        skill = SCRIPTS.parent
        sources = (skill / "references" / "data-sources.md").read_text()
        flat = " ".join(sources.split())
        self.assertIn("| Text addressed to AI tools (not followed) |", sources)
        self.assertIn("Always include this row", flat)
        self.assertIn("Open your reply with the privacy line", flat)
        text = " ".join((skill / "SKILL.md").read_text().replace("> ", "").split())
        self.assertIn("The forecast files are written only to ./flex-credit-forecast/ on your machine", text)
        self.assertIn("first shows anything read from a contract", text)

    def test_no_bytecode_written_beside_the_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([sys.executable, str(SCRIPTS / "forecast.py"), "--input", str(EXAMPLE), "--out-dir", tmp],
                           capture_output=True, check=True)
        self.assertFalse((SCRIPTS / "__pycache__").exists())

    def test_half_dollars_round_up_consistently(self) -> None:
        self.assertEqual(forecast.fmt_usd(137932.5), "$137,933")
        self.assertEqual(forecast.fmt_usd(144997.5), "$144,998")
        self.assertEqual(forecast.fmt_usd(2.125), "$2.13")
        self.assertEqual(forecast.fmt_credits(2.5), "3")
        self.assertEqual(forecast.fmt_credits(3.5), "4")

    def test_customer_sizing_is_computed_by_the_script(self) -> None:
        inp = _with_forecast("buy")
        inp["agents"][0]["path"] = "unsure"
        inp["customer_sizing"] = True
        res = forecast.build_result(inp)
        ag = res["customer_sizing"]["agents"][0]
        self.assertAlmostEqual(ag["credits_per_task"]["tools_external"], 0.7, places=9)
        self.assertAlmostEqual(ag["credits_per_task"]["extend_custom"], 2.35, places=9)
        self.assertAlmostEqual(ag["credits_per_task"]["api"], 0.0, places=9)
        self.assertAlmostEqual(ag["api_credits_per_task_above_allowance"], 0.03, places=9)
        mid = next(b for b in ag["bands"] if b["band"] == "10,000 to 29,999")
        expected_used = 3 * forecast.pattern_calls("efficient", 15000) + 2 * forecast.pattern_calls("typical", 15000)
        self.assertEqual(mid["integration_calls"], expected_used)
        self.assertAlmostEqual(mid["tasks_per_month_that_fit"], (4_500_000 - expected_used) / 60)
        self.assertTrue(any(line.startswith("Per task, agent 1") for line in res["chat_summary"]))
        self.assertTrue(any(line.startswith("Tasks a month that fit") for line in res["chat_summary"]))
        self.assertLessEqual(len(res["chat_summary"]), 10)
        self.assertIn("## Sizing for your customers", forecast.render_report(res))
        self.assertIsNone(forecast.build_result(_with_forecast("buy"))["customer_sizing"])
        self.assertTrue(any(e.startswith("customer_sizing:") for e in forecast.validate({"customer_sizing": "yes"})))

    def test_first_reply_is_capped_at_the_summary(self) -> None:
        text = " ".join((SCRIPTS.parent / "SKILL.md").read_text().split())
        self.assertIn("The first-forecast reply is that and nothing else", text)


if __name__ == "__main__":
    unittest.main()
