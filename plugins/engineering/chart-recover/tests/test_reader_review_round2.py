"""Regression coverage for the second queued reader review."""
import csv
import json
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw
import pytest
import requests

from test_autopilot import card, token, tokens
from test_reader_review import matching_calendar


def test_calendar_endpoints_do_not_prove_daily_sampling():
    from chart_recover.calendar_recovery import correspondence
    calendar, geometry = matching_calendar()
    calendar['consensus_tokens'].append(token('$', 175, 40))
    result = correspondence(calendar, geometry, {})
    assert result['status'] == 'needs_review' and result['full_period_from_image']
    assert any('daily' in reason for reason in result['reasons'])
    assumed = correspondence(calendar, geometry, dict(assume_full_month=True))
    assert assumed['status'] == 'matched' and assumed['assumptions']


def test_calendar_abstention_csv_keeps_dates_unassigned(tmp_path, monkeypatch):
    import chart_recover.calendar_recovery as recovery
    image = tmp_path/'chart.png'
    Image.new('RGB', (80, 60)).save(image)
    calendar = dict(status='needs_review', layout=dict(year=2026, month=7, days=31), observations=[])
    geometry = dict(roi=[0, 0, 80, 60], series=[dict(points=[dict(x=5, y=10)])], quality_issues=[])
    monkeypatch.setattr(recovery, 'read_calendar', lambda *args: calendar)
    monkeypatch.setattr(recovery, 'detect_curves', lambda *args: (geometry, []))
    monkeypatch.setattr(recovery, 'overlay', lambda *args: None)
    recovery.analyze_calendar(image, output=tmp_path/'out')
    with (tmp_path/'out/data.csv').open(encoding='utf-8') as file:
        rows = list(csv.DictReader(file))
    assert rows[0]['date'] == ''


def test_failed_profile_refresh_removes_previous_artifacts(tmp_path):
    from chart_recover.public_profile import fetch_profile
    for name in ('profile.md', 'profile.json'):
        (tmp_path/name).write_text('previous profile', encoding='utf-8')
    class Session:
        def get(self, *args, **kwargs):
            raise requests.ConnectionError('offline')
    with pytest.raises(requests.ConnectionError):
        fetch_profile('https://trustmrr.com/startup/synthetic-lumen-example', tmp_path, Session())
    assert not (tmp_path/'profile.md').exists() and not (tmp_path/'profile.json').exists()


def test_profile_stream_has_a_wall_clock_deadline(tmp_path, monkeypatch):
    import chart_recover.public_profile as public
    class Response:
        status_code = 200
        closed = False
        def iter_content(self, chunk_size):
            for _ in range(100):
                yield b'x'
        def close(self):
            self.closed = True
    response = Response()
    class Session:
        def get(self, *args, **kwargs):
            return response
    clock = iter(range(0, 1000, 10))
    monkeypatch.setattr(public, 'monotonic', lambda: next(clock), raising=False)
    with pytest.raises(TimeoutError, match='deadline'):
        public.fetch_profile('https://trustmrr.com/startup/synthetic-lumen-example', tmp_path, Session())
    assert response.closed


def test_accepted_shifted_money_token_is_not_rejected_a_second_time():
    from chart_recover.autopilot import consensus_tokens
    accepted, rejected = consensus_tokens([token('$100.00', 30)], [token('$100.00', 34)])
    assert len(accepted) == 1 and not rejected


def bar_reader(monkeypatch, tmp_path, second_footer):
    import chart_recover.autopilot as autopilot
    image = tmp_path/'card.png'
    Image.new('RGB', (300, 280), 'white').save(image)
    monkeypatch.setattr(autopilot, 'detect_bars', lambda *args: dict(size=[300, 280], candidates=[card()], method='test geometry'))
    passes = iter([tokens(), tokens(), tokens()[1:], second_footer])
    monkeypatch.setattr(autopilot, 'read_text', lambda *args, **kwargs: dict(tokens=next(passes), available=True))
    return autopilot.inspect_bar_card(image)


