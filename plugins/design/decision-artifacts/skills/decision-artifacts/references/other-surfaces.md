# Other surfaces

Read only the section for your output surface. Notes last checked on 2026-10-18.

## Codex site

Use the Sites capability for a shareable full-page site; the visualization capability is for an in-conversation preview.

- Start with a focused first preview and use the platform's standard components.
- Review content, calculations, labels and interaction before publishing. Every deployment URL is a production URL.
- Deploy only when the user asked for a shareable result and it has been reviewed.
- Check whether the site can load live data for its viewers; where it can't, use a dated snapshot and show its source and refresh time.
- If the site has no storage the agent can read, answers come back through "Copy my answers": ask the reader to paste them, and don't act until they do.
- Test the deployed URL from the intended visitor's access level before sharing; the in-app preview doesn't prove the deployed result.

Official references: [creating and managing ChatGPT Sites](https://help.openai.com/en/articles/20001339) and [ChatGPT Sites guidance](https://openai.com/academy/chatgpt-sites/).

## Self-contained HTML

With no artifact or site surface, write one focused HTML file with inline assets, no build step unless the interaction needs one, and say it's a local preview, not a hosted URL. Answers fall back to "Copy my answers": ask the reader to paste them back, and don't act until they do.

## Existing product or design system

Inside an existing product, follow its components, tokens, routes and accessibility conventions. The tastes are fallbacks, not permission to replace a design system.
