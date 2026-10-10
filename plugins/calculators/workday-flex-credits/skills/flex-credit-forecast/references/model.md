# Model: input format, formulas and the monthly engine

`scripts/forecast.py` implements everything here, and `scripts/model_constants.json` holds
every rate, band, default and range. The repository tests check the script against the
golden vectors in that JSON.

## Input JSON

Every key is optional. A missing or null value takes the default. Numbers above a range are
capped, and each cap is reported in the result's `adjusted` list, at the top of the Assumed
list and in the Inputs table. The script rejects, with one line per problem and exit code 2:
negative numbers, employees under 100, a price under $0.005, fewer than 1 call per task, an
`advanced_share` above 1, unknown keys in the lists below, a value of the wrong type, months
outside 2000 to 2100, growth above 10 (1,000%), and inventory items whose calls can't be
counted.

`organization` (text) names the report. `customer_sizing` (true or false) adds, for vendors,
the credits per task on each path and the agent tasks a month that fit in each employee
band's API allowance after typical integrations (the input's integration counts, or 3
efficient and 2 typical), at 2,000, 6,000, 15,000, 50,000 and 150,000 employees. `contract_notes` (a list of text) carries order-form
wording the model doesn't cover, such as rollover, true-down or rate lock, word for word.

```json
{
  "organization": "Example Retail Co",
  "employees": 8200,
  "skus": ["extend"],
  "price_per_credit": 0.10,
  "integrations": {"mode": "estimate", "counts": {"efficient": 4, "typical": 2, "heavy": 1}},
  "ssa_actions_per_employee_month": 2,
  "skills": [{"skill": "recruiting_fetch", "volume_per_year": 60}],
  "agents": [{"tasks_per_month": 10000, "calls_per_task": 5, "path": "unsure",
              "read_format": "rest_detail", "advanced_share": 0.10, "model_tier": "standard"}],
  "advanced": {"purchased_credits": 0, "policy_signed": true, "llm_price_per_m_tokens": 3.0,
               "context_rereads": 1.0, "tool_calls_also_metered_as_api": false,
               "allowance_override": null, "complimentary_override": null},
  "forecast": {"start": "2026-11", "months": 24,
               "growth": {"integrations": 0.0, "agents": 0.5, "workday_agents": 0.2}},
  "sources": {"employees": "user", "api_calls": "user", "allowance": "default"}
}
```

| Key | Values | Default |
|---|---|---|
| `employees` | 100 to 500,000 | 10,000 |
| `skus` | `student`, `procurement`, `accounting_center`, `extend`, `prism`, `financials` | none |
| `price_per_credit` | $0.005 to $0.50 | $0.10 |
| `integrations.mode` | `estimate` (with `counts`), `measured` (with `calls_per_year`), `inventory` (with `items`) | `estimate` |
| `integrations.counts` | `efficient`, `typical`, `heavy`: 0 to 50 each | 0 |
| `ssa_actions_per_employee_month` | 0 to 20 | 0 |
| `skills[].skill` | `recruiting_fetch`, `talent_mobility`, `contract_negotiation`, `financial_audit`, `revenue_contract`, `payroll_qa`, `core_reporting`, `recruiting_spotlight`, `contract_intelligence` | none |
| `skills[].volume_per_year` | 0 to 100,000 units | 0 |
| `agents[].tasks_per_month` | 0 to 10,000,000 | 0 |
| `agents[].calls_per_task` | 1 to 50 | 4 |
| `agents[].path` | `api`, `tools_external`, `extend_custom`, `unsure` | `api` |
| `agents[].read_format` | `full_soap`, `rest_detail`, `lean`, `soap_raw_full`, `soap_trimmed`, `rest_list_item`, `lean_json` | `rest_detail` |
| `agents[].advanced_share` | Share of tool calls that change data, 0 to 1 | 0.10 |
| `agents[].model_tier` | `base`, `standard`, `premium` (Extend custom agents) | `standard` |
| `advanced.purchased_credits` | Credits bought for the period. Without `forecast.purchased_packages`, the forecast treats it as one package covering the first 12 months | 0 |
| `advanced.policy_signed` | Signed the Flex Credits and Platform Entitlement Policy | true |
| `advanced.allowance_override` | Yearly allowance from the Console or contract; replaces band × uplift; 0 is valid | null |
| `advanced.complimentary_override` | Yearly complimentary grant from the Console; 0 is valid | null |
| `advanced.tool_calls_also_metered_as_api` | Also count Agent-Ready Tool calls against the API allowance (unconfirmed) | false |
| `advanced.llm_price_per_m_tokens` | $0 to $100 per million input tokens | $3.00 |
| `advanced.context_rereads` | 1 to 5 | 1.0 |

