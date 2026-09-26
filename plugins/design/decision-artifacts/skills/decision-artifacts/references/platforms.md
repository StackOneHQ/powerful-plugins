# Platform routing

Choose the native surface the user requested. Keep the decision spine and evidence model independent of the renderer.

Platform capabilities change. Before relying on live data, storage, access control, or public sharing, check the current platform documentation and the controls visible in the user's account. The constraints below were last checked on 2026-09-21.

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

Official references: [using Claude artifacts](https://support.claude.com/en/articles/9487310-what-are-artifacts-and-how-do-i-use-them) and [publishing and sharing artifacts](https://support.claude.com/en/articles/9547008-publish-and-share-artifacts).

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
