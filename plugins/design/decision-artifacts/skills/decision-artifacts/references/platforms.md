# Platform routing

Choose the native surface the user requested. Keep the decision spine and evidence model independent of the renderer.

Platform capabilities change. Before relying on live data, storage, access control, or public sharing, check the current platform documentation and the controls visible in the user's account. The constraints below were last checked on 2026-10-08.

## Claude artifact

Use Claude's native artifact capability when available.

- Build one self-contained page.
- Prefer HTML, CSS, SVG, and the platform-supported component runtime.
- Avoid backend assumptions, relative multi-page routes, and unnecessary dependencies.
- Make the page useful at rest before adding controls.
- Use connectors only when the requested artifact genuinely needs live viewer-specific data and the platform supports it.
- A viewer uses their own connector access. Show a clear unavailable or access-required state when a source cannot load; do not present missing data as an empty result.
- Treat personal and shared storage as different data scopes. Test storage only after publication when the platform requires it, and do not place sensitive source material in shared storage without explicit approval.
- Review attached source files before sharing because a shared artifact may expose its conversation attachments.
- Confirm the audience and distinguish a pinned version from a latest version when that choice is available and matters.

### Page constraints

The page runs under a strict content security policy. Load any library from the allowed public CDNs (cdnjs, unpkg, jsDelivr `/npm/`, the Tailwind and jQuery CDNs) and type from Google Fonts, inline all other CSS and JavaScript, and embed images, logos and screenshots as data URIs; external images do not load. The page cannot fetch other origins, so live data comes only through declared connectors. Use in-page anchors for long content, because relative links do not resolve.

### Runtime capabilities

Connector calls and file downloads are declared when the artifact is published, and the page cannot use anything outside that declaration. Declare only what the reader's job needs.

- **Live data.** Name the connector tools the page calls and check the names against the tools the connector actually exposes; a wrong name leaves the section empty for every viewer. Show when each live section last refreshed and offer a refresh control when the data moves during a meeting.
- **Downloads.** The viewer blocks downloads the page starts itself, including `data:` and `blob:` links. Offer a CSV of a table or a PNG of a chart only through the declared downloads capability.
- **Actions.** A control can call a connector tool with side effects, such as filing a ticket or posting a message once a decision is made. It runs as whoever selects it. Build one only when the user asked for it, label the destination and the effect on the control, and show what will be sent before it fires.

### Recording the decision

A decide or track artifact is more useful when the choice stays on the page. When the platform offers storage, record the selected option, who chose it, when, and any condition attached, in shared storage only when the audience should see each other's input, and show the recorded state on the page at rest. When storage is unavailable or the result needs to return to the working session, add an export control that copies the decision and its evidence references as plain text for the next prompt.

### Review loop

Shared artifacts can carry comment threads. People with edit access can send a thread to Claude, which can reply or revise and republish the page. Design for that loop:

- Give each section, row and slide a stable heading or label so a comment can point at it.
- When a revision answers a comment, say on the page or in the version note what changed and why.
- Viewers see each version but cannot change the page; editors republish through Claude. Confirm who should be an editor before sharing.
- Anyone reading through a public link sees no comments and, unless signed in to the same organization, no live sections. If the artifact must work for them, make the at-rest page carry the decision without connectors and say where the live view lives.

### Decks and design canvases

When the reader will consume the decision in a meeting, a Slides template (`/slides` in Claude Code) usually fits better than a scrolling page; read [presentations.md](presentations.md). When the request is a visual mockup of a screen or flow rather than a decision, a Design canvas (`/design`) is the native surface, and this skill supplies only the decision context around it.

Official references: [using Claude artifacts](https://support.claude.com/en/articles/9487310-what-are-artifacts-and-how-do-i-use-them), [publishing and sharing artifacts](https://support.claude.com/en/articles/9547008-publish-and-share-artifacts), and [sharing session output as artifacts from Claude Code](https://code.claude.com/docs/en/artifacts).

## Codex site

Use the Sites capability for a shareable full-page site. Use the visualization capability for an in-conversation preview or dry run, not as a substitute for requested hosting.

- Start with a focused first preview.
- Use the platform's standard components for tabs, sheets, tables, and controls.
- Review content, calculations, labels, and interaction before publishing.
- Save a reviewed version before deployment. Every deployment URL is a production URL.
- Do not deploy until the user has asked for a shareable or published result and the site has been reviewed.
- Sites cannot connect directly to live data at the time of this review. Use a dated snapshot or a separately reviewed refresh workflow, and show the source and last refresh in the site.
- Open the deployed URL in a browser and test it from the intended visitor's access level before sharing. Do not treat the in-app preview as proof of the deployed result.
- Confirm the selected audience before publishing, especially when public access is available.

Official references: [creating and managing ChatGPT Sites](https://help.openai.com/en/articles/20001339) and [ChatGPT Sites guidance](https://openai.com/academy/chatgpt-sites/).

## Self-contained HTML fallback

When no native artifact or site surface is available, create one focused HTML file.

- Keep assets inline or local and portable.
- Do not require a build step unless the requested interaction justifies it.
- State that the file is a local preview, not a hosted URL.
- Open or render it for inspection when the environment supports that.

## Existing product or design system

When the artifact belongs inside an existing product, follow that product's components, tokens, routes, and accessibility conventions. The built-in tastes are fallback directions, not permission to replace a design system.
