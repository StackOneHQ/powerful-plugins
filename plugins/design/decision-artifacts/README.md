# Decision Artifacts

Turn a set of findings into a page where someone can compare options, inspect the evidence and record a choice. On the next review, they can see which questions still need an answer and what happened to earlier decisions.

## Install

Decision Artifacts works on its own. Choose the commands for your tool.

**Claude Code**

```text
/plugin marketplace add StackOneHQ/powerful-plugins
/plugin install decision-artifacts@powerful-plugins
```

**Codex**

```sh
codex plugin marketplace add StackOneHQ/powerful-plugins
codex plugin add decision-artifacts@powerful-plugins
```

## Try it with one decision

> Use Decision Artifacts to help me choose a support plan for a six-week launch. Our current plan costs $300/month and promises a reply within two business days. Priority costs $480/month and promises four business hours. Our budget is $500/month. Make a local HTML page where I can compare the plans, see the trade-off, and pick one with a note.

Open the file. You should see the $180 monthly premium beside the difference in promised **reply** time. Pick a plan, add your reason and select **Copy my answers**. Paste that into the chat and ask the agent to update the page. Your choice becomes a receipt. Whether anyone has changed the plan is a separate field.

Use the same prompt with your own notes, quotes or findings. On a host with built-in answer storage accessible to the agent, the agent can read answers back directly. A local HTML file works offline and uses the copy-and-paste handoff. Shared pages and controls that take an external action need the appropriate host capabilities and your confirmation.

## Other ways to use it

- **Review a cost increase.** “Show which teams drove this month's bill. Let me filter by team, inspect the evidence and choose what to cut.”
- **Present a decision.** “Turn these vendor quotes into a six-slide decision deck. Put the recommendation first and the evidence in the appendix.”
- **Explain a change.** “Walk me through this retry policy with one example. Let me change the delay cap and compare it with today's behavior.”
- **Refresh a review.** “Update the same page with these results. Show what still needs me, what we picked last time and whether it worked.”

The bundled skill chooses a layout from the reader's task. You can ask for an editorial brief, dashboard, technical walkthrough or narrative. If you want a particular brand, chart or writing style, name an installed skill in your request. The page, charts, answer controls and evidence panels all work with Decision Artifacts alone.
