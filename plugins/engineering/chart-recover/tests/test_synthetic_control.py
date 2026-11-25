import json
from pathlib import Path
import numpy as np
from chart_recover.pipeline import analyze


def test_hidden_interior_values_from_two_disclosed_endpoints(tmp_path):
    root = Path(__file__).resolve().parent.parent
    folder = root / "skills/chart-recover/scripts/chart_recover/assets/examples/line"
    config = json.loads((folder / "config.json").read_text())
    result = analyze(folder / "chart.png", config, tmp_path)
    truth = json.loads((root / "tests/fixtures/line/truth.json").read_text())
    points = truth["series"][0]["points"]
    trace = result["geometry"]["series"][0]["points"]
    reference = np.array([point["value"] for point in points])
    estimated = np.interp([point["x"] for point in points], [point["x"] for point in trace], result["recovery"][0]["values"])
    assert len(config["anchors"]) == 2
    assert len(reference[1:-1]) >= 6
    assert np.mean(abs(estimated[1:-1] - reference[1:-1])) / np.ptp(reference) < .02
