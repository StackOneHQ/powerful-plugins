# Evidence in diagrams

Choose the view by the reader's question: dependencies, sequence, states, comparison
or cause. Use an available diagramming skill such as `diagram-explainer` for the smallest useful representation.
Quantitative charts remain with `tufte-viz`; this reference concerns the
claims a diagram makes, not a new rendering system.

For each consequential arrow, identify its source and relationship: a data flow,
dependency, time order and causal effect are different claims. Label conditions,
optional paths, failures and unknowns. An earlier event does not establish causation.
Do not turn a branching flow into a chain to make the layout simpler.

Keep a compact source mapping in the artifact's existing evidence layer. Distinguish
observed behavior, documented design, inference and illustrative scenarios with words
or line styles, not color alone. If sources conflict, name the version represented
and retain the disagreement; missing evidence does not authorize a typical-looking
connection.

Deliver editable source when a diagram is requested, a rendered preview when the
renderer is available, and a short text equivalent. Inspect labels, arrow direction,
conditions and readability at the intended size after rendering. A Mermaid block
is editable source, not proof that it rendered. Keep unknown checks explicit.
