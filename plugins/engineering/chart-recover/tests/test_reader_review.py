"""Regression cases for review findings in calendar and public-source readers."""
from datetime import date, timedelta

from PIL import Image
import pytest

from chart_recover.calendar_recovery import correspondence
from test_calendar import context, token


def matching_calendar():
    calendar, geometry = context()
    calendar['observations'] = [dict(currency='$')]
    calendar['consensus_tokens'] += [
        token('Daily', 60, 40, 35), token('revenue', 100, 40, 60),
        token('July', 210, 40, 35), token('2026', 250, 40, 35),
        token('Daily', 295, 375, 35), token('revenue', 335, 375, 60),
        token('Jul', 35, 320, 27), token('1', 57, 320, 7),
        token('Jul', 825, 320, 24), token('31', 852, 320, 14),
    ]
    return calendar, geometry


def test_daily_sales_is_a_metric_contradiction_even_with_assumption():
    calendar, geometry = context()
    calendar['consensus_tokens'] += [token('Daily', 60, 40, 35), token('sales', 100, 40, 60)]
    result = correspondence(calendar, geometry, dict(assume_shared_daily_revenue=True, assume_full_month=True))
    assert result['status'] == 'needs_review'
    assert any('heading contradicts' in reason for reason in result['reasons'])


@pytest.mark.parametrize('text,split', [('Jun', True), ('Jun1', False)])
def test_wrong_month_endpoint_is_preserved_despite_full_month_assumption(text, split):
    calendar, geometry = context()
    calendar['consensus_tokens'] += [token(text, 35, 320, 27)]
    if split:
        calendar['consensus_tokens'].append(token('1', 57, 320, 7))
    result = correspondence(calendar, geometry, dict(assume_shared_daily_revenue=True, assume_full_month=True))
    assert result['status'] == 'needs_review'
    assert result['date_ticks'][0]['month'] == 6
    assert any('period or endpoint' in reason for reason in result['reasons'])


def test_matching_metric_headings_do_not_supply_missing_currency():
    calendar, geometry = matching_calendar()
    result = correspondence(calendar, geometry, {})
    assert result['status'] == 'needs_review'
    assert any('currency' in reason for reason in result['reasons'])
    assumed = correspondence(calendar, geometry, dict(assume_shared_daily_revenue=True, assume_full_month=True))
    assert assumed['status'] == 'matched'
    assert any('same currency' in assumption for assumption in assumed['assumptions'])


@pytest.mark.parametrize('assume', [False, True])
def test_euro_curve_cannot_use_dollar_calendar_values(assume):
    calendar, geometry = matching_calendar()
    calendar['consensus_tokens'].append(token('€', 175, 40))
    result = correspondence(calendar, geometry, dict(assume_shared_daily_revenue=assume))
    assert result['status'] == 'needs_review'
    assert any('currency' in reason for reason in result['reasons'])


def test_date_axis_retains_unmatched_visible_month_day():
    from chart_recover.external_evidence import date_axis
    geometry = dict(size=[700, 400], roi=[50, 100, 650, 300],
                    series=[dict(points=[dict(x=50, y=300), dict(x=650, y=100)])])
    periods = [(date(2026, 9, 1) + timedelta(days=i)).isoformat() for i in range(30)]
    tokens = []
    for month, day, x in [('Aug', 28, 50), ('Sep', 7, 170), ('Sep', 12, 270), ('Sep', 17, 370)]:
        tokens += [token(month, x-18, 320, 20), token(str(day), x+4, 320, 14)]
    result = date_axis(tokens, geometry, periods)
    assert result['status'] == 'needs_review'
    assert result['unmatched_labels'][0]['month_day'] == '08-28'
    assert len(result['labels']) == 4


def test_numeric_ticks_do_not_merge_vertically_separate_panels():
    from chart_recover.tick_recovery import bind_ticks
    ys = [80, 120, 160, 340, 380, 420]
    labels = [token(f'${1000-y}', 515, y-8, 40, 16) for y in ys]
    lines = [dict(y=y, left=70, right=500) for y in ys]
    result = bind_ticks(labels, lines, (600, 500), 'synthetic panels')
    assert not result['axes']
    assert any('panel' in rejected['reason'] for rejected in result['rejected'])


def empty_external(monkeypatch, size):
    import chart_recover.external_evidence as external
    geometry = dict(size=list(size), roi=[0, 0, *size], series=[], quality_issues=[])
    monkeypatch.setattr(external, 'trace_curve', lambda image: (geometry, []))
    monkeypatch.setattr(external, 'overlay', lambda *args: None)
    return external, dict(source='https://example.com/profile', source_sha256='synthetic', entity='Lumen', tables=[])


