# Spend reviews

Read this when a page answers "where does this total go, and what should we change": a cloud bill, model or token spend, compute hours, seats. It pairs `explore` (the reader slices the data) with `decide` (savings to approve). The page shape, evidence and answer rules in `SKILL.md` still apply.

## Data

- Keep one tidy dataset: a row per day, owner, product, billed meter and resource, with usage, unit, list cost and net cost (after included amounts or credits). Every view is a calculation over it, so filters and windows stay consistent.
- Pull twice the longest window shown, so "last 30 days" compares with the 30 before. Where a source keeps less history, leave that series out of comparisons and say so beside the number.
- Assign owners by stated rules (resource name patterns, a model-to-owner map). Name shared and unassigned spend as rows of their own.
- Keep judgement apart from data: findings and decisions are their own dated datasets, so a data refresh can't carry stale advice forward.
- A snapshot says what it is: source, window, when it was pulled, and "estimate, not the invoice" when that's true.

## Tabs

1. **Overview.** A headline sentence computed from the data (total, monthly pace, the two largest owners and their shares). Four tiles: the window's total, the pace from the last 7 days, the change on comparable series, and the waste figure the decisions turn on. An owner table with two windows, the daily rate now and before, the change and a share bar; each row opens Explore filtered to that owner. Four to six findings, each with a text label as well as a tone colour. A savings chart with one low-to-high range bar per decision.
2. **Explore.** One shared filter state: period, net or list, group by (owner, product, resource, meter), stacked, lines or share, day or week, filter chips and Reset. Clicking a bar, legend entry, row or box filters every view to it and adds a removable chip. Views: cost over time, a searchable ranked list with share, change and a sparkline per row, a product-to-resource treemap, and a meter table showing what the plan covered.
3. **Waste.** The inefficiency the savings come from, with its rule on the page (for idle compute: "up 45 minutes or more of an hour, under 1% of its CPU"). Working against wasted units per day, a scatter of time up against work done (log axes, dot size is cost), per-group bars, and a sortable table of the worst items with a "still running" flag.
4. **Decisions.** One row per decision: action, evidence, where, effort, status and a monthly saving range at the recent pace, with the usual choice and note. Method notes close the tab.

## Traps

- A source with shorter history makes the earlier period look cheap. Mark the gap on the time chart itself ("no data before 19 Sep"), recover what older pulls kept, and name the missing months in the headline finding, not only in a note.
- A percent change on a near-zero base misleads: "+1,147%" when last month fit inside the free tier. Print both amounts beside it, or compare at list price.
- Colour follows the entity, not its rank, through every filter. Fold series past the seventh into "Other".
- Savings are ranges with their basis ("at the last 7 days' pace"). Say when two savings overlap, and label a risk-only item as risk instead of showing $0.
- Recompute the findings after every refresh and check each number in them against the data.
- Rebuild an existing review from its published source, not from a summary of it. Summaries keep the totals and lose the controls.
