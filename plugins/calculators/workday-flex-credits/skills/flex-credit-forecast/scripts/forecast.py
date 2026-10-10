#!/usr/bin/env python3
"""Forecast Workday Flex Credit use and cost month by month.

usage: forecast.py --input input.json --out-dir DIR [--formats xlsx,md,json] [--constants PATH]

Reads an input JSON (format in references/model.md), validates it, and writes result.json,
report.md and forecast.xlsx (and forecast_by_month.csv with --formats ...,csv) to DIR.
Standard library only, no network calls. Exits 2 with one line per problem on bad input.
"""

from __future__ import annotations

import argparse
import copy
import csv
import datetime as dt
import json
import math
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Union

# Keep the installed plugin folder free of __pycache__ when the sibling module is imported.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import xlsx_writer  # noqa: E402
from xlsx_writer import StyledCell  # noqa: E402

Json = dict[str, Any]
Cell = Union[str, int, float, bool, None, StyledCell]  # noqa: UP007

HERE = Path(__file__).resolve().parent
SUPPORTED_VERSIONS = ("2026-10-09-r2",)
SOURCE_VALUES = ("console", "contract", "user", "default")
SOURCE_KEYS = (
    "allowance", "complimentary", "purchased", "api_calls", "price_per_credit", "employees", "skus",
    "agents", "workday_agents", "policy_signed", "forecast_start", "growth", "rates", "model_price",
)
CONFIDENCE_KEYS = ("allowance", "complimentary", "api_calls")
FIRM_SOURCES = ("console", "contract")
# Which source stands behind each credit stream, for the confidence rule.
STREAM_SOURCES = {
    "api_overage": "api_calls",
    "workday_agents_ssa": "workday_agents",
    "workday_agents_skills": "workday_agents",
    "agent_tool_calls": "agents",
    "agent_invocations": "agents",
}
UNSURE = "unsure"
FORMATS = ("xlsx", "md", "json", "csv")
EPS = 0.005

STREAM_LABELS = {
    "api_overage": "API calls above your allowance",
    "workday_agents_ssa": "Self-Service Agent",
    "workday_agents_skills": "Other Workday agents",
    "agent_tool_calls": "Agent-Ready Tool calls",
    "agent_invocations": "Extend agent runs",
}
PATH_NAMES = {
    "api": "Workday APIs",
    "tools_external": "Workday's Agent-Ready Tools",
    "extend_custom": "Custom agent in Workday Extend",
}
PATH_INCLUDED = {
    "api": "Calls count against your yearly API allowance; credits only for calls above it "
    "({rate} a call, from {billable}). Model tokens paid to your model provider.",
    "tools_external": "Workday-hosted MCP tools at the rate card's non-Custom Agent rate (our "
    "reading). Needs Workday Extend Professional, so the Extend allowance uplift applies. "
    "Model tokens paid to your model provider.",
    "extend_custom": "Runs inside Workday Extend; invocation credits include the model, plus "
    "Agent-Ready Tool calls at the custom rate. Needs Workday Extend Professional.",
}
FLAG_WORDS = {
    "grace": "Grace period",
    "complimentary_reset": "Free credits reset",
    "complimentary_assumed": "Assumed after renewal",
    "allowance_year_start": "New allowance year",
}
CAVEATS = (
    "Workday doesn't publish a price per credit. Analysts estimate under $0.01 to $0.10; we "
    "start at $0.10. Use the price on your order form.",
    "Allowance bands and subscription uplifts come from analysts' reading of a policy Workday "
    "hasn't published.",
    "We count one request as one call: a page of results, a report run, a record written. "
    "Workday hasn't confirmed this.",
    "We read the rate card's 'non-Custom Agents' rate as applying to agents built outside "
    "Workday. Workday hasn't defined it publicly.",
    "We assume Agent-Ready Tool calls don't also count against your API allowance. Ask Workday.",
    "Extend custom agent credits include the model. Agents outside Workday pay their own model "
    "tokens.",
    "Token counts come from synthetic Workday payloads, input tokens only, and vary about 15% "
    "by tokenizer.",
    "API overage is billed from {billable}, the date analysts (Commit Consulting, Redress "
    "Compliance) report it becomes billable, and only for customers who've signed the Flex "
    "Credits and Platform Entitlement Policy. Earlier months are a grace period.",
    "Rates are from Workday's public Flex Credits rate card dated {card_date}. Workday says "
    "this rate card is informational; your order form's rate card governs.",
    "We count one agent task as one Extend invocation, and every Workday call it makes as an "
    "Agent-Ready Tool call. Workday's Developer Site defines invocation types.",
    "Agent-Ready Tools and custom agents need Workday Extend Professional, so we apply its "
    "allowance uplift when you choose them.",
    "Complimentary credits go to customers who accept the policy. Workday can change them at "
    "renewal.",
)
DISCLAIMER = (
    "Estimates, not a quote. This tool is not produced or endorsed by Workday. Workday and Flex "
    "Credits are trademarks of Workday, Inc."
)

_CONSTANTS: Json | None = None


def _fill(text: str, c: Json) -> str:
    """Put the dates and rate from the constants into fixed text, so it can't go stale."""
    billable = dt.date(int(c["api_billable_from"][:4]), int(c["api_billable_from"][5:7]), 1)
    card = dt.date.fromisoformat(c["rate_card_date"])
    return text.format(
        billable=f"1 {billable.strftime('%B %Y')}",
        billable_month=billable.strftime("%B %Y"),
        card_date=f"{card.day} {card.strftime('%B %Y')}",
        rate=f"{c['api_credits_per_call']:g}",
    )


# ---------------------------------------------------------------- constants


def load_constants(path: str | Path | None = None) -> Json:
    """Load model_constants.json (beside this script unless a path is given)."""
    target = Path(path) if path else HERE / "model_constants.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    version = data.get("constants", {}).get("version")
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(
            f"{target}: constants version {version!r} is not one this script knows "
            f"({', '.join(SUPPORTED_VERSIONS)})"
        )
    const: Json = data["constants"]
    return const


def _c(c: Json | None) -> Json:
    global _CONSTANTS
    if c is not None:
        return c
    if _CONSTANTS is None:
        _CONSTANTS = load_constants()
    return _CONSTANTS


# ---------------------------------------------------------------- sanitize and helpers


