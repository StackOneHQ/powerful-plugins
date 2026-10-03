# Diagram explainer

Create editable, source-grounded diagrams for systems, sequences, state machines
and causal mechanisms. The skill delivers a preview, editable source, a short
text equivalent and evidence for consequential relationships.

## Install

```bash
/plugin marketplace add StackOneHQ/powerful-plugins
/plugin install diagram-explainer@powerful-plugins

codex plugin marketplace add StackOneHQ/powerful-plugins
codex plugin add diagram-explainer@powerful-plugins
```

## Use

In Claude Code: `/diagram-explainer:diagram-explainer <request and source>`.
In Codex: `$diagram-explainer:diagram-explainer`.

Example requests:

- "Diagram this request flow from the code. Include the failure path and cite the relevant files."
- "Turn this lifecycle document into an editable state diagram. Mark transitions that are not specified."
- "Explain how this mechanism works with a diagram and one concrete example."

The plugin has one skill, `diagram-explainer`, and no hooks, agents or MCP servers.
It uses available local rendering tools and installs no dependencies automatically.
Mermaid, SVG and Excalidraw are supported authoring choices; actual rendering or
editor validation depends on the tools available in the host. Missing verification
is reported rather than treated as a pass. External rendering and sharing require
authorization; the plugin sends no telemetry.

Use `tufte-viz` for quantitative charts, `decision-artifacts` for an interactive
page around the diagram, or `animation-studio` for motion and educational videos.
