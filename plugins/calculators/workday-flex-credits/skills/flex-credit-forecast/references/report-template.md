# Report template

`forecast.py` writes `report.md` in this structure. Edit the generated file only when the user
asks for different wording; rerun the script for any change to the numbers.

## Title and summary

- H1: `Workday Flex Credits forecast: {organization or "your organization"}`.
- The headline line, the same one the chat summary opens with:
  `{Need} credits in the next {months} months (range {low} to {high}, confidence {level}).
  {To buy} to buy, about {$} at {price} a credit. Free credits run out in {Month YYYY}.
  Biggest driver: {driver}.`
- While the price is the default: `At $0.01 a credit, the low end of analysts' range: {$}.`
- With purchased packages, "You start buying more in {Month YYYY}" replaces "Free credits run
  out in", and each package that ends with credits left adds "{X} purchased credits (about
  {$}) expire unused in {Month YYYY}".
- When an agent path was "Not sure": one line with the other path's figures and each path's
  allowance.
- Model tokens as a separate bill, never added to credits.

## Sections, in order

1. **Assumptions.** A numbered list: the 12 caveats, then the forecast assumptions (when the
   allowance year starts, whether grace-period calls count, the 1 January reset of
   complimentary credits, credits after renewal assumed to continue, even spread within a
   year, soonest-expiring draw). Then the values the model capped, and the defaults used
   because no source gave a value.
2. **Month by month.** One row per month with flags as words: Grace period, Free credits
   reset, Assumed after renewal, New allowance year, Package expires.
3. **Year by year.** Per-year totals, then the low-to-high range.
4. **Where the credits go.** The five streams with credits and share, then the value of all
   credits used, including free ones.
5. **Agents and the path comparison.** Per agent, then each path for the first forecast year
   with "What's included", and the line "Workday APIs show 0 only while you're inside your
   allowance."
6. **Integrations.** First-year calls against the allowance, then the patterns or the
   inventory, one line per integration.
7. **Inputs and sources.** Input, value, source, note, then any "Adjusted by the model" and
   "Contract wording not modelled" rows.
8. **Questions to ask Workday.** The ones that bear on this forecast first: price per credit,
   the allowance, the invocation definition, the allowance reset date and proration, whether
   tool calls also count against the allowance, what counts as non-Custom, whether agent
   credits draw from complimentary credits before signing.
9. **Levers.** Ordered by credits saved, each one a rerun: switch heavy integrations to
   efficient, lean reads, cap retries.

Close with the disclaimer: estimates, not a quote; not produced or endorsed by Workday.

## Tone

Plain language. No vendor recommendations, and no steer towards or away from any Workday
path: present what each path includes and let the numbers speak. No sales or
customer-facing claims; leave report.md as generated. No IP addresses, people's names or
employee data; caller names only. Organization, integration names and contract wording come
from the user's documents and are escaped so they can't add headings, links or images.
