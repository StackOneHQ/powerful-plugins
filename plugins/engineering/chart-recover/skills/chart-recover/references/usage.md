# Commands and evidence

Resolve the bundled `scripts/run.py` from the skill directory and invoke it with the configured Python environment. The examples below abbreviate that command as `chart-recover`; it is also the console entry point when the Python package is installed.

| Command | Purpose |
|---|---|
| `agent IMAGE --out NEW_FOLDER` | Try readers and conditional hypotheses, preserving failures and evidence |
| `agent IMAGE --strict-only --out NEW_FOLDER` | Suppress inferred correspondence and conditional source retrieval |
| `analyze IMAGE --config CONFIG --out NEW_FOLDER` | Geometry extraction with explicit reviewed anchors or constraints |
| `auto IMAGE --scale linear --out NEW_FOLDER` | Read a bar card with a supplied linear-scale assumption |
| `ticks IMAGE --out NEW_FOLDER` | Read a partially labeled numeric axis and its local curve |
| `recover IMAGE --out NEW_FOLDER` | Run all automatic image readers, keeping every attempt |
| `calendar IMAGE --out NEW_FOLDER` | Inspect calendar amounts and corresponding curve evidence |
| `recover-batch MANIFEST --out NEW_FOLDER` | Run automatic readers for each collected image |
| `agent-batch MANIFEST --out NEW_FOLDER` | Run readers and conditional hypotheses for each collected image |
| `investigate IMAGE --config CONFIG --out NEW_FOLDER` | Apply bounded evidence rounds and optional retrieval |
| `batch MANIFEST --out NEW_FOLDER` | Run evidence-round investigations for a collected manifest |
| `serve --port 8765` | Start the loopback-only workbench |
| `collect --public --url URL --out NEW_FOLDER` | Collect an explicitly requested public X post and exposed media |
| `collect --query QUERY --pages 1 --out NEW_FOLDER` | Search through authorized X API access; needs `X_BEARER_TOKEN` |
| `discover --limit 10 --agent --out NEW_FOLDER` | Bounded public-directory collection and analysis, when the user requested discovery |
| `agent IMAGE --profile-url URL --profile-snapshot FILE --out NEW_FOLDER` | Test an offline saved profile against the image |
| `generate --kind line --seed 42 --out NEW_FOLDER` | Generate a synthetic chart and separate private truth |
| `benchmark --seed 600000 --per-kind 2 --out NEW_FOLDER` | Run the conditional eight-family geometry protocol |

Use `--discover-evidence` only when public source discovery is requested. A cache passed with `--evidence-cache` avoids evidence-provider requests; it does not make the separate public-post collection command offline. `--profile-snapshot` requires the corresponding public profile URL for provenance. `agent-batch` and `recover-batch` accept a collected JSONL manifest. All output paths should point to a new user-selected directory.

## Standalone evaluations

From the plugin root, run `PYTHONPATH=skills/chart-recover/scripts .venv/bin/python -m chart_recover.MODULE --out NEW_FOLDER --seed SEED`. On platforms without that environment-assignment syntax, add the scripts folder to the chosen Python environment's import path first. Every module accepts `--help`.

| Module | Protocol |
|---|---|
| `aggregate_benchmark` | Supplied kind, linear scale, observation membership and period totals |
| `automatic_benchmark` | Bar-card OCR with an explicitly supplied linear scale |
| `calendar_benchmark` | Calendar/curve evidence with an explicit full-month daily-sampling assumption |
| `comparison_benchmark` | Two period totals under a shared-axis hypothesis |
| `curve_benchmark` | External evidence across linear, smooth and step renderings |
| `evidence_discovery_benchmark` | Offline fabricated catalog and full-agent source discovery |
| `external_benchmark` | Linked fabricated daily profile with withheld amounts |
| `first_customer_benchmark` | Caption and headline hypotheses with withheld history |
| `hypothesis_benchmark` | Conditional calendar correspondence |
| `jpeg_benchmark` | Compression and color stress cases |
| `sparse_benchmark` | Sparse line and external-date alignment |
| `step_benchmark` | Paired baseline/revised step readers from a frozen source package |
| `tick_benchmark` | Partially visible numeric-axis labels |

`step_benchmark` also requires `--baseline PATH_TO_REVIEWED_EXTERNAL_EVIDENCE_PY`. This deliberately executes the selected local Python reader; use a trusted, reviewed file. It snapshots the local dependency modules, generator and scorer, and removes truth from each image folder while readers run. This is a reproducible trusted-code comparison, not a sandbox for hostile readers. The baseline and revised readers use the same frozen dependency set and the environment's installed third-party packages.

Example: `PYTHONPATH=skills/chart-recover/scripts .venv/bin/python -m chart_recover.evidence_discovery_benchmark --out NEW_FOLDER --seed 650000`.

## Calibration

Two independently placed absolute anchors can determine a linear scale. A known zero and one absolute anchor can also suffice. With unknown scale, linear and logarithmic hypotheses may both fit. Explicit source correspondence is a caller assertion, not verification supplied by the URL.

```json
{
  "kind": "line",
  "scale": "linear",
  "anchors": [
    {"point_index": 0, "value": 100, "source": "Reviewed first-point disclosure", "matched": true},
    {"point_index": -1, "value": 900, "source": "Reviewed final-point disclosure", "matched": true}
  ]
}
```

For a reviewed zero baseline, explicitly select `"scale": "linear"` and supply, for example, `"baseline": {"pixel": 300, "value": 0, "source": "Reviewed visible zero tick", "matched": true}`. Replace the fictional pixel coordinate with the measured zero location; an unlabeled plot edge is insufficient.

The JSON above is a fictional formatting example. Never apply its values to the user's chart. Rounded disclosures should be intervals, and captions need entity, metric, currency and time correspondence. Growth ratios alone cannot establish an absolute unit.

Calendar-to-curve calibration requires matching visible daily-revenue headings and currency units. Endpoint labels establish a visible period but do not prove sampling: `assume_full_month` must explicitly assert one equally spaced observation per day across the full month. When units or headings are missing, `assume_shared_daily_revenue` records an explicit caller assumption. Visible metric, currency or date contradictions still reject the match.

Period totals require the actual observation count and membership, not an arbitrary number of samples along a continuous stroke. One total may yield only ranges. The two-comparison reader assumes both curves use a shared linear axis and compatible daily counts; an exact total fit does not validate those assumptions.

## Research basis

Separate extraction from calibration and evidence validation. [ChartOCR](https://openaccess.thecvf.com/content/WACV2021/papers/Luo_ChartOCR_Data_Extraction_From_Charts_Images_via_a_Deep_Hybrid_WACV_2021_paper.pdf) studies extraction from chart images; [DePlot](https://arxiv.org/abs/2212.10505) translates plots to tables; [WebPlotDigitizer](https://automeris.io/docs/digitize/) documents explicit calibration and tracing. None supplies missing absolute information merely because a curve was recognized. A neural prior can estimate plausible scale, but that remains a guess unless supported by evidence.