def test_bar_reader_keeps_anchors_for_agreed_four_pixel_footer_shift(tmp_path, monkeypatch):
    footer = [dict(t, box=[t['box'][0]+4, *t['box'][1:]]) for t in tokens()[1:]]
    result = bar_reader(monkeypatch, tmp_path, footer)
    assert len(result['binding']['anchors']) == 2


def test_bar_reader_withholds_all_anchors_for_conflicting_footer_amount(tmp_path, monkeypatch):
    footer = tokens()[1:]
    footer[-1] = dict(footer[-1], text='$900.00')
    result = bar_reader(monkeypatch, tmp_path, footer)
    assert result['binding']['anchors'] == []
    assert any('withheld' in item.get('reason', '') for item in result['binding']['decisions'])


def test_nonfinite_bar_amount_is_a_reviewable_rejection():
    from chart_recover.autopilot import bind_bar_labels
    labels = tokens()
    labels[-1]['text'] = '$' + '9'*400
    result = bind_bar_labels(card(), labels, 'synthetic image', [300, 280])
    assert result['anchors'] == []
    assert any('finite' in item.get('reason', '') for item in result['decisions'])
    json.dumps(result, allow_nan=False)


def test_ocr_output_limit_is_checked_before_tsv_parsing(tmp_path, monkeypatch):
    import chart_recover.ocr as ocr
    image = tmp_path/'image.png'
    Image.new('RGB', (40, 20), 'white').save(image)
    monkeypatch.setattr(ocr.shutil, 'which', lambda name: 'tesseract')
    monkeypatch.setattr(ocr, 'MAX_OCR_OUTPUT', 128, raising=False)
    def run(*args, **kwargs):
        assert not kwargs.get('capture_output')
        assert kwargs.get('stderr') == ocr.subprocess.DEVNULL
        kwargs['stdout'].write(b'x'*129)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(ocr.subprocess, 'run', run)
    result = ocr.read_text(image)
    assert not result['available'] and not result['tokens'] and 'limit' in result['reason']


@pytest.mark.parametrize('error', [KeyError('missing'), TypeError('invalid'), IndexError('index'), np.linalg.LinAlgError('singular')])
def test_reader_exception_does_not_abort_other_attempts(tmp_path, monkeypatch, error):
    import chart_recover.automatic as automatic
    image = tmp_path/'image'
    image.write_bytes(b'synthetic')
    def fail(*args):
        raise error
    def remaining(*args):
        return dict(status='needs_evidence_or_review', recovery=[], geometry=dict(series=[]), correspondence=dict(reasons=['Review']))
    monkeypatch.setattr(automatic, 'analyze', fail)
    monkeypatch.setattr(automatic, 'analyze_calendar', remaining)
    monkeypatch.setattr(automatic, 'analyze_ticks', remaining)
    result = automatic.recover(image, output=tmp_path/'out')
    assert len(result['attempts']) == 3 and result['attempts'][0]['status'] == 'failed'
    assert result['attempts'][2]['next_actions'] == ['Review']


def test_calendar_calibration_reason_is_kept_in_workflow(tmp_path, monkeypatch):
    import chart_recover.automatic as automatic
    image = tmp_path/'image'
    image.write_bytes(b'synthetic')
    def result(*args):
        return dict(status='needs_evidence_or_review', recovery=[dict(status='ambiguous_scale', reason='Confirm linear or logarithmic scale.')],
                    geometry=dict(series=[]), correspondence=dict(reasons=[]), trace=[dict(next_actions=[])])
    for reader in ('analyze', 'analyze_calendar', 'analyze_ticks'):
        monkeypatch.setattr(automatic, reader, result)
    workflow = automatic.recover(image, output=tmp_path/'out')
    assert workflow['attempts'][1]['next_actions'] == ['Confirm linear or logarithmic scale.']


