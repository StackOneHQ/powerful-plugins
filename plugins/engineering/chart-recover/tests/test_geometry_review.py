"""Regression controls for geometry and OCR review findings."""
from io import BytesIO
import json

import numpy as np
from PIL import Image, ImageDraw
import pytest

from chart_recover.autopilot import bind_bar_labels
from chart_recover.collect import save_posts
from chart_recover.comparison_totals import propose_comparison
from chart_recover.curve_grid import fit_shared_grid
from chart_recover.first_customer import caption_claim, propose_first_customer
from chart_recover.layout import detect_bars
from chart_recover.vision import extract


def token(text, x, y, width=40, height=12):
    return dict(text=text, box=[x, y, width, height], confidence=99)


@pytest.mark.parametrize('tops', [[90, 90, 90], [90, 92, 94]])
def test_equal_or_near_equal_bars_remain_label_bindable_candidates(tmp_path, tops):
    image = Image.new('RGB', (320, 270), 'white')
    draw = ImageDraw.Draw(image)
    for x, top in zip((30, 130, 230), tops):
        draw.rectangle([x, top, x+40, 190], fill='#7788ee')
    path = tmp_path/'equal-bars.png'
    image.save(path)
    layout = detect_bars(path)
    assert layout['status'] == 'unique_candidate'
    candidate = layout['candidates'][0]
    assert len(candidate['points']) == 3
    assert np.isfinite(candidate['shape_normalized']).all()
    tokens = [token('Revenue', 30, 55)]
    for x, month in zip((30, 130, 230), ('Jan', 'Feb', 'Mar')):
        tokens += [token(month, x, 201), token('$100', x, 221)]
    bound = bind_bar_labels(candidate, tokens, 'synthetic label fixture', layout['size'])
    assert len(bound['anchors']) == 3


def test_dense_bar_card_preserves_one_pixel_background_gaps(tmp_path):
    image = Image.new('RGB', (340, 240), 'white')
    draw = ImageDraw.Draw(image)
    tops = [60 + (i*17) % 100 for i in range(30)]
    for i, top in enumerate(tops):
        x = 25 + 9*i
        draw.rectangle([x, top, x+7, 200], fill='#7788ee')
    path = tmp_path/'dense-bars.png'
    image.save(path)
    layout = detect_bars(path)
    assert layout['status'] == 'unique_candidate'
    points = layout['candidates'][0]['points']
    assert len(points) == len(tops)
    assert [point['y'] for point in points] == tops


@pytest.mark.parametrize('kind', ['bar', 'barh', 'grouped_bar', 'stacked_bar', 'scatter'])
def test_explicit_mark_kind_retains_a_single_observation(tmp_path, kind):
    image = Image.new('RGB', (180, 160), 'white')
    draw = ImageDraw.Draw(image)
    if kind == 'scatter':
        draw.ellipse([70, 70, 82, 82], fill='#4466cc')
    else:
        draw.rectangle([55, 50, 110, 130], fill='#4466cc')
    path = tmp_path/'single-mark.png'
    image.save(path)
    result = extract(path, kind=kind, color=[68, 102, 204])
    assert result['status'] == 'extracted'
    assert len(result['series']) == 1
    assert len(result['series'][0]['points']) == 1
    assert result['series'][0]['shape_normalized'] == [0.]


@pytest.mark.parametrize('kind', ['line', 'area', 'stacked_area'])
def test_endpoint_span_cannot_hide_a_large_internal_trace_gap(tmp_path, kind):
    image = Image.new('RGB', (600, 240), 'white')
    draw = ImageDraw.Draw(image)
    for left, right in ((50, 235), (365, 550)):
        if kind == 'line':
            draw.line([(left, 100), (right, 100)], fill='#4466cc', width=3)
        else:
            draw.rectangle([left, 100, right, 190], fill='#4466cc')
    path = tmp_path/'interrupted-trace.png'
    image.save(path)
    result = extract(path, kind=kind, roi=[45, 70, 555, 210], color=[68, 102, 204])
    assert result['series']
    assert result['status'] == 'needs_review'
    assert any(issue.get('largest_unobserved_gap', 0) >= 129 for issue in result['quality_issues'])