def _is_number(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _num(v: object, key: str, c: Json, clamp: bool = True) -> float:
    lo, hi, default = c["ranges"][key]
    if not _is_number(v):
        return float(default)
    value = float(v)  # type: ignore[arg-type]
    return float(min(max(value, lo), hi) if clamp else max(value, lo))


def pattern_calls(pattern: str, n: float) -> int:
    """Yearly calls for one integration of a pattern, reading n records."""
    if pattern == "efficient":
        return 35040 + 52 * math.ceil(n / 999)
    if pattern == "typical":
        return 8760 * math.ceil(n / 100)
    if pattern == "heavy":
        return 105120 * math.ceil(n / 100)
    raise ValueError(f"unknown integration pattern {pattern!r}")


def inventory_item_calls(item: Json, employees: float) -> float:
    """Calls a year for one inventory item (see references/model.md)."""
    if _is_number(item.get("calls_per_year")):
        return float(item["calls_per_year"])
    if item.get("pattern") is not None:
        records: Any = item.get("records")
        n = float(records) if _is_number(records) else employees
        return float(pattern_calls(item["pattern"], n))
    runs = float(item.get("runs_per_year") or 0)
    per_run = float(item.get("records_per_run") or 0)
    page = float(item.get("page_size") or 100)
    writes = float(item.get("writes_per_year") or 0)
    return runs * math.ceil(per_run / page) + writes


def inventory_calls(items: list[Json], employees: float) -> float:
    """Sum of calls a year across inventory items."""
    return float(sum(inventory_item_calls(item, employees) for item in items))


def sanitize(inp: Json, c: Json | None = None, clamp: bool = True) -> Json:
    """Nulls and junk take defaults, numbers clamp to constants.ranges, unknown enums take
    the default, unknown SKUs and skills are dropped. With clamp=False only minimums apply."""
    c = _c(c)
    d = c["defaults"]
    out = copy.deepcopy(inp)
    out["employees"] = _num(inp.get("employees"), "employees", c, clamp)
    out["price_per_credit"] = _num(inp.get("price_per_credit"), "price_per_credit", c, clamp)
    out["skus"] = [s for s in (inp.get("skus") or []) if s in c["sku_uplifts"]]
    integ = inp.get("integrations") or {}
    if integ.get("mode") == "inventory":
        calls = inventory_calls(integ.get("items") or [], out["employees"])
        out["integrations"] = {
            "mode": "measured",
            "calls_per_year": _num(calls, "integration_calls_per_year", c, clamp),
            "counts": None,
        }
    elif integ.get("mode") == "measured":
        out["integrations"] = {
            "mode": "measured",
            "calls_per_year": _num(integ.get("calls_per_year"), "integration_calls_per_year", c, clamp),
            "counts": None,
        }
    else:
        counts = integ.get("counts") or {}
        out["integrations"] = {
            "mode": "estimate",
            "calls_per_year": None,
            "counts": {
                p: _num(counts.get(p), "integration_count", c, clamp) for p in c["integration_patterns"]
            },
        }
    out["ssa_actions_per_employee_month"] = _num(
        inp.get("ssa_actions_per_employee_month"), "ssa_actions_per_employee_month", c, clamp
    )
    out["skills"] = [
        {"skill": s["skill"], "volume_per_year": _num(s.get("volume_per_year"), "skill_volume_per_year", c, clamp)}
        for s in (inp.get("skills") or [])
        if isinstance(s, dict) and s.get("skill") in c["workday_skills"]
    ]
    agents = []
    for ag in inp.get("agents") or []:
        agents.append({
            "tasks_per_month": _num(ag.get("tasks_per_month"), "tasks_per_month", c, clamp),
            "calls_per_task": _num(ag.get("calls_per_task"), "calls_per_task", c, clamp),
            "path": ag.get("path") if ag.get("path") in c["agent_paths"] else d["path"],
            "read_format": ag.get("read_format") if ag.get("read_format") in c["read_formats"] else d["read_format"],
            "advanced_share": _num(ag.get("advanced_share"), "advanced_share", c, clamp),
            "model_tier": ag.get("model_tier") if ag.get("model_tier") in ("base", "standard", "premium") else d["model_tier"],
        })
    out["agents"] = agents
    adv = inp.get("advanced") or {}
    out["advanced"] = {
        "purchased_credits": _num(adv.get("purchased_credits"), "purchased_credits", c, clamp),
        "policy_signed": adv.get("policy_signed") if isinstance(adv.get("policy_signed"), bool) else True,
        "llm_price_per_m_tokens": _num(adv.get("llm_price_per_m_tokens"), "llm_price_per_m_tokens", c, clamp),
        "context_rereads": _num(adv.get("context_rereads"), "context_rereads", c, clamp),
        "tool_calls_also_metered_as_api": adv.get("tool_calls_also_metered_as_api") is True,
        "allowance_override": adv.get("allowance_override"),
        "complimentary_override": adv.get("complimentary_override"),
    }
    return out


def band_for(n: float, c: Json | None = None) -> Json:
    for b in _c(c)["bands"]:
        if n >= b["min_employees"]:
            band: Json = b
            return band
    raise ValueError(n)


def integration_calls(inp: Json, c: Json | None = None) -> float:
    """Yearly integration calls of a sanitized input."""
    integ = inp["integrations"]
    if integ["mode"] == "measured":
        return float(integ["calls_per_year"])
    return float(sum(cnt * pattern_calls(p, inp["employees"]) for p, cnt in integ["counts"].items()))


def price_band(p: float, c: Json | None = None) -> str:
    for b in _c(c)["price_bands"]:
        if b["max"] is None or p <= b["max"]:
            band_id: str = b["id"]
            return band_id
    raise ValueError(p)


# ---------------------------------------------------------------- annual model


def compute(raw: Json, c: Json | None = None, clamp: bool = True) -> Json:
    """One year at steady state (references/model.md, Annual formulas)."""
    c = _c(c)
    inp = sanitize(raw, c, clamp)
    adv = inp["advanced"]
    n = inp["employees"]
    p = inp["price_per_credit"]
    band = band_for(n, c)
    skus = list(inp["skus"])
    extend_implied = False
    if "extend" not in skus and any(
        c["agent_paths"][ag["path"]].get("requires_sku") == "extend" and ag["tasks_per_month"] > 0
        for ag in inp["agents"]
    ):
        skus.append("extend")
        extend_implied = True
    uplift = sum(c["sku_uplifts"][s]["uplift"] for s in skus)
    allowance = adv["allowance_override"]
    if allowance is None:
        allowance = band["allowance_calls"] * (1 + uplift)
    comp = adv["complimentary_override"]
    if comp is None:
        comp = band["complimentary_credits"]
    pool = comp + adv["purchased_credits"]

    a_int = integration_calls(inp, c)
    ssa = n * inp["ssa_actions_per_employee_month"] * 12 * c["ssa_credits_per_action"]
    skills = sum(
        s["volume_per_year"] * c["workday_skills"][s["skill"]]["credits_per_unit"] for s in inp["skills"]
    )

    agent_api_calls = tool_credits = inv_credits = token_usd = agent_calls_total = 0.0
    per_agent = []
    for ag in inp["agents"]:
        q = ag["tasks_per_month"] * 12
        x = q * ag["calls_per_task"]
        pd = c["agent_paths"][ag["path"]]
        a_share = ag["advanced_share"]
        tc = ic = tok = api = 0.0
        if ag["path"] == "api":
            api = x
        else:
            tc = x * ((1 - a_share) * pd["base_per_100"] + a_share * pd["advanced_per_100"]) / 100
            if ag["path"] == "extend_custom":
                ic = q * pd["invocation_credits"][ag["model_tier"]]
            if adv["tool_calls_also_metered_as_api"]:
                api = x
        if ag["path"] != "extend_custom":
            tok = (
                x * c["read_formats"][ag["read_format"]]["tokens_per_call"] * adv["context_rereads"]
                * adv["llm_price_per_m_tokens"] / 1e6
            )
        agent_api_calls += api
        tool_credits += tc
        inv_credits += ic
        token_usd += tok
        agent_calls_total += x
        per_agent.append({
            "path": ag["path"], "tasks_per_year": q, "workday_calls_per_year": x,
            "api_meter_calls": api, "tool_credits": tc, "invocation_credits": ic,
            "token_cost_usd": tok,
        })

    total_calls = a_int + agent_api_calls
    over = max(0.0, total_calls - allowance)
    api_credits = over * c["api_credits_per_call"] if adv["policy_signed"] else 0.0
    credits = {
        "api_overage": api_credits, "workday_agents_ssa": ssa, "workday_agents_skills": skills,
        "agent_tool_calls": tool_credits, "agent_invocations": inv_credits,
    }
    need = sum(credits.values())
    credits["total"] = need
    shortfall = max(0.0, need - pool)
    driver = max(STREAM_LABELS, key=lambda k: credits[k]) if need > 0 else None
    if shortfall > 0:
        state = "to_buy"
    elif need > 0:
        state = "covered"
    elif agent_api_calls > 0:
        state = "inside_allowance_agent"
    else:
        state = "zero"
    return {
        "band_label": band["label"],
        "extend_implied": extend_implied,
        "skus_applied": skus,
        "allowance_calls": allowance,
        "complimentary_credits": comp,
        "pool_credits": pool,
        "integration_calls": a_int,
        "agent_api_calls": agent_api_calls,
        "total_api_calls": total_calls,
        "allowance_left_calls": max(0.0, allowance - total_calls),
        "allowance_used_ratio": (total_calls / allowance) if allowance > 0 else None,
        "over_allowance_calls": over,
        "credits": credits,
        "shortfall_credits": shortfall,
        "shortfall_usd": shortfall * p,
        "usage_value_usd": need * p,
        "pool_months_of_cover": pool * 12 / need if need > 0 else None,
        "agent_workday_calls": agent_calls_total,
        "token_cost_usd": token_usd,
        "largest_driver": driver,
        "headline_state": state,
        "price_band": price_band(p, c),
        "agents": per_agent,
    }


# ---------------------------------------------------------------- monthly forecast


def _ym(s: str) -> int:
    y, m = map(int, s.split("-"))
    return y * 12 + m - 1


def _ym_str(i: int) -> str:
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def next_month(today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    return _ym_str(today.year * 12 + today.month)


def forecast_settings(raw: Json, c: Json | None = None, today: dt.date | None = None) -> Json:
    """The forecast block with its defaults filled in."""
    fd = _c(c)["forecast_defaults"]
    f = dict(raw.get("forecast") or {})
    f["start"] = f.get("start") or next_month(today)
    f["months"] = int(f.get("months") or fd["months"])
    f["growth"] = dict(f.get("growth") or {})
    if f.get("complimentary_reset") is None:
        f["complimentary_reset"] = fd["complimentary_reset"]
    if f.get("allowance_counts_during_grace") is None:
        f["allowance_counts_during_grace"] = fd["allowance_counts_during_grace"]
    bought: Any = (raw.get("advanced") or {}).get("purchased_credits")
    if not f.get("purchased_packages") and _is_number(bought) and bought > 0:
        # A bare purchased total becomes one package covering the first forecast year.
        first = _ym(f["start"])
        f["purchased_packages"] = [{"credits": bought, "from": f["start"], "to": _ym_str(first + 11)}]
    return f


def _scaled(raw: Json, gi: float, ga: float, gw: float, mult: float, c: Json) -> Json:
    y = sanitize(raw, c)
    y["integrations"] = {"mode": "measured", "calls_per_year": integration_calls(y, c) * gi * mult, "counts": None}
    for ag in y["agents"]:
        ag["tasks_per_month"] = ag["tasks_per_month"] * ga * mult
    y["ssa_actions_per_employee_month"] = y["ssa_actions_per_employee_month"] * gw * mult
    for s in y["skills"]:
        s["volume_per_year"] = s["volume_per_year"] * gw * mult
    return y


def _monthly(raw: Json, f: Json, c: Json, mult: float = 1.0) -> Json:
    inp = sanitize(raw, c)
    start = _ym(f["start"])
    months = f["months"]
    g = f["growth"]
    bill = _ym(c["api_billable_from"])
    counts_grace = f["allowance_counts_during_grace"]
    reset = f["complimentary_reset"]
    ays = _ym(f["allowance_year_start"]) if f.get("allowance_year_start") else start
    renewal = _ym(f["complimentary_assumed_after"]) if f.get("complimentary_assumed_after") else None

    cache: dict[int, Json] = {}

    def year_result(yi: int) -> Json:
        if yi not in cache:
            y = _scaled(
                raw, (1 + g.get("integrations", 0)) ** yi, (1 + g.get("agents", 0)) ** yi,
                (1 + g.get("workday_agents", 0)) ** yi, mult, c,
            )
            y["advanced"]["purchased_credits"] = 0
            cache[yi] = compute(y, c, clamp=False)
        return cache[yi]

    c0 = year_result(0)["complimentary_credits"]
    opening = f.get("opening_complimentary")
    if opening is None:
        opening = c0 * (12 - start % 12) / 12 if reset == "jan1" else c0
    comp_bal = float(opening)
    packages: list[Json] = [
        {"credits": float(pk["credits"]), "from": _ym(pk["from"]), "to": _ym(pk["to"]), "bal": None}
        for pk in (f.get("purchased_packages") or [])
    ]
    cum = float(f.get("allowance_used_at_start") or 0)
    signed = inp["advanced"]["policy_signed"]
    streams = dict.fromkeys(STREAM_LABELS, 0.0)
    rows = []
    for m in range(months):
        cm = start + m
        r = year_result(m // 12)
        if cm != ays and (cm - ays) % 12 == 0:
            cum = 0.0
        calls = r["total_api_calls"] / 12
        e = r["allowance_calls"]
        api_cr = 0.0
        if counts_grace or cm >= bill:
            prev = cum
            cum += calls
            over = max(0.0, cum - e) - max(0.0, prev - e)
            if cm >= bill and signed:
                api_cr = over * c["api_credits_per_call"]
        nonapi = (r["credits"]["total"] - r["credits"]["api_overage"]) / 12
        streams["api_overage"] += api_cr
        for k in STREAM_LABELS:
            if k != "api_overage":
                streams[k] += r["credits"][k] / 12
        need = api_cr + nonapi
        reset_now = False
        if m > 0 and ((reset == "jan1" and cm % 12 == 0) or (reset == "start_anniversary" and m % 12 == 0)):
            comp_bal = float(c0)
            reset_now = True
        comp_exp = (cm // 12) * 12 + 11 if reset == "jan1" else start + (m // 12) * 12 + 11
        buckets: list[tuple[int, int, str, int]] = [(comp_exp, 0, "comp", -1)]
        for i, pk in enumerate(packages):
            if pk["from"] <= cm <= pk["to"]:
                if pk["bal"] is None:
                    pk["bal"] = pk["credits"]
                buckets.append((pk["to"], 1, "pkg", i))
        buckets.sort(key=lambda b: (b[0], b[1]))
        rem = need
        drawn_comp = drawn_pkg = 0.0
        for _, _, kind, i in buckets:
            if rem <= 0:
                break
            if kind == "comp":
                take = min(rem, comp_bal)
                comp_bal -= take
                drawn_comp += take
            else:
                take = min(rem, packages[i]["bal"])
                packages[i]["bal"] -= take
                drawn_pkg += take
            rem -= take
        pkg_bal = sum(pk["bal"] or 0.0 for pk in packages if pk["from"] <= cm <= pk["to"])
        # Purchased credits don't roll over: what's left in a package after its last month is lost.
        expired = sum(pk["bal"] or 0.0 for pk in packages if pk["to"] == cm)
        rows.append({
            "month": _ym_str(cm),
            "api_calls": calls,
            "api_credits": api_cr,
            "other_credits": nonapi,
            "credits_needed": need,
            "from_complimentary": drawn_comp,
            "from_purchased": drawn_pkg,
            "to_buy": rem,
            "complimentary_left": comp_bal,
            "purchased_left": pkg_bal,
            "token_cost_usd": r["token_cost_usd"] / 12,
            "expired_purchased": expired,
            "flags": [fl for fl, on in (
                ("grace", cm < bill),
                ("complimentary_reset", reset_now),
                ("complimentary_assumed", renewal is not None and cm >= renewal),
                ("allowance_year_start", cm == ays or (cm - ays) % 12 == 0),
            ) if on],
        })
    price = inp["price_per_credit"]
    years = []
    for yi in range(0, months, 12):
        blk = rows[yi:yi + 12]
        need_y = sum(x["credits_needed"] for x in blk)
        buy = sum(x["to_buy"] for x in blk)
        years.append({
            "year": yi // 12 + 1, "from": blk[0]["month"], "to": blk[-1]["month"],
            "api_credits": sum(x["api_credits"] for x in blk), "credits_needed": need_y,
            "to_buy": buy, "to_buy_usd": buy * price,
            "token_cost_usd": sum(x["token_cost_usd"] for x in blk),
        })
    totals = {
        "credits_needed": sum(y["credits_needed"] for y in years),
        "to_buy": sum(y["to_buy"] for y in years),
        "to_buy_usd": sum(y["to_buy_usd"] for y in years),
        "token_cost_usd": sum(y["token_cost_usd"] for y in years),
    }
    return {
        "months": rows, "years": years, "totals": totals,
        "free_credits_run_out": next((x["month"] for x in rows if x["to_buy"] > EPS), None),
        "extend_implied": year_result(0)["extend_implied"],
        "streams": streams,
        "first_year": year_result(0),
        "opening_complimentary": float(opening),
        "expiring_unused": [
            {"month": x["month"], "credits": x["expired_purchased"], "usd": x["expired_purchased"] * price}
            for x in rows if x["expired_purchased"] > EPS
        ],
    }


def _forecast_one(raw: Json, c: Json, with_range: bool, today: dt.date | None) -> Json:
    f = forecast_settings(raw, c, today)
    out = _monthly(raw, f, c)
    out["settings"] = f
    if with_range:
        mults = c["forecast_defaults"]["range_multipliers"]
        lo = _monthly(raw, f, c, mults["low"])["totals"]
        hi = _monthly(raw, f, c, mults["high"])["totals"]
        out["range"] = {
            "low": {"credits_needed": lo["credits_needed"], "to_buy": lo["to_buy"]},
            "high": {"credits_needed": hi["credits_needed"], "to_buy": hi["to_buy"]},
        }
    return out


def resolve_unsure(raw: Json, path: str) -> Json:
    """A copy of raw with every "unsure" agent path set to path."""
    out = copy.deepcopy(raw)
    for ag in out.get("agents") or []:
        if ag.get("path") == UNSURE:
            ag["path"] = path
    return out


def has_unsure(raw: Json) -> bool:
    return any(ag.get("path") == UNSURE for ag in raw.get("agents") or [])


def run_forecast(raw: Json, c: Json | None = None, with_range: bool = True, today: dt.date | None = None) -> Json:
    """Monthly forecast with range. An "unsure" agent path runs as both api and tools_external;
    the higher result leads and both are kept under path_variants."""
    c = _c(c)
    if not has_unsure(raw):
        out = _forecast_one(raw, c, with_range, today)
        out["resolved_input"] = copy.deepcopy(raw)
        return out
    variants = {p: _forecast_one(resolve_unsure(raw, p), c, with_range, today) for p in ("api", "tools_external")}
    lead = max(variants, key=lambda p: (variants[p]["totals"]["to_buy"], variants[p]["totals"]["credits_needed"]))
    out = variants[lead]
    out["resolved_input"] = resolve_unsure(raw, lead)
    out["headline_path"] = lead
    out["path_variants"] = {
        p: {"totals": v["totals"], "range": v.get("range"), "free_credits_run_out": v["free_credits_run_out"],
            "extend_implied": v["extend_implied"], "allowance_calls": v["first_year"]["allowance_calls"]}
        for p, v in variants.items()
    }
    return out


def confidence(sources: Json, driver: str | None = None) -> str:
    """high: allowance, complimentary credits and API calls all come from the Console or a
    contract. medium: at least one of them does. low: none does, or the source behind the
    biggest credit stream is a default. Answers picked from a list never raise it alone."""

    def source(key: str) -> str:
        value = sources.get(key)
        if value is None and key == "complimentary":
            value = sources.get("pool")
        return str(value or "default")

    if driver is not None and source(STREAM_SOURCES[driver]) == "default":
        return "low"
    firm = [source(k) in FIRM_SOURCES for k in CONFIDENCE_KEYS]
    if all(firm):
        return "high"
    return "medium" if any(firm) else "low"


# ---------------------------------------------------------------- validation


def _check_number(
    errors: list[str], where: str, v: object, maximum: float | None = None, minimum: float = 0.0
) -> None:
    if v is None:
        return
    if not _is_number(v):
        errors.append(f"{where}: expected a number, got {v!r}")
        return
    value = float(v)  # type: ignore[arg-type]
    if value < 0 and minimum == 0:
        errors.append(f"{where}: can't be negative ({v})")
    elif value < minimum:
        errors.append(f"{where}: can't be less than {minimum:g} ({v})")
    elif maximum is not None and value > maximum:
        errors.append(f"{where}: can't be more than {maximum:g} ({v})")


def _check_month(errors: list[str], where: str, v: object) -> None:
    if v is None:
        return
    ok = isinstance(v, str) and len(v) == 7 and v[4] == "-" and v[:4].isdigit() and v[5:].isdigit()
    if not ok or not 1 <= int(str(v)[5:]) <= 12 or not 2000 <= int(str(v)[:4]) <= 2100:
        errors.append(f"{where}: expected a month as YYYY-MM between 2000 and 2100, got {v!r}")


def _check_enum(errors: list[str], where: str, v: object, allowed: list[str]) -> None:
    if v is not None and v not in allowed:
        errors.append(f"{where}: unknown value {v!r} (use {', '.join(allowed)})")


def _as_dict(errors: list[str], where: str, v: object) -> Json:
    if v is None:
        return {}
    if not isinstance(v, dict):
        errors.append(f"{where}: expected an object, got {type(v).__name__}")
        return {}
    return v


def _as_list(errors: list[str], where: str, v: object) -> list[Any]:
    if v is None:
        return []
    if not isinstance(v, list):
        errors.append(f"{where}: expected a list, got {type(v).__name__}")
        return []
    return v


def validate(raw: object, c: Json | None = None) -> list[str]:
    """Hard errors in an input, one line each. An empty list means the input is usable."""
    c = _c(c)
    if not isinstance(raw, dict):
        return ["input: expected a JSON object"]
    e: list[str] = []
    ranges = c["ranges"]
    big = 1e12
    if raw.get("organization") is not None and not isinstance(raw.get("organization"), str):
        e.append("organization: expected text")
    _check_number(e, "employees", raw.get("employees"), big, ranges["employees"][0])
    _check_number(e, "price_per_credit", raw.get("price_per_credit"), big, ranges["price_per_credit"][0])
    _check_number(e, "ssa_actions_per_employee_month", raw.get("ssa_actions_per_employee_month"), big)
    for i, sku in enumerate(_as_list(e, "skus", raw.get("skus"))):
        _check_enum(e, f"skus[{i}]", sku, list(c["sku_uplifts"]))
    integ = _as_dict(e, "integrations", raw.get("integrations"))
    _check_enum(e, "integrations.mode", integ.get("mode"), ["estimate", "measured", "inventory"])
    _check_number(e, "integrations.calls_per_year", integ.get("calls_per_year"), big)
    for p, n in _as_dict(e, "integrations.counts", integ.get("counts")).items():
        _check_enum(e, "integrations.counts", p, list(c["integration_patterns"]))
        _check_number(e, f"integrations.counts.{p}", n, big)
    items = _as_list(e, "integrations.items", integ.get("items"))
    for i, item in enumerate(items):
        where = f"integrations.items[{i}]"
        if not isinstance(item, dict):
            e.append(f"{where}: expected an object")
            continue
        if item.get("name") is not None and not isinstance(item.get("name"), str):
            e.append(f"{where}.name: expected text")
        _check_enum(e, f"{where}.pattern", item.get("pattern"), list(c["integration_patterns"]))
        before = len(e)
        for k in ("calls_per_year", "records", "runs_per_year", "records_per_run", "writes_per_year"):
            _check_number(e, f"{where}.{k}", item.get(k), big)
        _check_number(e, f"{where}.page_size", item.get("page_size"), big, 1)
        if not any(item.get(k) is not None for k in ("calls_per_year", "pattern", "runs_per_year")):
            e.append(f"{where}: give calls_per_year, a pattern, or runs_per_year with records_per_run")
        elif item.get("calls_per_year") is None and item.get("pattern") is None and item.get("records_per_run") is None:
            e.append(f"{where}.records_per_run: required with runs_per_year")
        if len(e) == before:
            try:
                calls = inventory_item_calls(item, 0.0)
            except (OverflowError, ValueError, ZeroDivisionError):
                calls = math.inf
            if not math.isfinite(calls):
                e.append(f"{where}: these values give more calls than the model can count")
    if integ.get("mode") == "inventory" and not items:
        e.append("integrations.items: inventory mode needs at least one item")
    for i, s in enumerate(_as_list(e, "skills", raw.get("skills"))):
        if not isinstance(s, dict):
            e.append(f"skills[{i}]: expected an object")
            continue
        _check_enum(e, f"skills[{i}].skill", s.get("skill"), list(c["workday_skills"]))
        _check_number(e, f"skills[{i}].volume_per_year", s.get("volume_per_year"), big)
    for i, ag in enumerate(_as_list(e, "agents", raw.get("agents"))):
        where = f"agents[{i}]"
        if not isinstance(ag, dict):
            e.append(f"{where}: expected an object")
            continue
        _check_number(e, f"{where}.tasks_per_month", ag.get("tasks_per_month"), big)
        _check_number(e, f"{where}.calls_per_task", ag.get("calls_per_task"), big, ranges["calls_per_task"][0])
        _check_number(e, f"{where}.advanced_share", ag.get("advanced_share"), maximum=1)
        _check_enum(e, f"{where}.path", ag.get("path"), [*c["agent_paths"], UNSURE])
        _check_enum(e, f"{where}.read_format", ag.get("read_format"), list(c["read_formats"]))
        _check_enum(e, f"{where}.model_tier", ag.get("model_tier"), ["base", "standard", "premium"])
    adv = _as_dict(e, "advanced", raw.get("advanced"))
    for key in ("purchased_credits", "llm_price_per_m_tokens", "context_rereads",
                "allowance_override", "complimentary_override"):
        _check_number(e, f"advanced.{key}", adv.get(key), big)
    for key in ("policy_signed", "tool_calls_also_metered_as_api"):
        if adv.get(key) is not None and not isinstance(adv.get(key), bool):
            e.append(f"advanced.{key}: expected true or false, got {adv.get(key)!r}")
    f = _as_dict(e, "forecast", raw.get("forecast"))
    for key in ("start", "allowance_year_start", "complimentary_assumed_after"):
        _check_month(e, f"forecast.{key}", f.get(key))
    months = f.get("months")
    if months is not None and (not isinstance(months, int) or isinstance(months, bool) or not 1 <= months <= 60):
        e.append(f"forecast.months: expected a whole number from 1 to 60, got {months!r}")
    for key in ("opening_complimentary", "allowance_used_at_start"):
        _check_number(e, f"forecast.{key}", f.get(key), big)
    _check_enum(e, "forecast.complimentary_reset", f.get("complimentary_reset"), ["jan1", "start_anniversary"])
    if f.get("allowance_counts_during_grace") is not None and not isinstance(f.get("allowance_counts_during_grace"), bool):
        e.append("forecast.allowance_counts_during_grace: expected true or false")
    for key, v in _as_dict(e, "forecast.growth", f.get("growth")).items():
        _check_enum(e, "forecast.growth", key, ["integrations", "agents", "workday_agents"])
        if not _is_number(v) or not -1 < v <= 10:
            e.append(f"forecast.growth.{key}: expected a yearly rate above -1 and at most 10 (0.2 is 20%), got {v!r}")
    for i, pk in enumerate(_as_list(e, "forecast.purchased_packages", f.get("purchased_packages"))):
        where = f"forecast.purchased_packages[{i}]"
        if not isinstance(pk, dict):
            e.append(f"{where}: expected an object")
            continue
        if pk.get("credits") is None:
            e.append(f"{where}.credits: required")
        _check_number(e, f"{where}.credits", pk.get("credits"), big)
        for k in ("from", "to"):
            if pk.get(k) is None:
                e.append(f"{where}.{k}: required")
            _check_month(e, f"{where}.{k}", pk.get(k))
        if isinstance(pk.get("from"), str) and isinstance(pk.get("to"), str) and pk["from"] > pk["to"]:
            e.append(f"{where}: 'from' is after 'to'")
    if raw.get("customer_sizing") is not None and not isinstance(raw.get("customer_sizing"), bool):
        e.append("customer_sizing: expected true or false")
    for i, note in enumerate(_as_list(e, "contract_notes", raw.get("contract_notes"))):
        if not isinstance(note, str):
            e.append(f"contract_notes[{i}]: expected text")
    for key, v in _as_dict(e, "sources", raw.get("sources")).items():
        _check_enum(e, f"sources.{key}", v, list(SOURCE_VALUES))
    return e


# ---------------------------------------------------------------- formatting


def round_half_up(x: float, places: int = 0) -> float:
    """Round halves away from zero ($137,932.5 -> $137,933), unlike round()'s half-to-even."""
    return float(Decimal(repr(x)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def fmt_credits(x: float) -> str:
    return f"{int(round_half_up(x)):,}"


def fmt_number(x: float) -> str:
    return f"{int(x):,}" if float(x).is_integer() else f"{x:,.4g}"


def fmt_usd(x: float) -> str:
    """Cents under $10, whole dollars otherwise."""
    return f"${round_half_up(x, 2):,.2f}" if abs(x) < 10 else f"${int(round_half_up(x)):,}"


def fmt_price(p: float) -> str:
    """$0.10, $0.075, $0.005: at least two decimals, more when the price needs them."""
    text = f"{p:,.4f}".rstrip("0")
    whole, _, frac = text.partition(".")
    return f"${whole}.{frac.ljust(2, '0')}"


def month_name(ym: str) -> str:
    return dt.date(int(ym[:4]), int(ym[5:]), 1).strftime("%B %Y")


def short_month(ym: str) -> str:
    return dt.date(int(ym[:4]), int(ym[5:]), 1).strftime("%b %Y")


def md_escape(text: object) -> str:
    """Make untrusted text (organization, integration names, contract wording) inert in
    Markdown: one line, and no headings, links, images, emphasis or HTML."""
    flat = " ".join(str(text).split())
    return "".join("\\" + ch if ch in "\\`*_[]()!<>#|~" else ch for ch in flat)


# ---------------------------------------------------------------- result assembly


def effective_sources(raw: Json) -> Json:
    """Every source key. An explicit value is kept as given; a missing one is "user" when the
    input clearly carries the user's own figure, otherwise "default"."""
    given = raw.get("sources") or {}
    src: Json = {k: given.get(k) for k in SOURCE_KEYS}
    for k in ("complimentary", "purchased"):
        if src[k] is None and given.get("pool") is not None:
            src[k] = given["pool"]
    src.update({k: v for k, v in given.items() if k not in src and k != "pool"})
    adv = raw.get("advanced") or {}
    f = raw.get("forecast") or {}
    c = _c(None)
    inferred = {
        "allowance": adv.get("allowance_override") is not None,
        "complimentary": adv.get("complimentary_override") is not None,
        "purchased": bool(f.get("purchased_packages")) or (_is_number(adv.get("purchased_credits"))
                                                             and adv["purchased_credits"] > 0),
        "api_calls": (raw.get("integrations") or {}).get("mode") in ("measured", "inventory"),
        "price_per_credit": _is_number(raw.get("price_per_credit"))
        and raw["price_per_credit"] != c["default_price_per_credit"],
        "model_price": _is_number(adv.get("llm_price_per_m_tokens"))
        and adv["llm_price_per_m_tokens"] != c["defaults"]["llm_price_per_m_tokens"],
        "forecast_start": bool(f.get("start")),
    }
    for k in SOURCE_KEYS:
        if src[k] is None:
            src[k] = "user" if inferred.get(k) else "default"
    return src


def _adjustments(raw: Json, c: Json) -> list[str]:
    """Values the model's ranges changed, in words, so the user sees every silent clamp."""
    out: list[str] = []
    ranges = c["ranges"]

    def check(label: str, v: object, key: str) -> None:
        if not _is_number(v):
            return
        lo, hi, _ = ranges[key]
        value = float(v)  # type: ignore[arg-type]
        if value > hi:
            out.append(f"{label}: {fmt_number(value)} is above the model's {fmt_number(hi)} cap; used {fmt_number(hi)}")
        elif value < lo:
            out.append(f"{label}: {fmt_number(value)} is below the model's minimum of {fmt_number(lo)}; used {fmt_number(lo)}")

    check("Employees", raw.get("employees"), "employees")
    check("Price per credit", raw.get("price_per_credit"), "price_per_credit")
    check("Self-Service Agent actions per employee a month", raw.get("ssa_actions_per_employee_month"),
          "ssa_actions_per_employee_month")
    integ = raw.get("integrations") or {}
    if integ.get("mode") == "measured":
        check("Integration calls a year", integ.get("calls_per_year"), "integration_calls_per_year")
    elif integ.get("mode") == "inventory":
        employees = sanitize(raw, c)["employees"]
        check("Integration calls a year (inventory total)", inventory_calls(integ.get("items") or [], employees),
              "integration_calls_per_year")
    else:
        for p, n in (integ.get("counts") or {}).items():
            check(f"{p.capitalize()} integrations", n, "integration_count")
    for s in raw.get("skills") or []:
        if s.get("skill") in c["workday_skills"]:
            check(f"{c['workday_skills'][s['skill']]['label']} volume a year", s.get("volume_per_year"),
                  "skill_volume_per_year")
    for i, ag in enumerate(raw.get("agents") or [], 1):
        check(f"Agent {i} tasks a month", ag.get("tasks_per_month"), "tasks_per_month")
        check(f"Agent {i} Workday calls per task", ag.get("calls_per_task"), "calls_per_task")
    adv = raw.get("advanced") or {}
    check("Purchased credits", adv.get("purchased_credits"), "purchased_credits")
    check("Model price per million tokens", adv.get("llm_price_per_m_tokens"), "llm_price_per_m_tokens")
    check("Context re-reads", adv.get("context_rereads"), "context_rereads")
    return out


def _assumed(res: Json, src: Json, raw: Json, c: Json) -> list[str]:
    s = res["sanitized"]
    fy = res["first_year"]
    f = res["settings"]
    out = list(res["adjusted"])
    if src["price_per_credit"] == "default":
        out.append(f"Price per credit: {fmt_price(s['price_per_credit'])}, the top of analysts' "
                   f"{fmt_price(c['price_range_note']['low'])} to {fmt_price(c['price_range_note']['high'])} range")
    if src["allowance"] == "default" and s["advanced"]["allowance_override"] is None:
        band = band_for(s["employees"], c)
        skus = fy["skus_applied"]
        if skus:
            mult = 1 + sum(c["sku_uplifts"][k]["uplift"] for k in skus)
            names = ", ".join(c["sku_uplifts"][k]["label"] for k in skus)
            line = (f"API allowance: {fmt_credits(band['allowance_calls'])} for the {band['label']} employee band "
                    f"x {mult:g} for {names} = {fmt_credits(fy['allowance_calls'])} calls a year (analysts' reading)")
            if fy["extend_implied"]:
                line += ", with Extend assumed because Agent-Ready Tools and custom agents need Extend Professional"
        else:
            line = (f"API allowance: {fmt_credits(fy['allowance_calls'])} calls a year for the {band['label']} "
                    "employee band (analysts' reading)")
        out.append(line)
    if (raw.get("forecast") or {}).get("opening_complimentary") is None:
        c0 = fy["complimentary_credits"]
        if f["complimentary_reset"] == "jan1":
            left = 12 - _ym(f["start"]) % 12
            out.append(f"Free credits left at the start: {fmt_credits(res['opening_complimentary'])} ({left}/12 of "
                       f"the yearly {fmt_credits(c0)}, assumed); check Credit Balance in the Console")
        else:
            out.append(f"Free credits left at the start: the full yearly {fmt_credits(c0)} (assumed); check Credit "
                       "Balance in the Console")
    if src["api_calls"] == "default":
        out.append(f"Integration calls: about {fmt_credits(fy['integration_calls'])} a year, estimated from typical sync patterns")
    if src["complimentary"] == "default" and s["advanced"]["complimentary_override"] is None:
        reset = "the 1 January reset" if f["complimentary_reset"] == "jan1" else "a reset each forecast year"
        out.append(f"Complimentary credits: {fmt_credits(fy['complimentary_credits'])} a year, with {reset}")
    if src["employees"] == "default":
        out.append(f"Employees: {fmt_credits(s['employees'])}")
    if src["agents"] == "default" and any(a["tasks_per_month"] > 0 for a in s["agents"]):
        out.append("Agent volume and Workday calls per task are estimates")
    if src["workday_agents"] == "default" and (s["ssa_actions_per_employee_month"] > 0 or s["skills"]):
        out.append("Workday agent volumes are estimates")
    if src["growth"] == "default" and f["months"] > 12:
        g = f["growth"]
        out.append(
            "Growth a year: integrations {:.0%}, agents {:.0%}, Workday agents {:.0%}".format(
                g.get("integrations", 0), g.get("agents", 0), g.get("workday_agents", 0)
            )
        )
    if src["policy_signed"] == "default":
        out.append("You've signed the Flex Credits and Platform Entitlement Policy")
    if src["forecast_start"] == "default":
        out.append(f"Forecast starts {month_name(f['start'])}, which also starts the allowance year")
    return out


def _path_comparison(base: Json, c: Json, today: dt.date | None) -> list[Json]:
    """The first forecast year with only one agent's path changed, so the row for the path
    in use matches the By year table exactly."""
    rows = []
    for i, ag in enumerate(base.get("agents") or []):
        if not _is_number(ag.get("tasks_per_month")) or ag["tasks_per_month"] <= 0:
            continue
        for path in c["agent_paths"]:
            trial = copy.deepcopy(base)
            trial["agents"][i]["path"] = path
            run = _forecast_one(trial, c, False, today)
            y1 = run["years"][0]
            rows.append({
                "agent": i + 1, "path": path, "current": path == ag.get("path"),
                "from": y1["from"], "to": y1["to"], "credits_needed": y1["credits_needed"],
                "to_buy": y1["to_buy"], "token_cost_usd": y1["token_cost_usd"],
                "extend_implied": run["extend_implied"], "included": _fill(PATH_INCLUDED[path], c),
            })
    return rows


def _levers(raw: Json, base_totals: Json, c: Json, today: dt.date | None) -> list[Json]:
    trials: list[tuple[str, Json]] = []
    integ = raw.get("integrations") or {}
    mode = integ.get("mode")
    if mode == "inventory":
        items = integ.get("items") or []
        if any(it.get("pattern") in ("typical", "heavy") for it in items):
            t = copy.deepcopy(raw)
            for it in t["integrations"]["items"]:
                if it.get("pattern") in ("typical", "heavy"):
                    it["pattern"] = "efficient"
            trials.append(("Switch the integrations listed as typical or heavy to changes-only syncs", t))
    elif mode != "measured":
        counts = integ.get("counts") or {}
        moved = sum(float(counts.get(p) or 0) for p in ("typical", "heavy"))
        if moved > 0:
            t = copy.deepcopy(raw)
            t["integrations"] = {
                "mode": "estimate",
                "counts": {"efficient": float(counts.get("efficient") or 0) + moved, "typical": 0, "heavy": 0},
            }
            trials.append(("Switch hourly and full-compare integrations to changes-only syncs", t))
    reads = [a for a in raw.get("agents") or []
             if a.get("path") != "extend_custom" and a.get("read_format") not in ("lean", "lean_json")
             and _is_number(a.get("tasks_per_month")) and a["tasks_per_month"] > 0]
    if reads:
        t = copy.deepcopy(raw)
        for a in t["agents"]:
            if a.get("path") != "extend_custom":
                a["read_format"] = "lean"
        trials.append(("Have agents read reports or lean JSON instead of full records (model tokens only)", t))
    calls = integration_calls(sanitize(raw, c), c)
    if calls > 0:
        t = copy.deepcopy(raw)
        t["integrations"] = {"mode": "measured", "calls_per_year": calls * 0.9}
        trials.append(("Cap retries and duplicate pulls (illustrative: 10% fewer integration calls)", t))
    out = []
    for label, t in trials:
        tot = _forecast_one(t, c, False, today)["totals"]
        saved = base_totals["credits_needed"] - tot["credits_needed"]
        tok = base_totals["token_cost_usd"] - tot["token_cost_usd"]
        if saved > EPS or tok > EPS:
            out.append({
                "lever": label, "credits_saved": saved,
                "to_buy_saved": base_totals["to_buy"] - tot["to_buy"], "token_usd_saved": tok,
            })
    out.sort(key=lambda x: (-x["credits_saved"], -x["token_usd_saved"]))
    return out


def _open_questions(res: Json, src: Json, raw: Json) -> list[Json]:
    s = res["sanitized"]
    paths = {a.get("path") for a in raw.get("agents") or []
             if _is_number(a.get("tasks_per_month")) and a["tasks_per_month"] > 0}
    tools = bool(paths & {"tools_external", "extend_custom", UNSURE})
    q = [
        ("What is our price per Flex Credit, and are there volume tiers?", src["price_per_credit"] == "default"),
        ("What yearly API allowance applies to us, and which subscriptions raise it?",
         src["allowance"] not in FIRM_SOURCES),
        ("When does our API allowance reset, and is the first period prorated?", True),
        ("Do Agent-Ready Tool calls also count against our API allowance?", tools),
        ("What counts as a non-Custom agent on the rate card?", bool(paths & {"tools_external", UNSURE})),
        ("How is an invocation defined for custom agents in Workday Extend, and does one agent task "
         "equal one invocation?", "extend_custom" in paths),
        ("Do agent credits draw from complimentary credits before we sign the Flex Credits and "
         "Platform Entitlement Policy?", not s["advanced"]["policy_signed"]),
        ("Is a paginated read one call per page, and is a report (RaaS) run one call whatever the "
         "row count?", res["first_year"]["integration_calls"] > 0),
        ("Which Agent-Ready Tools count as base and which as advanced?", tools),
        ("Does Agent Gateway meter third-party agent interactions, and at what rate?",
         bool(paths & {"tools_external", "api", UNSURE})),
        ("Will complimentary credits continue at renewal, and at what level?",
         res["settings"]["months"] > 12 or bool(res["settings"].get("complimentary_assumed_after"))),
    ]
    # The report always asks the five questions every forecast depends on (indexes 2 to 6);
    # the rest only when they bear on this input.
    core = {2, 3, 4, 5, 6}
    items = [{"question": text, "applies": applies, "core": i in core, "untrusted": False}
             for i, (text, applies) in enumerate(q)]
    for note in res["contract_notes"]:
        quoted = " ".join(note.split())
        quoted = quoted if len(quoted) <= 200 else quoted[:197] + "..."
        items.append({"question": f'How does "{quoted}" in our order form apply to our Flex Credits?',
                      "applies": True, "core": False, "untrusted": True})
    return [x for x in items if x["applies"]] + [x for x in items if not x["applies"]]


def _headline(res: Json) -> str:
    t = res["totals"]
    f = res["settings"]
    rng = res.get("range") or {}
    price = res["sanitized"]["price_per_credit"]
    fy = res["first_year"]
    low = rng.get("low", {}).get("credits_needed", t["credits_needed"])
    high = rng.get("high", {}).get("credits_needed", t["credits_needed"])
    parts = [
        f"{fmt_credits(t['credits_needed'])} credits in the next {f['months']} months "
        f"(range {fmt_credits(low)} to {fmt_credits(high)}, confidence {res['confidence']})."
    ]
    if t["to_buy"] > EPS:
        parts.append(f"{fmt_credits(t['to_buy'])} to buy, about {fmt_usd(t['to_buy_usd'])} at {fmt_price(price)} a credit.")
    elif t["credits_needed"] > EPS:
        parts.append("Nothing to buy: your free and purchased credits cover it.")
    elif fy["agent_api_calls"] > 0:
        parts.append(
            f"Nothing to buy: your agents' {fmt_credits(fy['agent_api_calls'])} Workday calls a year fit in your API "
            f"allowance, with {fmt_credits(fy['allowance_left_calls'])} calls to spare in the first year."
        )
    else:
        parts.append("Nothing to buy: you're inside your API allowance.")
    if res["free_credits_run_out"]:
        lead = "You start buying more in" if f.get("purchased_packages") else "Free credits run out in"
        parts.append(f"{lead} {month_name(res['free_credits_run_out'])}.")
    for x in res["expiring_unused"]:
        parts.append(f"{fmt_credits(x['credits'])} purchased credits (about {fmt_usd(x['usd'])}) expire unused "
                     f"in {month_name(x['month'])}.")
    driver = res["driver"]
    parts.append(f"Biggest driver: {STREAM_LABELS[driver] if driver else 'none, nothing is metered'}.")
    return " ".join(parts)


def _first_year_line(res: Json) -> str:
    fy = res["first_year"]
    used = fy["allowance_used_ratio"]
    share = f" ({used:.0%} used)" if used is not None else ""
    return (f"First year: {fmt_credits(fy['integration_calls'])} integration calls and "
            f"{fmt_credits(fy['agent_api_calls'])} agent API calls against an allowance of "
            f"{fmt_credits(fy['allowance_calls'])} calls{share}.")


# A typical employee count for each band, used only for the customer sizing table.
BAND_REFERENCE_EMPLOYEES = {100000: 150000, 30000: 50000, 10000: 15000, 3500: 6000, 0: 2000}


def _customer_sizing(base: Json, c: Json) -> Json | None:
    """For vendors sizing an agent for their customers: credits per task on each path, and how
    many tasks a month fit in each employee band's API allowance after typical integrations.
    Computed here so the chat never has to do this arithmetic."""
    if not base.get("customer_sizing"):
        return None
    agents = [(i, a) for i, a in enumerate(base.get("agents") or [])
              if _is_number(a.get("tasks_per_month")) and a["tasks_per_month"] > 0]
    if not agents:
        return None
    integ = base.get("integrations") or {}
    counts = integ.get("counts") if integ.get("mode") in (None, "estimate") and integ.get("counts") else None
    counts = counts or {"efficient": 3, "typical": 2, "heavy": 0}
    counts_text = ", ".join(f"{fmt_number(float(n))} {p}" for p, n in counts.items() if n) or "none"
    out: Json = {"integrations_assumed": counts_text, "agents": []}
    for i, ag in agents:
        per_path = {}
        for path in c["agent_paths"]:
            trial = copy.deepcopy(base)
            trial["agents"] = [dict(ag, path=path)]
            row = compute(trial, c)["agents"][0]
            per_path[path] = (row["tool_credits"] + row["invocation_credits"]) / row["tasks_per_year"]
        calls = sanitize({"agents": [ag]}, c)["agents"][0]["calls_per_task"]
        bands = []
        for band in c["bands"]:
            n = BAND_REFERENCE_EMPLOYEES.get(band["min_employees"], band["min_employees"])
            used = float(sum(float(cnt or 0) * pattern_calls(p, n) for p, cnt in counts.items()))
            left = max(0.0, band["allowance_calls"] - used)
            bands.append({"band": band["label"], "employees": n, "allowance_calls": band["allowance_calls"],
                          "integration_calls": used, "tasks_per_month_that_fit": left / (12 * calls)})
        out["agents"].append({
            "agent": i + 1, "calls_per_task": calls,
            "credits_per_task": per_path,
            "api_credits_per_task_above_allowance": calls * c["api_credits_per_call"],
            "bands": sorted(bands, key=lambda b: b["employees"]),
        })
    return out


def _sizing_lines(sizing: Json | None) -> list[str]:
    if not sizing:
        return []
    lines = []
    for ag in sizing["agents"]:
        cpt = ag["credits_per_task"]
        lines.append(
            f"Per task, agent {ag['agent']} ({fmt_number(ag['calls_per_task'])} Workday calls): Workday APIs 0 credits "
            f"inside the allowance, {ag['api_credits_per_task_above_allowance']:.3g} above it; Workday's Agent-Ready "
            f"Tools {cpt['tools_external']:.3g}; custom agent in Workday Extend {cpt['extend_custom']:.3g}."
        )
        fits = "; ".join(f"{b['band']}: {fmt_credits(b['tasks_per_month_that_fit'])}" for b in ag["bands"])
        lines.append(
            f"Tasks a month that fit in the API allowance after typical integrations ({sizing['integrations_assumed']}), "
            f"by employee band, no subscription uplifts: {fits}."
        )
    return lines


def _chat_summary(res: Json) -> list[str]:
    """The summary forecast.py prints, ready to paste: every figure the chat needs, so nothing
    has to be recomputed. At most 10 lines, so with the Files line and the agent's refine
    offer the chat reply stays within 12."""
    lines = [res["headline"]]
    for extra in (res["low_price_note"], res["path_note"]):
        if extra:
            lines.append(extra)
    lines.append(_first_year_line(res))
    lines += _sizing_lines(res["customer_sizing"])[:4]
    asks = [q["question"] for q in res["open_questions"] if q["applies"]][:2]
    room = 10 - len(lines) - (1 if asks else 0) - 1
    if res["assumed"] and room > 0:
        lines.append("Assumed:")
        lines += [f"- {a}" for a in res["assumed"][:min(5, room)]]
    if asks:
        lines.append("To ask Workday: " + " ".join(f"({i}) {q}" for i, q in enumerate(asks, 1)))
    return lines


def _variant_note(res: Json) -> str | None:
    if "path_variants" not in res:
        return None
    lead = res["headline_path"]
    other = "api" if lead == "tools_external" else "tools_external"
    lv, ov = res["path_variants"][lead], res["path_variants"][other]

    def allowance(v: Json) -> str:
        uplift = "with the Extend uplift" if v["extend_implied"] else "no Extend uplift"
        return f"allowance {fmt_credits(v['allowance_calls'])}, {uplift}"

    return (
        f"The headline assumes {PATH_NAMES[lead]} for the agent you weren't sure about ({allowance(lv)}). "
        f"Through {PATH_NAMES[other]} instead ({allowance(ov)}): {fmt_credits(ov['totals']['credits_needed'])} "
        f"credits, {fmt_credits(ov['totals']['to_buy'])} to buy."
    )


def build_result(raw: Json, c: Json | None = None, today: dt.date | None = None) -> Json:
    """Everything result.json, report.md and forecast.xlsx need."""
    c = _c(c)
    res = run_forecast(raw, c, True, today)
    resolved = res.pop("resolved_input")
    res["sanitized"] = sanitize(resolved, c)
    src = effective_sources(raw)
    res["sources"] = src
    streams = res["streams"]
    res["driver"] = max(streams, key=lambda k: streams[k]) if res["totals"]["credits_needed"] > EPS else None
    res["confidence"] = confidence(src, res["driver"])
    res["organization"] = " ".join(str(raw.get("organization") or "").split()) or None
    res["contract_notes"] = [n for n in raw.get("contract_notes") or [] if isinstance(n, str) and n.strip()]
    res["version"] = c["version"]
    res["rate_card_date"] = c["rate_card_date"]
    res["price_is_default"] = src["price_per_credit"] == "default"
    res["adjusted"] = _adjustments(raw, c)
    res["headline"] = _headline(res)
    low_price = c["price_range_note"]["low"]
    res["low_price"] = low_price
    res["low_price_note"] = (
        f"At {fmt_price(low_price)} a credit, the low end of analysts' range: "
        f"{fmt_usd(res['totals']['to_buy'] * low_price)}."
        if res["price_is_default"] and res["totals"]["to_buy"] > EPS else None
    )
    res["path_note"] = _variant_note(res)
    res["assumed"] = _assumed(res, src, raw, c)
    res["agent_paths"] = _path_comparison(resolved, c, today)
    res["levers"] = _levers(resolved, res["totals"], c, today)
    res["customer_sizing"] = _customer_sizing(resolved, c)
    res["open_questions"] = _open_questions(res, src, raw)
    res["caveats"] = _caveats(res, c)
    res["forecast_assumptions"] = _forecast_assumptions(res, c)
    res["inputs"] = _input_rows(res, raw, c)
    res["inputs_echo"] = copy.deepcopy(raw)
    res["disclaimer"] = DISCLAIMER
    res["chat_summary"] = _chat_summary(res)
    return res


def _caveats(res: Json, c: Json) -> list[str]:
    out = [_fill(text, c) for text in CAVEATS]
    if not res["price_is_default"]:
        out[0] = (f"Workday doesn't publish a price per credit. This forecast uses {fmt_price(res['sanitized']['price_per_credit'])}, "
                  f"from your {res['sources']['price_per_credit']}; analysts estimate under $0.01 to $0.10.")
    return out


def _forecast_assumptions(res: Json, c: Json) -> list[str]:
    f = res["settings"]
    ays = f.get("allowance_year_start") or f["start"]
    out = [f"The API allowance year starts in {month_name(ays)} and resets every 12 months."]
    if _ym(f["start"]) < _ym(c["api_billable_from"]):
        out.append(
            _fill("Calls during the grace period (before {billable_month}) count toward the allowance.", c)
            if f["allowance_counts_during_grace"]
            else _fill("The allowance only counts calls from {billable_month}; grace-period calls are ignored.", c)
        )
    out.append(
        "Complimentary credits reset on 1 January, with the first grant prorated by month."
        if f["complimentary_reset"] == "jan1"
        else "Complimentary credits reset on each anniversary of the forecast start."
    )
    if f.get("complimentary_assumed_after"):
        out.append(
            f"Complimentary credits after renewal ({month_name(f['complimentary_assumed_after'])}) are "
            "assumed to continue at the same level."
        )
    elif f["months"] > 12:
        out.append("Complimentary credits are assumed to continue at the same level after renewal.")
    out.append("Usage is spread evenly across the months of each forecast year; growth steps up once a year.")
    out.append("Purchased packages are used soonest-expiring first and don't roll over: what's left after "
               "their last month expires unused.")
    return out


def _input_rows(res: Json, raw: Json, c: Json) -> list[list[str]]:
    s = res["sanitized"]
    fy = res["first_year"]
    src = res["sources"]
    f = res["settings"]
    integ = s["integrations"]
    raw_integ = raw.get("integrations") or {}
    rows: list[list[str]] = [
        ["Employees", fmt_credits(s["employees"]), src["employees"], f"Band: {fy['band_label']}"],
        ["Subscriptions that raise the allowance",
         ", ".join(c["sku_uplifts"][k]["label"] for k in fy["skus_applied"]) or "None",
         src["skus"], "Extend added because an agent uses Agent-Ready Tools or Extend" if fy["extend_implied"] else ""],
        ["Yearly API allowance (first year)", fmt_credits(fy["allowance_calls"]) + " calls", src["allowance"],
         "From the Console or contract" if s["advanced"]["allowance_override"] is not None else "Band x (1 + uplifts)"],
        ["Yearly complimentary credits", fmt_credits(fy["complimentary_credits"]), src["complimentary"], ""],
        ["Free credits left at the start", fmt_credits(res["opening_complimentary"]),
         "user" if (raw.get("forecast") or {}).get("opening_complimentary") is not None else "default", ""],
        ["Purchased credit packages",
         "; ".join(f"{fmt_credits(p['credits'])} ({p['from']} to {p['to']})" for p in f.get("purchased_packages") or [])
         or "None", src["purchased"], ""],
        ["Price per credit", fmt_price(s["price_per_credit"]), src["price_per_credit"],
         "Top of analysts' range" if res["price_is_default"] else ""],
        ["Policy signed", "Yes" if s["advanced"]["policy_signed"] else "No", src["policy_signed"],
         "" if s["advanced"]["policy_signed"] else "No API overage credits while unsigned"],
    ]
    if raw_integ.get("mode") == "inventory":
        note = f"{len(raw_integ.get('items') or [])} integrations listed one by one"
    elif integ["mode"] == "measured":
        note = "Measured total"
    else:
        note = ", ".join(f"{int(n)} {p}" for p, n in integ["counts"].items() if n)
    rows.append(["Integration calls a year (first year)", fmt_credits(fy["integration_calls"]), src["api_calls"], note])
    rows.append(["Self-Service Agent actions per employee a month", f"{s['ssa_actions_per_employee_month']:g}",
                 src["workday_agents"], ""])
    for sk in s["skills"]:
        meta = c["workday_skills"][sk["skill"]]
        rows.append([meta["label"], f"{fmt_credits(sk['volume_per_year'])} {meta['unit']}s a year",
                     src["workday_agents"], f"{meta['credits_per_unit']} credits per {meta['unit']}"])
    for i, ag in enumerate(s["agents"], 1):
        rows.append([
            f"Agent {i}",
            f"{fmt_credits(ag['tasks_per_month'])} tasks a month x {ag['calls_per_task']:g} Workday calls",
            src["agents"],
            f"{PATH_NAMES[ag['path']]}; reads {c['read_formats'][ag['read_format']]['label']}; "
            f"{ag['advanced_share']:.0%} of tool calls change data",
        ])
    rows.append(["Model price per million input tokens", fmt_usd(s["advanced"]["llm_price_per_m_tokens"]),
                 src["model_price"], ""])
    rows.append(["Forecast", f"{month_name(f['start'])}, {f['months']} months", src["forecast_start"], ""])
    if f["months"] > 12 or f["growth"]:
        g = f["growth"]
        rows.append(["Growth a year", "integrations {:.0%}, agents {:.0%}, Workday agents {:.0%}".format(
            g.get("integrations", 0), g.get("agents", 0), g.get("workday_agents", 0)), src["growth"], ""])
    for line in res["adjusted"]:
        rows.append(["Adjusted by the model", line, "model range", "Outside the range the model supports"])
    for note in res["contract_notes"]:
        rows.append(["Contract wording not modelled", " ".join(note.split()), "contract",
                     "Not in the numbers; listed in the questions for Workday"])
    return rows


# ---------------------------------------------------------------- workbook


def _credits(x: float, bold: bool = False) -> StyledCell:
    return StyledCell(round_half_up(x, 2), "credits", bold)


def _usd(x: float, bold: bool = False) -> StyledCell:
    """Cents under $10, whole dollars from $10, as in the report."""
    return StyledCell(round_half_up(x, 2), "usd" if abs(x) < 10 else "usd_whole", bold)


def _head(*labels: str) -> list[Cell]:
    return [StyledCell(label, "text", True) for label in labels]


def _month_notes(row: Json) -> str:
    words = [FLAG_WORDS[fl] for fl in row["flags"]]
    if row.get("expired_purchased", 0) > EPS:
        words.append(f"Package expires: {fmt_credits(row['expired_purchased'])} unused")
    return ", ".join(words)


def _run_out_label(res: Json) -> str:
    return "You start buying more in" if res["settings"].get("purchased_packages") else "Free credits run out in"


def build_sheets(res: Json) -> list[tuple[str, list[list[Cell]]]]:
    """The workbook's sheets as (name, rows)."""
    t = res["totals"]
    rng = res.get("range") or {}
    months = res["months"]
    price = res["sanitized"]["price_per_credit"]
    summary: list[list[Cell]] = [
        [StyledCell(f"Workday Flex Credits forecast: {res['organization'] or 'your organization'}", "text", True)],
        [res["headline"]],
        [],
        _head("Item", "Value"),
        ["Period", f"{short_month(months[0]['month'])} to {short_month(months[-1]['month'])}"],
        ["Credits needed", _credits(t["credits_needed"], True)],
        ["Credits needed, low", _credits(rng.get("low", {}).get("credits_needed", t["credits_needed"]))],
        ["Credits needed, high", _credits(rng.get("high", {}).get("credits_needed", t["credits_needed"]))],
        ["Credits to buy", _credits(t["to_buy"], True)],
        ["Credits to buy, low", _credits(rng.get("low", {}).get("to_buy", t["to_buy"]))],
        ["Credits to buy, high", _credits(rng.get("high", {}).get("to_buy", t["to_buy"]))],
        ["Cost of credits to buy", _usd(t["to_buy_usd"], True)],
        ["Price per credit", fmt_price(price)],
    ]
    if res["low_price_note"]:
        summary.append([f"Cost at {fmt_price(res['low_price'])} a credit", _usd(t["to_buy"] * res["low_price"])])
    run_out = res["free_credits_run_out"]
    summary.append([_run_out_label(res).replace(" in", ""), month_name(run_out) if run_out else "Not within the forecast"])
    for x in res["expiring_unused"]:
        summary.append([f"Purchased credits expiring unused in {month_name(x['month'])}", _credits(x["credits"])])
        summary.append([f"Value of those credits at {fmt_price(price)}", _usd(x["usd"])])
    summary += [
        ["Confidence", res["confidence"]],
        ["Biggest driver", STREAM_LABELS[res["driver"]] if res["driver"] else "None"],
        ["Extend added automatically for Agent-Ready Tools or Extend agents", "Yes" if res["extend_implied"] else "No"],
        ["Model tokens (separate bill, paid to your model provider)", _usd(t["token_cost_usd"])],
        ["Value of all credits used, including free ones", _usd(t["credits_needed"] * price)],
    ]
    if res["path_note"]:
        summary += [[], [res["path_note"]]]
    summary += [[], [res["disclaimer"]]]

    by_month: list[list[Cell]] = [_head(
        "Month", "API calls", "API credits", "Other credits", "Credits needed", "From complimentary",
        "From purchased", "To buy", "Complimentary left", "Purchased left", "Model tokens ($)", "Notes",
    )]
    for r in months:
        by_month.append([
            r["month"], _credits(r["api_calls"]), _credits(r["api_credits"]), _credits(r["other_credits"]),
            _credits(r["credits_needed"]), _credits(r["from_complimentary"]), _credits(r["from_purchased"]),
            _credits(r["to_buy"]), _credits(r["complimentary_left"]), _credits(r["purchased_left"]),
            _usd(r["token_cost_usd"]), _month_notes(r),
        ])
    by_month.append([
        StyledCell("Total", "text", True), _credits(sum(r["api_calls"] for r in months), True),
        _credits(sum(r["api_credits"] for r in months), True), _credits(sum(r["other_credits"] for r in months), True),
        _credits(t["credits_needed"], True), _credits(sum(r["from_complimentary"] for r in months), True),
        _credits(sum(r["from_purchased"] for r in months), True), _credits(t["to_buy"], True), None, None,
        _usd(t["token_cost_usd"], True), "",
    ])
    if res["settings"]["complimentary_reset"] == "jan1":
        by_month += [[], ["Complimentary credits reset on 1 January and expire on 31 December."]]

    by_year: list[list[Cell]] = [_head(
        "Year", "From", "To", "API credits", "Credits needed", "To buy", "To buy ($)", "Model tokens ($)",
    )]
    for y in res["years"]:
        by_year.append([
            y["year"], y["from"], y["to"], _credits(y["api_credits"]), _credits(y["credits_needed"]),
            _credits(y["to_buy"]), _usd(y["to_buy_usd"]), _usd(y["token_cost_usd"]),
        ])
    by_year += [[], _head("Where the credits go", "Credits", "Share")]
    total = t["credits_needed"] or 1.0
    for k, label in STREAM_LABELS.items():
        by_year.append([label, _credits(res["streams"][k]), StyledCell(round(res["streams"][k] / total, 4), "pct")])

    inputs: list[list[Cell]] = [_head("Input", "Value", "Source", "Note")]
    inputs += [list(r) for r in res["inputs"]]

    agents: list[list[Cell]] = [_head(
        "Agent", "Path", "Tasks a year", "Workday calls a year", "Agent-Ready Tool credits",
        "Invocation credits", "Model tokens ($)",
    )]
    for i, ag in enumerate(res["first_year"]["agents"], 1):
        agents.append([
            i, PATH_NAMES[ag["path"]], _credits(ag["tasks_per_year"]), _credits(ag["workday_calls_per_year"]),
            _credits(ag["tool_credits"]), _credits(ag["invocation_credits"]), _usd(ag["token_cost_usd"]),
        ])
    if res["agent_paths"]:
        first = res["agent_paths"][0]
        agents += [[], [StyledCell(f"Path comparison, first forecast year ({first['from']} to {first['to']}), with only "
                                   "this agent's path changed", "text", True)],
                   _head("Agent", "Path", "In use", "Credits needed", "Credits to buy", "Model tokens ($)", "What's included")]
        for row in res["agent_paths"]:
            agents.append([
                row["agent"], PATH_NAMES[row["path"]], "Yes" if row["current"] else "", _credits(row["credits_needed"]),
                _credits(row["to_buy"]), _usd(row["token_cost_usd"]), row["included"],
            ])
        agents.append(["Workday APIs show 0 only while you're inside your allowance."])
    if res["customer_sizing"]:
        sz = res["customer_sizing"]
        agents += [[], [StyledCell("Sizing for your customers", "text", True)]]
        for ag in sz["agents"]:
            cpt = ag["credits_per_task"]
            agents += [_head("Agent", "Path", "Credits per task"),
                       [ag["agent"], PATH_NAMES["api"] + " (above the allowance)", ag["api_credits_per_task_above_allowance"]],
                       [ag["agent"], PATH_NAMES["tools_external"], round_half_up(cpt["tools_external"], 4)],
                       [ag["agent"], PATH_NAMES["extend_custom"], round_half_up(cpt["extend_custom"], 4)],
                       _head("Agent", "Employee band", "Employees used", "Allowance", "Integration calls",
                             "Agent tasks a month that fit")]
            agents += [[ag["agent"], b["band"], _credits(b["employees"]), _credits(b["allowance_calls"]),
                        _credits(b["integration_calls"]), _credits(b["tasks_per_month_that_fit"])] for b in ag["bands"]]
        agents.append([f"Typical integrations assumed: {sz['integrations_assumed']}. No subscription uplifts."])

    assumptions: list[list[Cell]] = [_head("#", "Assumption")]
    numbered = list(res["caveats"]) + list(res["forecast_assumptions"])
    assumptions += [[i, text] for i, text in enumerate(numbered, 1)]
    if res["assumed"]:
        assumptions += [[], [StyledCell("Defaults and adjustments used in this forecast", "text", True)]]
        assumptions += [["", text] for text in res["assumed"]]

    questions: list[list[Cell]] = [_head("#", "Question to ask Workday")]
    questions += [[i, q["question"]] for i, q in enumerate([q for q in res["open_questions"] if q["applies"]], 1)]

    return [
        ("Summary", summary), ("By month", by_month), ("By year", by_year), ("Inputs", inputs),
        ("Agents", agents), ("Assumptions", assumptions), ("Open questions", questions),
    ]


COL_WIDTHS = {
    "Summary": [58, 22],
    "By month": [10, 14, 12, 13, 15, 19, 15, 12, 19, 15, 16, 44],
    "By year": [44, 10, 10, 13, 15, 13, 13, 16],
    "Inputs": [44, 60, 12, 60],
    "Agents": [8, 30, 22, 22, 24, 18, 90],
    "Assumptions": [5, 120],
    "Open questions": [5, 110],
}
FREEZE_ROWS = {name: 1 for name in COL_WIDTHS if name != "Summary"}


# ---------------------------------------------------------------- report


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    def clean(cell: str) -> str:
        return " ".join(str(cell).split()).replace("|", "/")

    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(clean(c) for c in row) + " |" for row in rows]
    return out


def render_report(res: Json) -> str:
    """report.md, following references/report-template.md. Text that came from the user's
    documents (organization, integration names, contract wording) is escaped."""
    t = res["totals"]
    price = res["sanitized"]["price_per_credit"]
    org = md_escape(res["organization"]) if res["organization"] else "your organization"
    lines = [f"# Workday Flex Credits forecast: {org}", ""]
    lines += [res["headline"], ""]
    if res["low_price_note"]:
        lines += [res["low_price_note"], ""]
    if res["path_note"]:
        lines += [res["path_note"], ""]
    if t["token_cost_usd"] > EPS:
        lines += [
            f"Model tokens are a separate bill: about {fmt_usd(t['token_cost_usd'])} over the period, paid to "
            "your model provider, not in credits.", "",
        ]

    lines += ["## Assumptions", ""]
    items = list(res["caveats"]) + list(res["forecast_assumptions"])
    lines += [f"{i}. {text}" for i, text in enumerate(items, 1)]
    if res["assumed"]:
        lines += ["", "Defaults and adjustments used because no source gave a value, or a value was outside the "
                  "model's range:", ""]
        lines += [f"- {a}" for a in res["assumed"]]
    lines.append("")

    lines += ["## Month by month", ""]
    lines += _table(
        ["Month", "API calls", "API credits", "Other credits", "Needed", "From free", "From purchased", "To buy",
         "Free left", "Notes"],
        [[r["month"], fmt_credits(r["api_calls"]), fmt_credits(r["api_credits"]), fmt_credits(r["other_credits"]),
          fmt_credits(r["credits_needed"]), fmt_credits(r["from_complimentary"]), fmt_credits(r["from_purchased"]),
          fmt_credits(r["to_buy"]), fmt_credits(r["complimentary_left"]), _month_notes(r)] for r in res["months"]],
    )
    lines.append("")

    lines += ["## Year by year", ""]
    lines += _table(
        ["Year", "Months", "API credits", "Credits needed", "To buy", f"To buy at {fmt_price(price)}", "Model tokens"],
        [[str(y["year"]), f"{y['from']} to {y['to']}", fmt_credits(y["api_credits"]), fmt_credits(y["credits_needed"]),
          fmt_credits(y["to_buy"]), fmt_usd(y["to_buy_usd"]), fmt_usd(y["token_cost_usd"])] for y in res["years"]],
    )
    rng = res.get("range")
    if rng:
        lines += ["", f"Range: {fmt_credits(rng['low']['credits_needed'])} to {fmt_credits(rng['high']['credits_needed'])} "
                  f"credits needed, {fmt_credits(rng['low']['to_buy'])} to {fmt_credits(rng['high']['to_buy'])} to buy, "
                  "with every volume halved or doubled."]
    for x in res["expiring_unused"]:
        lines += ["", f"{fmt_credits(x['credits'])} purchased credits (about {fmt_usd(x['usd'])} at {fmt_price(price)}) "
                  f"expire unused at the end of {month_name(x['month'])}. Purchased credits don't roll over."]
    lines.append("")

    lines += ["## Where the credits go", ""]
    total = t["credits_needed"] or 1.0
    lines += _table(
        ["Stream", "Credits", "Share"],
        [[label, fmt_credits(res["streams"][k]), f"{res['streams'][k] / total:.0%}"] for k, label in STREAM_LABELS.items()],
    )
    lines += ["", f"Value of all credits used, including free ones: {fmt_usd(t['credits_needed'] * price)} at "
              f"{fmt_price(price)} a credit. Complimentary credits pay for every stream.", ""]

    lines += ["## Agents and the path comparison", ""]
    fy = res["first_year"]
    if fy["agents"] and any(a["tasks_per_year"] > 0 for a in fy["agents"]):
        lines += _table(
            ["Agent", "Path", "Workday calls a year", "Tool credits", "Invocation credits", "Model tokens a year"],
            [[str(i), PATH_NAMES[a["path"]], fmt_credits(a["workday_calls_per_year"]), fmt_credits(a["tool_credits"]),
              fmt_credits(a["invocation_credits"]), fmt_usd(a["token_cost_usd"])]
             for i, a in enumerate(fy["agents"], 1)],
        )
        if res["agent_paths"]:
            first = res["agent_paths"][0]
            lines += ["", f"Each row is the first forecast year ({first['from']} to {first['to']}) with only that "
                      "agent's path changed; the row in use matches the year-by-year table.", ""]
            lines += _table(
                ["Agent", "Path", "In use", "Credits needed", "To buy", "Model tokens", "What's included"],
                [[str(r["agent"]), PATH_NAMES[r["path"]], "yes" if r["current"] else "", fmt_credits(r["credits_needed"]),
                  fmt_credits(r["to_buy"]), fmt_usd(r["token_cost_usd"]), r["included"]] for r in res["agent_paths"]],
            )
            lines += ["", "Workday APIs show 0 only while you're inside your allowance. Workday hasn't published a "
                      "rate for metering agents through Agent Gateway."]
        if fy["extend_implied"]:
            lines += ["", "Extend added to your subscriptions: Agent-Ready Tools and custom agents need Workday Extend "
                      "Professional, so the forecast applies its allowance uplift."]
    else:
        lines.append("No agents in this forecast.")
    lines.append("")

    if res["customer_sizing"]:
        sz = res["customer_sizing"]
        lines += ["## Sizing for your customers", ""]
        for ag in sz["agents"]:
            cpt = ag["credits_per_task"]
            lines += [f"Agent {ag['agent']}, {fmt_number(ag['calls_per_task'])} Workday calls per task.", ""]
            lines += _table(
                ["Path", "Credits per task"],
                [[PATH_NAMES["api"], f"0 inside the allowance; {ag['api_credits_per_task_above_allowance']:.3g} above it"],
                 [PATH_NAMES["tools_external"], f"{cpt['tools_external']:.3g}"],
                 [PATH_NAMES["extend_custom"], f"{cpt['extend_custom']:.3g}, model included"]],
            )
            lines += ["", f"API allowance headroom by employee band, after typical integrations "
                      f"({sz['integrations_assumed']}) and before subscription uplifts:", ""]
            lines += _table(
                ["Employee band", "Employees used", "Allowance", "Integration calls", "Agent tasks a month that fit"],
                [[b["band"], fmt_credits(b["employees"]), fmt_credits(b["allowance_calls"]),
                  fmt_credits(b["integration_calls"]), fmt_credits(b["tasks_per_month_that_fit"])] for b in ag["bands"]],
            )
            lines.append("")
        lines += ["Agent-Ready Tools and Extend agents don't use the API allowance (our assumption, caveat 5), and "
                  "need Workday Extend Professional, which raises the allowance by 50%.", ""]

    lines += ["## Integrations", "", _first_year_line(res)]
    integ = res["sanitized"]["integrations"]
    raw_integ = res["inputs_echo"].get("integrations") or {}
    if raw_integ.get("mode") == "inventory":
        employees = res["sanitized"]["employees"]
        lines += [""] + _table(
            ["Integration", "Calls a year"],
            [[md_escape(it.get("name") or f"Integration {i}"), fmt_credits(inventory_item_calls(it, employees))]
             for i, it in enumerate(raw_integ.get("items") or [], 1)],
        )
    elif integ["mode"] == "estimate":
        lines += [""] + _table(
            ["Pattern", "Integrations", "Calls a year each"],
            [[p, f"{n:g}", fmt_credits(pattern_calls(p, res["sanitized"]["employees"]))]
             for p, n in integ["counts"].items()],
        )
    lines.append("")

    lines += ["## Inputs and sources", ""]
    lines += _table(["Input", "Value", "Source", "Note"],
                    [[r[0], md_escape(r[1]) if r[0] == "Contract wording not modelled" else r[1], r[2], r[3]]
                     for r in res["inputs"]])
    lines.append("")

    lines += ["## Questions to ask Workday", ""]
    asked = [q for q in res["open_questions"] if q["applies"] or q["core"]]
    lines += [f"{i}. {md_escape(q['question']) if q['untrusted'] else q['question']}" for i, q in enumerate(asked, 1)]
    lines.append("")

    lines += ["## Levers", ""]
    if res["levers"]:
        lines += _table(
            ["Lever", "Credits saved", "To buy saved", "Model tokens saved"],
            [[lv["lever"], fmt_credits(lv["credits_saved"]), fmt_credits(lv["to_buy_saved"]), fmt_usd(lv["token_usd_saved"])]
             for lv in res["levers"]],
        )
        lines += ["", "Each lever is a rerun of this forecast with that one change."]
    else:
        lines.append("No lever in the standard set changes this forecast.")
    lines += ["", "---", "", res["disclaimer"], ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- outputs


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, float):
        return round(obj, 4) if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


def write_outputs(res: Json, out_dir: Path, formats: tuple[str, ...]) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    if "json" in formats:
        keep = {k: v for k, v in res.items() if k not in ("sanitized",)}
        path = out_dir / "result.json"
        path.write_text(json.dumps(_json_safe(keep), indent=2) + "\n", encoding="utf-8")
        written.append(path)
    if "md" in formats:
        path = out_dir / "report.md"
        path.write_text(render_report(res), encoding="utf-8")
        written.append(path)
    if "xlsx" in formats:
        path = out_dir / "forecast.xlsx"
        xlsx_writer.write_xlsx(path, build_sheets(res), COL_WIDTHS, FREEZE_ROWS)
        written.append(path)
    if "csv" in formats:
        path = out_dir / "forecast_by_month.csv"
        cols = ["month", "api_calls", "api_credits", "other_credits", "credits_needed", "from_complimentary",
                "from_purchased", "to_buy", "complimentary_left", "purchased_left", "token_cost_usd"]
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow([*cols, "notes"])
            for r in res["months"]:
                writer.writerow([r["month"], *(round(r[k], 4) for k in cols[1:]), _month_notes(r).replace(", ", "; ")])
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Forecast Workday Flex Credit use month by month.")
    parser.add_argument("--input", required=True, help="input JSON (see references/model.md)")
    parser.add_argument("--out-dir", required=True, help="folder for result.json, report.md and forecast.xlsx")
    parser.add_argument("--formats", default="xlsx,md,json", help="comma-separated: xlsx, md, json, csv")
    parser.add_argument("--constants", default=None, help="model constants JSON (default: the bundled one)")
    args = parser.parse_args(argv)

    formats = tuple(x.strip() for x in args.formats.split(",") if x.strip())
    bad = [x for x in formats if x not in FORMATS]
    if bad or not formats:
        print(f"--formats: unknown format(s) {', '.join(bad) or '(none)'}; use {', '.join(FORMATS)}", file=sys.stderr)
        return 2
    try:
        c = load_constants(args.constants)
    except (OSError, ValueError, KeyError) as exc:
        print(f"constants: {exc}", file=sys.stderr)
        return 2
    try:
        raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"input: can't read {args.input}: {exc}", file=sys.stderr)
        return 2
    errors = validate(raw, c)
    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        return 2
    try:
        res = build_result(raw, c)
    except (ArithmeticError, ValueError) as exc:
        print(f"input: these values are too large or inconsistent to forecast ({exc})", file=sys.stderr)
        return 2
    written = write_outputs(res, Path(args.out_dir), formats)
    for line in res["chat_summary"]:
        print(line)
    print("Files: " + ", ".join(str(p) for p in written))
    return 0


if __name__ == "__main__":
    sys.exit(main())