Inventory items are `{name, calls_per_year}`, `{name, pattern}` (optional `records`,
default `employees`) or `{name, runs_per_year, records_per_run, page_size, writes_per_year}`.

### `forecast`

| Key | Meaning | Default |
|---|---|---|
| `start` | First month, `YYYY-MM` | Next month |
| `months` | 1 to 60 | 12 |
| `growth` | Yearly growth for `integrations`, `agents`, `workday_agents`, applied as a step at each forecast-year boundary (0.2 is 20%) | 0 each |
| `purchased_packages` | `[{credits, from, to}]`, available from `from` to `to` inclusive, then expire | none |
| `opening_complimentary` | Complimentary credits left at `start` | C0 × (12 − start month index) / 12 with a 1 Jan reset, else C0 |
| `complimentary_reset` | `jan1` (policies effective on or after 29 May 2026) or `start_anniversary` | `jan1` |
| `complimentary_assumed_after` | Renewal month; later months are flagged as assumed | null |
| `allowance_year_start` | When the API allowance year starts | `start` |
| `allowance_used_at_start` | Allowance calls already used at `start` | 0 |
| `allowance_counts_during_grace` | Calls before February 2027 count toward the allowance | true |

### `sources`

Each value is `console`, `contract`, `user` or `default`. Missing keys count as `default`.

| Key | Covers |
|---|---|
| `allowance` | The yearly API allowance |
| `complimentary` | The yearly complimentary grant (`pool` is accepted for both this and `purchased`) |
| `purchased` | Purchased credit packages |
| `api_calls` | Integration calls |
| `price_per_credit`, `employees`, `skus`, `policy_signed` | The input of that name |
| `agents`, `workday_agents` | Agent volumes; Self-Service Agent and skill volumes |
| `forecast_start`, `growth`, `rates`, `model_price` | Forecast start, growth rates, contracted rates, model price |

A key left out counts as `user` when the input plainly holds the user's own figure (an
override, a measured or inventory total, a non-default price), otherwise `default`. A key
given explicitly is never changed.

