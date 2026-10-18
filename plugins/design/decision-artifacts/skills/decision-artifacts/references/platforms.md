# Platform routing

Read only the section for your output surface. Keep the decision spine and evidence model independent of the renderer. Platform capabilities change; these notes were last checked on 2026-10-18.

## Claude artifact

The Artifact tool, `artifact-design` and `artifact-capabilities` own the page contract (format, title, theming, CSP, runtime capabilities). Follow them; this section only adds what decision pages need.

- **Answers.** Declare the `db` capability and store one document per decision id in a `decisions` collection, `{choice, note, updated_at}`. Read it back with ArtifactData `list` before asking or acting. Persistence is untested until a reader's answer has been read back; say so at hand-off. When several people answer, keep one document per decision and viewer, with `db` rules so each writes only their own; answers under `data/users/` are private even from the owner, so Claude can't read them.
- **Updates.** Republish the same file path to keep the URL. After compaction or a reset, pass the artifact `url` explicitly; a publish by path alone can create a second page.
- **Hooks.** When a file-edit hook is configured, edit the file and then publish; a publish that carries `edits` is refused.
- **Media.** 15 MB per file, 64 MiB per publish, 256 MiB per version. Transcode first, spread large sets over several publishes or use the asset store, and give changed media a new file name so caches don't serve the old one.
- **Access.** Connectors run with the viewer's own access; show an unavailable state rather than an empty result when a source can't load. Review attached files before sharing. Confirm the audience before widening access.

### Checking the page

- The publish wrapper adds a charset meta and `[hidden] { display: none !important; }`. A local file without them shows bugs that aren't live and hides ones that are, so put both in the page itself.
- Browser extensions usually can't see or click inside the published artifact frame. Check the local file with a real browser (Playwright or similar) using real clicks and keys at desktop and 390 px, and say that the live frame wasn't exercised.
- An animated chart that renders empty in an automated tab may be animation throttling, not a bug; check before reporting it.
- Parse every inline script and data block before publishing. A syntax error leaves the tables empty.

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
