# Workday Flex Credits

Forecasts how many Workday Flex Credits your organization will use month by month, what the
credits you have to buy would cost, when your free credits run out and what drives the
number. It covers Workday's own agents, agents you build, agents you buy and the integrations
that call Workday, and writes a spreadsheet and a Markdown report. For Workday admins,
integration leads and finance teams planning a budget or a renewal.

## Installation

Inside Claude Code, type:

```text
/plugin marketplace add StackOneHQ/powerful-plugins
/plugin install workday-flex-credits@powerful-plugins
```

Or from your terminal:

```bash
claude plugin marketplace add StackOneHQ/powerful-plugins
claude plugin install workday-flex-credits@powerful-plugins
```

For Codex, in your terminal:

```bash
codex plugin marketplace add StackOneHQ/powerful-plugins
codex plugin add workday-flex-credits@powerful-plugins
```

## Features

| Type | Name | Description |
|---|---|---|
| Skill | `flex-credit-forecast` | Asks a few questions, gives a first forecast by the second or third turn, then refines it from your Platform Consumption Console, order form or an export. Writes a by-month spreadsheet and a report with assumptions, a low-to-high range, a confidence level, a path comparison for agents and questions to ask Workday. |

## Usage

Ask in your own words, for example:

- "Forecast our Workday Flex Credits for the next 12 months"
- "We're buying an agent that uses Workday's Agent-Ready Tools. What will it use in credits?"
- "Read our Platform Consumption Console with me and tell me when our credits run out"

## How it works

1. **A first estimate in two turns.** Four quick questions (what to size, the period,
   employee count, whether you have real numbers), then up to four about the agents or
   integrations you picked. Anything you don't know takes a default and is listed as
   assumed.
2. **Refine if you want.** Read your Platform Consumption Console together in the browser,
   share an order form or a Console export, list your integrations one by one, or add growth
   for a multi-year view. Each refinement reruns the forecast and says what moved.

The forecast is month by month: API overage becomes billable from February 2027 and only
above your yearly allowance, complimentary credits reset on 1 January, and purchased packages
expire at the end of their term; the report says how many would go unused. Credits and dollars stay separate from model token cost,
which your model provider bills.

## Outputs

Four files in `./flex-credit-forecast/` in your working directory:

| File | Contents |
|---|---|
| `input.json` | Your answers and where each value came from |
| `result.json` | Every month, year and total, the range, confidence and sources |
| `report.md` | Summary, numbered assumptions, month and year tables, where the credits go, agent paths, integrations, questions for Workday and levers |
| `forecast.xlsx` | Summary, By month, By year, Inputs, Agents, Assumptions and Open questions sheets |

Ask for a CSV too if you want a by-month CSV. In the chat you get a short summary of at most
12 lines, taken straight from the script's output: the headline, what was assumed, the
first-year calls against your allowance and the top questions for Workday.

## Data handling

The forecast files are written only to ./flex-credit-forecast/ on your machine, and the
scripts make no network calls. Anything Claude reads, including your order form and Console
pages, is processed by your AI provider under your account's terms, like any other
conversation.

The privacy note above is repeated in the chat the first time anything from your order
form, an export or the Console is shown. The browser opens only when you say yes, and it
reads pages as you, in your own signed-in session. It asks before clicking export or download, and it never types credentials or
changes anything in Workday. Every document read gets a "Text addressed to AI tools" line
that quotes any instruction found inside it, or says none was found; such instructions are
never followed. It looks for files only where you point it.

## Model and sources

- Rates come from Workday's public Flex Credits rate card dated 9 October 2026. Workday says
  that card is informational; the rate card in your order form governs.
- API allowance bands and subscription uplifts follow analysts' reading (Incubane, Redress
  Compliance, i8CLOUD) of a policy Workday hasn't published. The 1 February 2027 billing date
  comes from Commit Consulting and Redress Compliance.
- Workday doesn't publish a price per credit. Analysts estimate under $0.01 to $0.10; the
  forecast starts at $0.10, the top of that range, until you give your contracted price.
- The assumptions are listed in every report. The full model is in
  `skills/flex-credit-forecast/references/model.md`.
- Every rate and band lives in `skills/flex-credit-forecast/scripts/model_constants.json`.
  To update them, follow "Updating the constants" in
  `skills/flex-credit-forecast/references/rate-card.md`.

## Requirements

- Python 3.9 or later. No packages to install.
- Optional: a browser extension for reading the Console, such as Claude in Chrome in Claude
  Code or the Chrome plugin in Codex. Without one, paste values or share an export.
- Reading the Platform Consumption Console needs the "Management Dashboard: Platform
  Consumption Console" security domain in Workday.

## Disclaimer

These are estimates, not a quote. This plugin is not produced or endorsed by Workday. Workday
and Flex Credits are trademarks of Workday, Inc.