`confidence`, applied in this order:
1. `low` when the source behind the biggest credit stream is `default` (API overage:
   `api_calls`; Workday's agents: `workday_agents`; your agents: `agents`).
2. `high` when `allowance`, `complimentary` and `api_calls` all come from the Console or a
   contract.
3. `medium` when at least one of them does.
4. `low` otherwise. Answers picked from a list (`user`) never raise it on their own.

Every `default` source becomes a line in the result's `assumed` list, with the arithmetic
where it matters (the band allowance times any uplift, including an implied Extend uplift,
and the prorated free balance at the start).

## Annual formulas (`compute`)

```
band       = first band with employees >= min_employees (100k, 30k, 10k, 3.5k, 0)
skus*      = skus + extend, if any agent with tasks > 0 uses tools_external or extend_custom
             (both need Workday Extend Professional; extend_implied = true when added)
E          = allowance_override, else band allowance × (1 + sum of uplifts for skus*)
C0         = complimentary_override, else band complimentary credits
Pool       = C0 + purchased_credits

A_int      = measured calls, or sum of count × pattern(N) over patterns
             efficient(N) = 35,040 + 52 × ceil(N / 999)   changes every 15 min, weekly full sync at 999 a page
             typical(N)   = 8,760 × ceil(N / 100)         hourly full pull at 100 a page
             heavy(N)     = 105,120 × ceil(N / 100)       full compare every 5 min at 100 a page
Cr_ssa     = employees × SSA actions × 12 × 1
Cr_skills  = sum of volume × credits per unit

per agent: Q = tasks a month × 12, X = Q × calls per task
  api            : API calls += X
  tools_external : Cr_tools += X × ((1 − adv) × 10 + adv × 50) / 100
  extend_custom  : Cr_tools += X × ((1 − adv) × 5 + adv × 25) / 100, Cr_inv += Q × {1, 2, 3}
  tool_calls_also_metered_as_api and path is not api : API calls += X
  token $ (path is not extend_custom) += X × tokens per call × rereads × model price / 1,000,000

A_total    = A_int + agent API calls
Over       = max(0, A_total − E)
Cr_api     = Over × 0.006 if the policy is signed, else 0
Need       = Cr_api + Cr_ssa + Cr_skills + Cr_tools + Cr_inv
Shortfall  = max(0, Need − Pool)
Driver     = the largest of the five streams
```

## Monthly engine (`run_forecast`)

For each month `m` from `start`:

1. Year index `m // 12`. Volumes scale by `(1 + growth) ^ year index`. The annual model runs
   unclamped (growth can pass the ranges above) with purchased credits set to 0.
2. Monthly API calls = `A_total / 12`. The running count resets at each allowance-year
   anniversary. A month counts toward the allowance when `allowance_counts_during_grace` is
   true or the month is February 2027 or later.
3. API credits = `0.006 × [max(0, running − E) − max(0, previous running − E)]`, billed only
   from February 2027 and only if the policy is signed.
4. Other credits = `(Need − Cr_api) / 12`.
5. The complimentary balance resets to C0 on 1 January (or on the anniversary of `start`).
6. Credits are drawn soonest-expiring first; on a tie, complimentary credits go first.
   Complimentary credits expire on 31 December (or at the anniversary); a package expires
   after its `to` month. Whatever is left is `to_buy`.

Outputs per month: API calls, API credits, other credits, credits needed, credits taken from
complimentary and from purchased, to buy, both balances, token $, and flags (grace period,
free credits reset, assumed after renewal, new allowance year). Years and totals sum the
months. `free_credits_run_out` is the first month with something to buy.

**Range:** the forecast reruns with every volume (integration calls, agent tasks, Self-Service
Agent actions, skill volumes) halved and doubled.

**Unsure path:** an agent with `path: "unsure"` runs once as `api` and once as
`tools_external`. The higher result (by credits to buy, then credits needed) leads, and
`path_variants` and `path_note` give the other.

**Purchased credits don't roll over.** Whatever is left in a package after its `to` month is
reported in `expiring_unused` (month, credits, dollars), in the headline and as a "Package
expires" note on that month. With purchased packages, the headline says "You start buying
more in {month}" instead of "Free credits run out in {month}".

**Chat summary.** The script prints a ready-to-paste summary of at most 12 lines (also in
`chat_summary` in result.json): the headline, the $0.01 line, the other path for an unsure
agent, first-year calls against the allowance, up to 5 Assumed lines, the top 2 questions
for Workday and the file paths.

## Derived values in the report

- **Path comparison:** for each agent with tasks, the monthly engine reruns with that agent
  on each of the three paths, nothing else changed, and reports the first forecast year. The
  row for the path in use equals year 1 in the By year table.
- **Levers:** full reruns with one change each, ordered by credits saved: move typical and
  heavy integrations to efficient; agents read reports or lean JSON (tokens only); 10% fewer
  integration calls from capping retries and duplicate pulls (illustrative).
