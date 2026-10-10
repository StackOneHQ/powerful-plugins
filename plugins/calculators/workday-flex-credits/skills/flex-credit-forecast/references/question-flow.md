# Question flow

The first forecast comes by the end of turn 2 or 3. Ask the turn 1 questions in one go, the
turn 2 questions in one go, then run the script. Everything else waits for the refine step.

## How to ask

- Claude Code: `AskUserQuestion`, 2 to 4 options per question. The tool adds "Other" itself,
  so never add a fifth option.
- Codex and other runtimes: plain text, numbered options, and say the user can answer
  "not sure".
- If the user picks Other and says they don't know, use the default, set its source to
  `default` and list it under Assumed.
- If the user's first message already answers a question, skip it. Never ask more than 4
  questions in a turn, and when you skip one, don't add another in its place.
- Answers picked from a list (a band, a pattern, a volume) have source `user`. They don't
  raise confidence; only the Console or a contract does.

## Turn 1 (one call, 4 questions)

| Question | Options | Maps to |
|---|---|---|
| What do you want to size? (multi-select) | Workday's own agents · An agent we build · An agent we buy · Our integrations | Which turn 2 questions to ask |
| What period? | Next 12 months · 24 months · 36 months | `forecast.months`. `forecast.start` is next month unless a contract says otherwise |
| How many employees? | Under 3,500 · 3,500 to 9,999 · 10,000 to 29,999 · 30,000 or more | `employees`: the band's midpoint (2,000 · 6,000 · 15,000 · 50,000). Ask for the exact number only for 30,000 or more, because the 100,000 band edge changes the allowance |
| Do you have real numbers to hand? | Estimates are fine for now · I can share our order form or an export · I can open our Platform Consumption Console (Workday's usage dashboard) | What to offer in the refine step. Nothing is read yet |

Integrations are always in the forecast, because every integration that calls Workday shares
the API allowance with agents. If the user didn't pick "Our integrations", use the default of
3 efficient and 2 typical integrations and list it under Assumed.

## Turn 2 (4 questions or fewer, only for the personas chosen)

When more than one persona was chosen, pick the 4 questions with the most effect on the
number (tasks a month and the path first) and use defaults for the rest.

### An agent we build, or an agent we buy

| Question | Options | Maps to |
|---|---|---|
| Tasks a month? | About 1,000 · About 10,000 · About 50,000 | `agents[].tasks_per_month` |
| Where will the agent you're sizing run? | Our own code or an agent platform · A vendor's product · Built inside Workday Extend | Extend sets `path = "extend_custom"`; the other two lead to the next question |
| If outside Workday, how does it reach Workday? | Workday's APIs, directly or through a connector or MCP server · Workday's Agent-Ready Tools (Workday-hosted MCP tools) · Not sure | `path`: `api`, `tools_external` or `unsure`. With `unsure` the script computes both and reports both |
| Workday calls per task? | 3 · 5 · 10 | `agents[].calls_per_task` (default 4 for build, 5 for buy) |

### Workday's own agents

| Question | Options | Maps to |
|---|---|---|
| Self-Service Agent actions per employee a month? | 1 · 2 · 5 | `ssa_actions_per_employee_month`. Averaged over all employees, users or not. One question can use several actions |
| Other Workday agents? | None · Recruiting Agent: Fetch · Contract agents · Payroll agents | `skills[]`; then ask the yearly volume in a short follow-up (requisitions, documents or requests). If the user doesn't know, use 100 a year and list it under Assumed |

Contract agents map to `contract_negotiation` or `contract_intelligence`; payroll agents map
to `payroll_qa`. The full list of skill keys is in `model.md`.

### Our integrations

| Question | Options | Maps to |
|---|---|---|
| How many counted integrations, roughly? | 1 to 5 · 6 to 15 · More than 15 | Total count: 3 · 10 · 20 |
| How do most of them sync? | Changes only · Full pull hourly · Full compare every few minutes | Which pattern gets most of the count: `efficient`, `typical` or `heavy` |

Split the count as about 70% in the chosen pattern and the rest in `typical` (or `efficient`
when the chosen pattern is `typical`), rounding to whole integrations.

Counted integrations are Studio integrations, Orchestrations, modified Workday integrations,
partner and certified integrations and external agents. Unmodified Workday-built integrations
such as Core Connectors are exempt (analysts' reading of the policy).

## Then

Run `forecast.py` on these answers and the defaults, then show the summary. Then offer:

> Want a tighter number? I can read your Console (with you watching), read your order form or
> an export, list your integrations one by one, or add growth for a multi-year view.

If the user is an existing customer, ask for the free credits left today (Credit Balance in
the Console) and set `forecast.opening_complimentary`; otherwise the forecast assumes the
prorated grant and says so.

Keep one output folder. Offer other scenarios as reruns with a changed `input.json`, and
say what changed.

Ask about growth only when `months` is more than 12. Defaults, each listed under Assumed:
0% a year for integrations, 50% for agents, 20% for Workday's agents.

The read-format question (Full SOAP records · REST detail · Reports or lean JSON) comes only
in the refine step, because it changes token cost and not credits. Typed input accepts all 7
read formats in `model.md`.

## Refine branches

Each branch is described in `data-sources.md`. After each one, update `input.json` and its
`sources`, rerun, and say in one line what moved and why.

| Branch | What it gives |
|---|---|
| Console in the browser | Allowance, complimentary grant, balances, packages, measured calls, contracted rates, top callers |
| Order form or contract | Price per credit, subscription dates, SKUs, employee count, purchased packages, policy version and date |
| Export, screenshots or pasted values | Measured calls, balances |
| Email | Alert levels already hit; vendor answers on sync patterns |
| Integration inventory | Calls per integration, summed into a measured total |

## Sizing for your customers (vendors)

When the user builds or sells an agent and sizes it for their customers, set
`"customer_sizing": true` in `input.json`. The script then prints and reports, for each path,
the credits per task, and for each employee band the agent tasks a month that fit in the API
allowance after typical integrations. Quote those figures; don't work them out yourself. Give
conditional figures ("0 credits while the tenant stays
under its allowance; X credits a year through Agent-Ready Tools"), not a recommended path,
and don't write customer-facing claims into the report.