def test_current_external_abstention_removes_previous_daily_csv(tmp_path, monkeypatch):
    external, profile = empty_external(monkeypatch, (80, 60))
    monkeypatch.setattr(external, 'read_text', lambda *args, **kwargs: dict(tokens=[]))
    image = tmp_path/'chart.png'
    Image.new('RGB', (80, 60), 'white').save(image)
    output = tmp_path/'result'
    output.mkdir()
    (output/'daily.csv').write_text('stale estimates', encoding='utf-8')
    result = external.recover_external(image, profile, output)
    assert result['status'] == 'needs_evidence_or_review'
    assert not (output/'daily.csv').exists()


def test_external_ocr_scales_stay_distinct_and_bounded_for_large_images(tmp_path, monkeypatch):
    external, profile = empty_external(monkeypatch, (3000, 2000))
    image = tmp_path/'chart.png'
    Image.new('RGB', (3000, 2000), 'white').save(image)
    scales = []
    def read(image, *, scale):
        assert round(3000*scale)*round(2000*scale) <= 30_000_000
        scales.append(scale)
        return dict(tokens=[])
    monkeypatch.setattr(external, 'read_text', read)
    external.recover_external(image, profile, tmp_path/'result')
    assert len(scales) == 2 and scales[0] < scales[1]


def test_calendar_full_image_and_weekday_ocr_use_distinct_bounded_scales(tmp_path, monkeypatch):
    import chart_recover.calendar_vision as vision
    image = tmp_path/'chart.png'
    Image.new('RGB', (3000, 2500), 'white').save(image)
    calls = []
    def read(path, *, scale, region=None, **kwargs):
        width, height = (region[2]-region[0], region[3]-region[1]) if region else (3000, 2500)
        assert round(width*scale)*round(height*scale) <= 30_000_000
        calls.append(scale)
        return dict(tokens=[])
    monkeypatch.setattr(vision, 'read_text', read)
    monkeypatch.setattr(vision, 'locate_calendar', lambda *args: [])
    monkeypatch.setattr(vision, 'weekday_strip_proposals', lambda *args: [[0, 0, 3000, 1000]])
    vision.read_calendar(image, tmp_path/'result')
    assert len(calls) == 4 and calls[0] < calls[1] and calls[2] < calls[3]


def test_calendar_amount_atlas_uses_distinct_bounded_scales(tmp_path, monkeypatch):
    import chart_recover.calendar_vision as vision
    image = tmp_path/'chart.png'
    Image.new('RGB', (3000, 2500), 'white').save(image)
    layout = dict(year=2026, month=7, days=31, offset=2, glyph_height=120,
                  weekday=dict(step=400, centers=[250+i*400 for i in range(7)]),
                  row_centers=[400+i*400 for i in range(5)])
    atlas_scales = []
    def read(path, *, scale, **kwargs):
        with Image.open(path) as im:
            assert round(im.width*scale)*round(im.height*scale) <= 30_000_000
        if path != image:
            atlas_scales.append(scale)
        return dict(tokens=[])
    monkeypatch.setattr(vision, 'read_text', read)
    monkeypatch.setattr(vision, 'locate_calendar', lambda *args: [layout])
    result = vision.read_calendar(image, tmp_path/'result')
    assert result['status'] == 'needs_review'
    assert len(atlas_scales) == 2 and atlas_scales[0] < atlas_scales[1]


@pytest.mark.parametrize('post_text', [42, True, ['Lumen'], {'name': 'Lumen'}])
def test_malformed_post_text_does_not_crash_catalog_discovery(tmp_path, monkeypatch, post_text):
    import chart_recover.evidence_discovery as discovery
    image = tmp_path/'chart.png'
    Image.new('RGB', (80, 60), 'white').save(image)
    resolver = discovery.EvidenceDiscovery(tmp_path/'catalog')
    monkeypatch.setattr(resolver, 'catalog', lambda: dict(source='public catalog', source_sha256='synthetic',
                        entries=[dict(name='Lumen', url='https://trustmrr.com/startup/lumen.md', locations=[])]))
    monkeypatch.setattr(discovery, 'read_text', lambda *args, **kwargs: dict(tokens=[]))
    result = resolver.discover(image, dict(post_text=post_text), tmp_path/'result')
    assert result['status'] == 'no_candidate' and result['candidates'] == []