@pytest.mark.parametrize('content', ['', '{"id":"123","images":[]}\n'])
def test_empty_automatic_batch_replaces_previous_summary(tmp_path, content):
    from chart_recover.automatic import recover_batch
    manifest = tmp_path/'posts.jsonl'
    manifest.write_text(content, encoding='utf-8')
    output = tmp_path/'out'
    output.mkdir()
    (output/'batch.json').write_text('{"images":999}', encoding='utf-8')
    result = recover_batch(manifest, output)
    assert json.loads((output/'batch.json').read_text()) == result
    assert result['images'] == 0


@pytest.mark.parametrize('names', [
    ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
])
def test_standard_weekday_names_are_recognized(names):
    from chart_recover.calendar_vision import weekday_rows
    rows = weekday_rows([dict(text=name, box=[100+i*70, 200, 30, 12]) for i, name in enumerate(names)])
    assert len(rows) == 1
    assert rows[0]['first_weekday'] == (6 if names[0] == 'Sunday' else 0)


def test_catalog_can_replay_its_own_raw_export(tmp_path):
    from chart_recover.evidence_discovery import EvidenceDiscovery
    cache = tmp_path/'cache'
    cache.mkdir()
    (cache/'catalog.raw.json').write_text(json.dumps(dict(recentlyAddedStartups=[], fastestGrowingStartups=[])), encoding='utf-8')
    result = EvidenceDiscovery(tmp_path/'out', cache=cache).catalog()
    assert result['mode'] == 'offline_snapshot' and result['entries'] == []


@pytest.mark.parametrize('outer_grid', [False, True])
def test_tick_curve_cannot_be_silently_cropped_to_inner_labels(outer_grid):
    from chart_recover.tick_recovery import bind_ticks, trace_axis_curve
    im = Image.new('RGB', (600, 400), 'white')
    draw = ImageDraw.Draw(im)
    ys = [40, 100, 160, 220, 280, 340] if outer_grid else [100, 160, 220]
    lines = [dict(y=y, left=70, right=500) for y in ys]
    labels = [dict(text=f'${400-y}', box=[515, y-8, 40, 16], confidence=95) for y in (100, 160, 220)]
    draw.line([(70, 180), (80, 30), (90, 180), (499, 180)], fill='#725ade', width=3)
    axis = bind_ticks(labels, lines, im.size, 'synthetic chart')['axes'][0]
    candidates, roi = trace_axis_curve(np.array(im), axis)
    if outer_grid:
        assert len(candidates) == 1 and min(candidates[0]['coordinates']) < 60
        assert roi[1] < 30
    else:
        assert candidates == []


def test_accumulated_grid_extent_drift_abstains_without_empty_gap_crash():
    from chart_recover.tick_recovery import bind_ticks
    lines = [dict(y=80+i*60, left=left, right=right)
             for i, (left, right) in enumerate([(200,700), (100,700), (200,710), (200,720), (0,710)])]
    labels = [dict(text=f'${400-i*100}', box=[line['right']+15, line['y']-8, 40, 16], confidence=95)
              for i, line in enumerate(lines)]
    result = bind_ticks(labels, lines, (1000, 600), 'synthetic extent drift')
    assert not result['axes']
    assert any('distinct grid strokes' in rejected['reason'] for rejected in result['rejected'])


def test_currency_csv_uses_utf8_under_a_legacy_host_locale(tmp_path, monkeypatch):
    from pathlib import Path
    import chart_recover.tick_recovery as recovery
    from test_ticks import fixture
    image, _, labels = fixture(tmp_path)
    for label in labels:
        label['text'] = label['text'].replace('$', '€')
    monkeypatch.setattr(recovery, 'read_text', lambda *args, **kwargs: dict(tokens=labels))
    original = Path.open
    def legacy_default(path, mode='r', *args, **kwargs):
        if path.name == 'data.csv' and mode == 'w':
            kwargs.setdefault('encoding', 'cp1252')
        return original(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', legacy_default)
    result = recovery.analyze_ticks(image, output=tmp_path/'result')
    assert result['status'] == 'calibrated'
    assert '€' in (tmp_path/'result/data.csv').read_bytes().decode('utf-8')
