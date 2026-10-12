# Rates, bands, dates and sources

Every number here is also in `scripts/model_constants.json`, which the script reads. When
they disagree, the JSON wins; update this file to match.

Confidence: **Workday** means a public Workday document. **Analysts** means a third-party
reading of a policy Workday hasn't published. **Our reading** means an interpretation the
forecast makes and labels.

## Meters

| Meter | Rate | Confidence |
|---|---|---|
| API calls above the yearly allowance | 60 credits per 10,000 calls (0.006 a call), "includes ingress and egress" | Workday, rate card 9 Oct 2026 |
| Self-Service Agent | 1 credit per action. A task can use several actions | Workday, rate card |
| Recruiting Agent: Fetch | 750 per requisition | Workday, rate card |
| Talent Mobility Agent | 750 per requisition | Workday, rate card |
| Contract Negotiation Agent | 500 per document | Workday, rate card |
| Financial Audit Agent | 60 per sample | Workday, rate card |
| Revenue Contract Agent | 25 per contract | Workday, rate card |
| Payroll Agent: Q&A | 10 per request | Workday, rate card |
| Core Reporting Agent | 8 per request | Workday, rate card |
| Recruiting Agent: Spotlight | 6 per resume | Workday, rate card |
| Contract Intelligence Agent | 5 per document | Workday, rate card |
| Agent-Ready Tool calls, agents built outside Workday | 10 per 100 base calls, 50 per 100 advanced (data-changing) calls | Workday rate card's "non-Custom Agents" rate; applying it to agents built outside Workday is our reading |
| Agent-Ready Tool calls, custom agents in Workday Extend | 5 per 100 base calls, 25 per 100 advanced calls | Workday, rate card |
| Extend Professional custom agent runs | 1, 2 or 3 credits per invocation (Base, Standard, Premium model tier), model included | Workday, rate card |

Agent-Ready Tools and custom agents need Workday Extend Professional (Workday, SKU
prerequisites, 8 Oct 2026), so the forecast adds the Extend allowance uplift when either is
chosen and reports `extend_implied`.

Workday agents that the rate card lists don't count against the API allowance. Unmodified
Workday-built integrations, including Core Connectors, are exempt (analysts' reading of the
policy).

## Allowance and complimentary credits by employee band

| Employees | Yearly API allowance | Yearly complimentary credits |
|---|---|---|
| Under 3,500 | 2,500,000 | 15,000 |
| 3,500 to 9,999 | 3,500,000 | 30,000 |
| 10,000 to 29,999 | 4,500,000 | 60,000 |
| 30,000 to 99,999 | 6,000,000 | 120,000 |
| 100,000 or more | 6,500,000 | 200,000 |

Allowance bands: analysts (Incubane, Redress Compliance, i8CLOUD). Complimentary credits:
Workday, Complimentary Flex Credits Policy (21 May 2026) and Flex Credits Policy (8 Oct 2026).

## Subscription uplifts to the allowance

Each uplift is a share of the band's allowance, and they add up (analysts).

| Subscription | Uplift |
|---|---|
| Student | +150% |
| Procurement | +100% |
| Accounting Center | +100% |
| Extend | +50% |
| Prism Analytics | +15% |
| Financials | +15% |

## Dates and rules

| Rule | Value | Confidence |
|---|---|---|
| API overage billable from | 1 February 2027 (no charges from 30 May 2026 to 31 January 2027) | Analysts (Commit Consulting, Redress Compliance) |
| Who pays API overage | Only customers who signed the Flex Credits and Platform Entitlement Policy | Workday, Console admin guide |
| Complimentary reset | 1 January for policies effective on or after 29 May 2026, first grant prorated by month; earlier policies reset on their anniversary | Workday, Flex Credits Policy |
| API allowance reset | Yearly; the date isn't clear. The forecast starts the allowance year at the forecast start | Analysts; open question |
| Rollover | None. Purchased credits expire at the end of the subscription period | Workday, Flex Credits Policy |
| Draw-down order | Allowance first, then credits, soonest-expiring first | Workday, Console admin guide |
| Alerts | 80%, 90% and 100% of entitlement. Offers aren't switched off at 100%; the customer pays for overages | Workday, Console admin guide and Flex Credits Policy |
| Counting unit | One request is one call: a page of results, a report run, a record written | Our reading; Workday hasn't confirmed it |
| Transports | SOAP, REST, RaaS and WQL all count | Workday, API Activity Reports doc |

## Price per credit

Workday doesn't publish one. Analysts estimate under $0.01 to $0.10. The forecast starts at
$0.10, the top of that range, so the dollar figure is a ceiling until the user gives the price
on their order form. At $0.10 a credit, 10,000 API calls above the allowance cost $6.00.

## Model tokens

A separate bill, paid to the model provider by whoever runs an agent outside Workday. Never
added to credits. Extend custom agent credits include the model.

| Read format | Tokens per call |
|---|---|
| Raw SOAP, every response group | 33,153 |
| Full SOAP responses | 14,207 |
| SOAP with trimmed response groups | 6,370 |
| REST detail responses | 1,300 (default) |
| REST list item | 490 |
| Reports (RaaS) or lean JSON | 205 |
| Lean JSON, 13 fields | 92 |

Counts come from synthetic Workday payloads, input tokens only, and vary about 15% by
tokenizer. Default model price: $3.00 per million input tokens.

## Sources

The `sources` list in `model_constants.json` holds the titles and URLs: the Workday rate card
(9 Oct 2026), Flex Credits Policy, Complimentary Flex Credits Policy, SKU prerequisites, the
Platform Consumption Console and API Activity Reports admin guides, and the analyst notes from
Incubane, Redress Compliance, Commit Consulting and i8CLOUD.

The rate card is informational; the rate card in the customer's order form governs.

## Updating the constants

When Workday publishes a new rate card or policy, edit `scripts/model_constants.json`: change
the rates, bump `version` and `rate_card_date`, and recompute the expected values in its
`vectors` list (they are the model's outputs for each input, so rerun them and check a few by
hand). Add the new version to `SUPPORTED_VERSIONS` in `forecast.py`, because the script
refuses a constants file whose `version` it doesn't know. The repository's tests pin the
file's sha256, so update that too, then bump the plugin version.

The billing date, the rate card date, the API rate and the low end of the price range in the
report text come from the constants. Text to edit by hand: the caveats in `forecast.py`
(`CAVEATS`), the "What's included" lines (`PATH_INCLUDED`) and this file.
