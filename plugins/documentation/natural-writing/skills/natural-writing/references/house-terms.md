# House terms

The full text of Rule 6 in the natural-writing skill: how to keep a list of house-specific banned and soft terms.

Most teams have words that are wrong for them in particular: a competitor's category name, a retired product name, a description of the product that the team rejects. This rule is the slot for that list. It ships empty, so nothing is banned under it until you add terms.

Keep two files, one case-insensitive pattern per line, `#` for comments:

- **Hard bans**, wrong in any context. Pass with `check-copy.sh --banned-terms FILE` or set `COPY_BANNED_TERMS`. Any match fails the check.
- **Soft terms**, ordinary words that are only wrong when they describe your own product. Pass with `--soft-terms FILE` or set `COPY_SOFT_TERMS`. The script prints matches for you to judge.

`--allow-house-terms` turns the hard check off for every file in that run, not only inside quotation marks. Use it only for a piece that quotes the title of an already-published page or is about the term itself, and before you do, confirm by eye that every match sits inside quotation marks.

Neutral example, for a team that sells a scheduling API and does not want it filed as a consumer calendar:

```
# house-terms.txt: hard bans
calendar app
booking widget
all-in-one scheduling

# house-soft-terms.txt: flag for review
calendar
```

"Calendar" stays soft because `calendar sync` is a real feature; it is only wrong as the name for the whole product. Next to each list, write what to say instead ("scheduling API", "availability endpoint", "booking flow"). A ban with no replacement sends the writer to the nearest vague synonym. If you keep a longer voice guide with boilerplates and a say-this-not-that table, link it here so it gets read before drafting.