def test_coarse_requested_sampling_is_not_an_unobserved_pixel_gap(tmp_path):
    image = Image.new('RGB', (600, 240), 'white')
    ImageDraw.Draw(image).line([(50, 100), (550, 150)], fill='#4466cc', width=3)
    path = tmp_path/'complete-trace.png'
    image.save(path)
    result = extract(path, kind='line', roi=[45, 70, 555, 210], samples=2, color=[68, 102, 204])
    assert result['status'] == 'extracted'
    assert not result['quality_issues']


@pytest.mark.parametrize('size, accepted', [((6000, 5001), False), ((100, 80), True)])
def test_downloaded_public_images_are_dimension_checked_before_persisting(tmp_path, monkeypatch, size, accepted):
    encoded = BytesIO()
    Image.new('1', size).save(encoded, format='PNG')
    content = encoded.getvalue()
    assert len(content) < 20_000_000

    class Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield content

        def close(self):
            pass

    monkeypatch.setattr('chart_recover.collect.requests.get', lambda *args, **kwargs: Response())
    post = dict(id='123', media=[dict(type='photo', url='https://pbs.twimg.com/media/synthetic.png')])
    save_posts([post], tmp_path)
    saved = json.loads((tmp_path/'posts.jsonl').read_text(encoding='utf-8'))
    assert bool(saved['images']) is accepted
    assert (tmp_path/'123-0.image').exists() is accepted
    if not accepted:
        assert saved['errors']


@pytest.mark.parametrize('caption', [
    'Got my first paying customer, but the chart is for our other company.',
    'Got my first paying customer. The chart is for Acme.',
    'Got my first paying customer 10 days after I launched a new startup, although this revenue belongs to a different product.',
])
def test_contradictory_caption_scope_never_proposes_zero_history(caption):
    assert caption_claim(caption, 'https://x.com/fixture/status/123')['status'] == 'unsupported'


def test_nonfinite_headline_abstains_before_anchor_construction():
    xs = np.arange(50., 951., 10.)
    ys = np.interp(xs, [50, 850, 950], [450, 450, 150])
    geometry = dict(roi=[49, 148, 952, 453], quality_issues=[], series=[dict(
        id='series_0', points=[dict(x=float(x), y=float(y)) for x, y in zip(xs, ys)])])
    tokens = [token('MRR', 50, 20), token('$'+'9'*400, 50, 65)]
    result = propose_first_customer(geometry, tokens, 'Got my first paying customer!', 'https://x.com/fixture/status/123')
    assert not result['recovery']
    assert result['reasons'] == ['Headline amount must be finite.']


def test_nonfinite_period_total_abstains_before_grid_or_calibration():
    candidates = [dict(trace_mode='thin_strong_stroke_center', x=[40, 500], y=ys)
                  for ys in ([150, 350], [220, 400])]
    tokens = [token('revenue', 40, 0), token('$'+'9'*400, 40, 30), token('vs.', 0, 60),
              token('$100', 40, 60), token('last', 100, 60), token('period', 160, 60)]
    result = propose_comparison(candidates, tokens, 'synthetic totals fixture', [560, 500])
    assert not result['recovery']
    assert result['reasons'] == ['Monetary totals must be finite.']


def test_daily_grid_reports_local_diagnostic_scope_without_global_uniqueness():
    rng = np.random.default_rng(19)
    knots = np.linspace(40, 1000, 28)
    x = np.arange(39, 1002)
    candidates = [dict(x=x.tolist(), y=np.interp(x, knots, rng.uniform(130, 570, 28)).tolist())
                  for _ in range(2)]
    result = fit_shared_grid(candidates, 39, 1001, 28)
    assert result['status'] == 'supported'
    assert result['diagnostic_scope'] == 'proposed_count_and_neighbors_within_two'
    assert result['global_grid_uniqueness_established'] is False
    assert {trial['count'] for trial in result['alternative_grids']} == {26, 27, 29, 30}
