# Commands and evidence

Resolve the bundled `scripts/run.py` from the skill directory and invoke it with the configured Python environment. The examples below abbreviate that command as `chart-recover`; it is also the console entry point when the Python package is installed.

| Command | Purpose |
|---|---|
| `agent IMAGE --out NEW_FOLDER` | Try readers and conditional hypotheses, preserving failures and evidence |
| `agent IMAGE --strict-only --out NEW_FOLDER` | Suppress inferred correspondence and conditional source retrieval |
| `analyze IMAGE --config CONFIG --out NEW_FOLDER` | Geometry extraction with explicit reviewed anchors or constraints |
| `auto IMAGE --scale linear --out NEW_FOLDER` | Read a bar card with a supplied linear-scale assumption |
| `ticks IMAGE --out NEW_FOLDER` | Read a partially labeled numeric axis and its local curve |
| `collect --public --url URL --out NEW_FOLDER` | Collect an explicitly requested public X post and exposed media |
| `collect --query QUERY --pages 1 --out NEW_FOLDER` | Search through authorized X API access; needs `X_BEARER_TOKEN` |
| `discover --limit 10 --agent --out NEW_FOLDER` | Bounded public-directory collection and analysis, when the user requested discovery |
| `agent IMAGE --profile-url URL --profile-snapshot FILE --out NEW_FOLDER` | Test an offline saved profile against the image |
| `generate --kind line --seed 42 --out NEW_FOLDER` | Generate a synthetic chart and separate private truth |
| `benchmark --seed 600000 --per-kind 2 --out NEW_FOLDER` | Run the conditional eight-family geometry protocol |

Use `--discover-evidence` only when public source discovery is requested. A cache passed with `--evidence-cache` avoids evidence-provider requests; it does not make the separate public-post collection command offline. `--profile-snapshot` requires the corresponding public profile URL for provenance. `agent-batch` and `recover-batch` accept a collected JSONL manifest. All output paths should point to a new user-selected directory.

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

The JSON above is a fictional formatting example. Never apply its values to the user's chart. Rounded disclosures should be intervals, and captions need entity, metric, currency and time correspondence. Growth ratios alone cannot establish an absolute unit.

Period totals require the actual observation count and membership, not an arbitrary number of samples along a continuous stroke. One total may yield only ranges. The two-comparison reader assumes both curves use a shared linear axis and compatible daily counts; an exact total fit does not validate those assumptions.

## Research basis

Separate extraction from calibration and evidence validation. [ChartOCR](https://openaccess.thecvf.com/content/WACV2021/papers/Luo_ChartOCR_Data_Extraction_From_Charts_Images_via_a_Deep_Hybrid_WACV_2021_paper.pdf) studies extraction from chart images; [DePlot](https://arxiv.org/abs/2212.10505) translates plots to tables; [WebPlotDigitizer](https://automeris.io/docs/digitize/) documents explicit calibration and tracing. None supplies missing absolute information merely because a curve was recognized. A neural prior can estimate plausible scale, but that remains a guess unless supported by evidence.
