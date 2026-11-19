import json
from types import SimpleNamespace

import pytest
from PIL import Image


@pytest.mark.parametrize("attempt", [
    {"reader": "calendar", "status": "failed"},
    {"reader": "calendar", "status": "needs_evidence_or_review", "result": "calendar/result.json"},
])
def test_agent_does_not_promote_a_previous_images_calendar(tmp_path, monkeypatch, attempt):
    from chart_recover import agent
    image = tmp_path / "new.png"
    Image.new("RGB", (80, 80), "white").save(image)
    folder = tmp_path / "output/readers/calendar"
    folder.mkdir(parents=True)
    (folder / "result.json").write_text(json.dumps({"image_sha256": "previous-image"}))
    monkeypatch.setattr(agent, "recover", lambda *a, **k: dict(
        image_sha256="current-image", status="needs_evidence_or_review",
        calibrated_candidates=0, attempts=[attempt]))
    monkeypatch.setattr(agent, "propose_calendar", lambda *a: pytest.fail("stale calendar promoted"))
    monkeypatch.setattr("chart_recover.comparison_totals.recover_comparison", lambda *a: dict(
        status="needs_evidence_or_review", evidence_strength="none"))
    result = agent.investigate_image(image, output=tmp_path / "output")
    assert result["conditional_candidates"] == 0


def test_curve_pixel_limit_is_checked_before_decode(monkeypatch):
    from chart_recover import external_evidence

    class Oversized:
        width = height = 10000
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def convert(self, *args): pytest.fail("oversized image decoded")

    monkeypatch.setattr(external_evidence.Image, "open", lambda *a: Oversized())
    with pytest.raises(ValueError, match="30 megapixels"):
        external_evidence.trace_curve("oversized.png")


def test_tesseract_output_uses_utf8_independently_of_locale(tmp_path, monkeypatch):
    from chart_recover import ocr
    image = tmp_path / "label.png"
    Image.new("RGB", (40, 20), "white").save(image)
    monkeypatch.setattr(ocr.shutil, "which", lambda name: "tesseract")
    def run(*args, **kwargs):
        assert kwargs.get("encoding") == "utf-8"
        kwargs['stdout'].write("level\tblock_num\tpar_num\tline_num\tleft\ttop\twidth\theight\tconf\ttext\n5\t1\t1\t1\t1\t1\t20\t10\t99\t€100\n".encode('utf-8'))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(ocr.subprocess, "run", run)
    assert ocr.read_text(image)["tokens"][0]["text"] == "€100"
