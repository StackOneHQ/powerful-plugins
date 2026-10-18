# Platform routing

This file covers Claude artifacts. For a Codex site, a local HTML file or an existing product, read [other-surfaces.md](other-surfaces.md) instead. Keep the decision spine and evidence model independent of the renderer. Platform capabilities change; these notes were last checked on 2026-10-18.

## Claude artifact

The Artifact tool, `artifact-design` and `artifact-capabilities` own the page contract; this section adds what decision pages need.

- **Answers.** Declare the `db` capability and store one document per decision id in a `decisions` collection, `{choice, note, updated_at}`. Read it back with ArtifactData `list` before asking or acting. Until the test answer below has been read back, say persistence is untested. When several people answer, keep one document per decision and viewer with `db` rules so each writes only their own; act only on your user's answers unless told otherwise, and say whose you read. Everyone who can open the page can read shared answers; answers under `data/users/` are private even from the owner, so Claude can't read them.
- **Updates.** Republish the same file path to keep the URL. After compaction or a reset, pass the artifact `url` explicitly; a publish by path alone can create a second page.
- **Hooks.** When a file-edit hook is configured, edit the file and then publish; a publish that carries `edits` is refused.
- **Media.** 15 MB per file, 64 MiB per publish, 256 MiB per version. Transcode first, spread large sets over several publishes or use the asset store, and give changed media a new file name so caches don't serve the old one.
- **Access.** Connectors run with the viewer's own access; show an unavailable state rather than an empty result when a source can't load. Review attached files before sharing. Confirm the audience before widening access.

### Checking the page

- Look once before publishing (a preview, or one screenshot of the local file), fix what it shows, and publish; no screenshot-and-probe loop.
- After publishing, save a test answer with ArtifactData, read it back, then delete it.
- The publish skeleton adds the charset meta. Keep `[hidden] { display: none !important; }` in the page's own style so a local look matches the live page.
- Parse every inline script and data block before publishing; a syntax error leaves the tables empty.
- Browser extensions usually can't reach inside the artifact frame. When a full click-through is asked for, run it on the local file in a real browser at desktop and 320 px, and say the live frame wasn't exercised. An animated chart that renders empty there may be throttled, not broken.
