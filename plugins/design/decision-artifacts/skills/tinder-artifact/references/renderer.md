# Render the user's deck

Write a UTF-8 file named for the task, such as `onboarding.tinder.json`. Keep the user's brief and boundaries in `brief`. Assign a unique `task-` ID using lowercase letters, digits and hyphens. A new proposal that changes what a prior approval would authorize needs a fresh deck ID when using the standalone renderer.

```json
{
  "id": "task-onboarding-note-v1",
  "brief": "Prepare the welcome note for our internal pilot. Keep the message a draft.",
  "payload": {
    "title": "Review the pilot welcome note",
    "cards": [
      {
        "job": "review",
        "kind": "proposal",
        "required": true,
        "question": "Use the draft wording for the welcome note?",
        "context": "The first line appears immediately after someone joins the pilot.",
        "before": "You're all set!",
        "after": "Your pilot workspace is ready. Open your first decision card when you're ready to start.",
        "recommendation": "Use the revision.",
        "reason": "It gives the reader a concrete first step.",
        "action": "Use the approved sentence in the draft welcome note.",
        "source": "The before text comes from the sample welcome note. The after text is a proposed edit.",
        "uncertainty": "The team has not tested the wording with pilot users.",
        "dependsOn": []
      }
    ]
  }
}
```

Each deck holds 1–24 decisions. Each card needs `question`, `context`, `recommendation`, `reason`, `action`, `source`, `uncertainty`, and a boolean `required`. Use `guide`, `review` or `triage` for `job`. Choose `proposal`, `single` or `multi` for `kind`. Single and multiple choice need 2–8 options with `label` and `detail`. Set `recommended: true` on one single-choice option or each recommended multi-choice option. The reader can approve the defaults with one swipe. Older decks use matching option labels from the recommendation text. If the recommendation cannot be matched, the first option is labelled Default. A review includes `before` and `after`. A triage item includes `item` and `preview`. List dependencies by earlier, one-based card numbers. Keep the action precise enough to execute as written.

Run the packaged command from this skill directory. It validates the deck and creates a self-contained HTML file. Give the user the clickable HTML file. For an existing Tinder GPT Site, also offer the JSON file, which imports through **Use your own task**. The same deck works in both.

```sh
node scripts/render-deck.mjs /absolute/path/onboarding.tinder.json /absolute/path/onboarding-review.html
```

Use a new output filename on revisions so the user retains the previous file. For the browser-only renderer, the user reviews the batch, chooses **Copy decisions for AI**, and pastes it into the originating chat. On receipt, use the submission ID and each card's disposition to perform the authorized actions and return the deliverable. Put revised and newly required decisions into the next deck and carry settled answers into its context.

## Send to the originating chat

From the originating Codex chat, launch the receiver in a retained process. It reads the trusted `CODEX_THREAD_ID` provided by the host and checks the installed CLI for `codex queue --thread … --resume`. Use a private receipt directory the agent can read, outside the deployed Site, and a short label the user will recognize. Give it the same JSON deck or seeded HTML generated above. Use the packaged renderer HTML for the built-in pilot.

```sh
node scripts/connect-deck.mjs /absolute/path/onboarding.tinder.json /private/agent-readable/receipts "Onboarding review"
```

Open the returned `local` link for the reviewer. To pair a published Site page, pass its exact HTTPS URL as the final argument and open the returned `hosted` link on the same computer. The hosted page must already contain that deck, or select its saved import via its existing URL. The browser may ask for local-network access. The local link works without a cross-origin connection. Keep the pairing links private and out of published assets. They expire after eight hours or when the receiver stops.

**Send to [chat]** writes the reviewed batch to a private file and queues its location in the bound chat. The CLI requests a session resume. **Queued** confirms that Codex accepted the message. When it arrives, read the indicated file, reconcile the submission ID and item revisions with prior work, then act within the original task. Revision requests call for a new proposal. The same submission ID reuses its receipt across reloads and receiver restarts. Local drafts belong to the browser origin, including its port. The receiver reuses its saved port when available. If another process occupies that port, show the returned draft notice and check the originating chat for prior receipts before resubmitting. A paired hosted page keeps its drafts at its stable HTTPS origin. If delivery is unknown, check the originating chat before initiating a different handoff.

## Try the design duel

From the skill directory, run `node scripts/render-deck.mjs examples/after-hours/after-hours.tinder.json after-hours.html`. The standalone file includes both mockups, the interactive device-mix control and verdict exports. All sales data is simulated.
