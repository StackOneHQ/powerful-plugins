"""Controls for the second review of collection and geometric hypotheses."""
from io import BytesIO
import json

import numpy as np
from PIL import Image, ImageDraw
import pytest
import requests

from chart_recover.collect import normalize_response, save_posts, XCollector
from chart_recover.curve_grid import fit_shared_grid
from chart_recover.discovery import discover, FEED
from chart_recover.hypotheses import propose_calendar, candidate_result
from chart_recover.layout import detect_bars
from chart_recover.vision import extract
from test_comparison_totals import fixture as comparison_fixture, propose
from test_hypotheses import fixture as calendar_fixture


@pytest.mark.parametrize('box', [[50, 30, 70, 180], [50, 50, 95, 80]])
def test_single_rectangle_auto_mode_explicitly_requests_kind(tmp_path, box):
    image = Image.new('RGB', (250, 220), 'white')
    ImageDraw.Draw(image).rectangle(box, fill='#4466cc')
    path = tmp_path/'single.png'; image.save(path)
    result = extract(path)
    assert result['status'] == 'needs_review' and not result['series']
    assert any('single rectangular mark' in issue['reason'] for issue in result['quality_issues'])


@pytest.mark.parametrize('kind', ['bar', 'barh'])
def test_auto_bar_orientation_uses_shared_baselines(tmp_path, kind):
    image = Image.new('RGB', (400, 260), 'white'); draw = ImageDraw.Draw(image)
    if kind == 'bar':
        for x, top in zip((30, 145, 260), (190, 185, 180)):
            draw.rectangle([x, top, x+75, 205], fill='#4466cc')
    else:
        for y, right in zip((30, 100, 170), (150, 200, 240)):
            draw.rectangle([30, y, right, y+15], fill='#4466cc')
    path = tmp_path/'bars.png'; image.save(path)
    result = extract(path)
    assert result['status'] == 'extracted'
    assert result['series'][0]['kind'] == kind


def test_layout_resize_uses_actual_axis_scales(tmp_path):
    image = Image.new('RGB', (4201, 899), 'white'); draw = ImageDraw.Draw(image)
    for x, top in zip((350, 1750, 3150), (500, 350, 200)):
        draw.rectangle([x, top, x+350, 750], fill='#7788ee')
    large = tmp_path/'large.png'; small = tmp_path/'small.png'
    image.save(large); image.resize((1400, 300)).save(small)
    native = detect_bars(large)['candidates'][0]['points']
    resized = detect_bars(small)['candidates'][0]['points']
    for actual, expected in zip(native, resized):
        assert actual['x'] == pytest.approx(expected['x']*4201/1400)
        assert actual['width'] == pytest.approx(expected['width']*4201/1400)
        assert actual['y'] == pytest.approx(expected['y']*899/300)
        assert actual['base'] == pytest.approx(expected['base']*899/300)


@pytest.mark.parametrize('size', [(1, 10000), (10000, 1)])
def test_layout_resize_never_rounds_an_axis_to_zero(tmp_path, size):
    path = tmp_path/'thin.png'; Image.new('RGB', size, 'white').save(path)
    result = detect_bars(path)
    assert result['status'] == 'needs_review' and result['size'] == list(size)


def test_hypothesis_preserves_configured_error_and_correspondence_assumptions():
    ordinary = calendar_fixture(); wide = calendar_fixture()
    wide['config'] = dict(pixel_error=8.)
    wide['correspondence']['assumptions'] = ['The user explicitly assumes the panels share a currency.']
    first = propose_calendar(ordinary); second = propose_calendar(wide)
    narrow = first['hypotheses'][0]['recovery']; broad = second['hypotheses'][0]['recovery']
    assert broad['pixel_error'] == pytest.approx(8.2)
    assert all(a['pixel_error'] == pytest.approx(8.2) for a in broad['anchors_used'])
    assert np.mean(np.array(broad['upper'])-broad['lower']) > np.mean(np.array(narrow['upper'])-narrow['lower'])
    candidate = candidate_result(wide, second)
    assert wide['correspondence']['assumptions'][0] in candidate['correspondence']['assumptions']
    assert wide['correspondence']['assumptions'][0] in candidate['recovery'][0]['assumptions']


def test_failed_hypotheses_explain_top_level_abstention():
    result = calendar_fixture()
    for i, observation in enumerate(result['calendar']['observations']):
        if i % 3 == 1:
            for key in ('value', 'low', 'high'): observation[key] += 1200
    proposal = propose_calendar(result)
    assert proposal['status'] == 'no_supported_hypothesis'
    assert proposal['rejections']
    assert proposal['hypotheses'][0]['reasons'][0] in proposal['rejections']


def test_zero_comparison_total_is_allowed_with_a_distinct_total():
    curves, tokens, _ = comparison_fixture()
    tokens[4]['text'] = '$0.00'
    result = propose(curves, tokens)
    assert result['status'] == 'conditional_calibration', result['reasons']
    assert result['totals'][1]['value'] == 0
    assert sum(result['recovery'][1]['values']) == pytest.approx(0., abs=1e-6)


def test_weak_columns_are_excluded_before_grid_fitting():
    rng = np.random.default_rng(19); x = np.arange(39, 1002); knots = np.linspace(40, 1000, 28)
    curves = []
    for _ in range(2):
        y = np.interp(x, knots, rng.uniform(130, 570, 28)); weak = x % 7 == 0
        errors = np.where(weak, 3.5, 2.5); y[weak] += 100
        curves.append(dict(x=x.tolist(), y=y.tolist(), pixel_error=errors.tolist()))
    result = fit_shared_grid(curves, 39, 1001, 28)
    assert result['status'] == 'supported', result
    assert result['weak_observation_policy'] == 'exclude'
    assert all(c['excluded_weak_columns'] > 100 and c['mean_error'] < .1 for c in result['checks'])
    for curve in curves: curve['pixel_error'] = [3.5]*len(x)
    result = fit_shared_grid(curves, 39, 1001, 28)
    assert result['status'] == 'needs_review'


@pytest.mark.parametrize('background, expected', [('black', True), ('white', False)])
def test_comparison_ocr_passes_use_luminance_inversion(tmp_path, monkeypatch, background, expected):
    import chart_recover.comparison_totals as module
    path = tmp_path/'comparison.png'; Image.new('RGB', (1050, 730), background).save(path)
    curves, _, _ = comparison_fixture(); calls = []
    monkeypatch.setattr(module, 'trace_curve', lambda *a, **k: (dict(size=[1050, 730]), curves))
    def read(*args, **kwargs):
        calls.append(kwargs); return dict(tokens=[])
    monkeypatch.setattr(module, 'read_text', read)
    module.recover_comparison(path, {}, tmp_path/'output')
    assert len(calls) == 4 and all(call['invert'] is expected for call in calls)


def test_missing_user_expansion_preserves_unknown_author():
    post = normalize_response(dict(data=dict(id='123', author_id='inaccessible')))[0]
    assert post['author'] is None
    assert post['url'] == 'https://x.com/i/status/123'


def test_collection_pages_deduplicate_and_respect_page_limit():
    class Response:
        status_code = 200
        def __init__(self, payload): self.payload = payload
        def raise_for_status(self): pass
        def json(self): return self.payload
    class Session:
        def __init__(self): self.calls = []
        def get(self, url, **kwargs):
            self.calls.append(dict(kwargs['params']))
            if len(self.calls) == 1:
                return Response(dict(data=[dict(id='1'), dict(id='2')], meta=dict(next_token='next-page')))
            return Response(dict(data=[dict(id='2'), dict(id='3')]))
    session = Session()
    assert [p['id'] for p in XCollector('test', session).search('revenue', max_pages=2)] == ['1', '2', '3']
    assert session.calls[1]['next_token'] == 'next-page'
    single = Session()
    assert len(list(XCollector('test', single).search('revenue', max_pages=1))) == 2
    assert len(single.calls) == 1


def png_bytes():
    stream = BytesIO(); Image.new('RGB', (30, 30), 'white').save(stream, format='PNG')
    return stream.getvalue()


class MediaResponse:
    status_code = 200
    def __init__(self, content): self.content = content; self.closed = False; self.received = 0
    def raise_for_status(self): pass
    def iter_content(self, size):
        for i in range(0, len(self.content), size):
            chunk = self.content[i:i+size]; self.received += len(chunk); yield chunk
    def close(self): self.closed = True


def test_metadata_only_collection_can_later_download_and_retry_failures(tmp_path, monkeypatch):
    post = dict(id='123', media=[dict(type='photo', url='https://pbs.twimg.com/media/test.png')])
    save_posts([post], tmp_path, download=False)
    monkeypatch.setattr('chart_recover.collect.requests.get', lambda *a, **k: MediaResponse(b'invalid PNG'))
    assert save_posts([post], tmp_path)['updated'] == 1
    response = MediaResponse(png_bytes()); calls = []
    def get(*args, **kwargs): calls.append(args); return response
    monkeypatch.setattr('chart_recover.collect.requests.get', get)
    result = save_posts([post], tmp_path)
    assert result['added'] == 0 and result['updated'] == 1 and response.closed
    saved = json.loads((tmp_path/'posts.jsonl').read_text())
    assert len(saved['images']) == 1 and not saved.get('errors')
    save_posts([post], tmp_path)
    assert len(calls) == 1


def test_cumulative_download_budget_stops_streaming_and_later_requests(tmp_path, monkeypatch):
    content = png_bytes(); responses = []
    def get(*args, **kwargs):
        response = MediaResponse(content); responses.append(response); return response
    monkeypatch.setattr('chart_recover.collect.requests.get', get)
    post = dict(id='123', media=[dict(type='photo', url=f'https://pbs.twimg.com/media/{i}.png') for i in range(3)])
    budget = len(content)+20
    save_posts([post], tmp_path, max_total_bytes=budget)
    saved = json.loads((tmp_path/'posts.jsonl').read_text())
    assert len(saved['images']) == 1 and len(responses) == 2
    assert responses[1].received <= 21 and all(r.closed for r in responses)
    assert len(list(tmp_path.glob('*.image'))) == 1
    assert any('budget' in error for error in saved['errors'])


class FeedResponse:
    def __init__(self, body=b'', status=200, headers=None):
        self.body = body; self.status_code = status; self.headers = headers or {}; self.closed = False
    def iter_content(self, size): yield self.body
    def close(self): self.closed = True


@pytest.mark.parametrize('failure', ['http', 'timeout', 'oversize'])
def test_directory_fetch_failures_write_an_auditable_summary(tmp_path, failure):
    class Session:
        def get(self, *args, **kwargs):
            if failure == 'timeout': raise requests.Timeout('synthetic timeout')
            return FeedResponse(status=503) if failure == 'http' else FeedResponse(b'x'*5_000_001)
    with pytest.raises((RuntimeError, ValueError, requests.RequestException)):
        discover(tmp_path, session=Session(), download=False)
    saved = json.loads((tmp_path/'discovery.json').read_text())
    assert saved['status'] == 'failed' and saved['records'][0]['url'] == FEED
    assert saved['stored_posts'] == saved['downloaded_images'] == 0


def test_directory_follows_only_bounded_same_host_https_redirects(tmp_path):
    first = FeedResponse(status=301, headers={'Location': '/feed/'}); final = FeedResponse()
    class Session:
        def __init__(self): self.urls = []
        def get(self, url, **kwargs):
            self.urls.append(url)
            assert kwargs['allow_redirects'] is False
            return first if len(self.urls) == 1 else final
    session = Session(); result = discover(tmp_path, session=session, download=False)
    assert session.urls == [FEED, FEED+'/'] and first.closed and final.closed
    assert result['stored_posts'] == result['downloaded_images'] == 0


def test_directory_refuses_a_redirect_to_another_host(tmp_path):
    response = FeedResponse(status=302, headers={'Location': 'https://example.com/feed'})
    class Session:
        def get(self, *args, **kwargs): return response
    with pytest.raises(ValueError, match='public directory HTTPS host'):
        discover(tmp_path, session=Session(), download=False)
    assert response.closed
    assert json.loads((tmp_path/'discovery.json').read_text())['status'] == 'failed'


def test_per_post_write_failure_does_not_skip_later_urls(tmp_path, monkeypatch):
    import chart_recover.discovery as module
    urls = ['https://x.com/a/status/123', 'https://x.com/b/status/456']
    class Session:
        def get(self, *args, **kwargs): return FeedResponse(''.join(f'<a href="{u}">post</a>' for u in urls).encode())
    class Collector:
        def lookup(self, url): return [dict(id=url.rsplit('/', 1)[-1], media=[])]
    calls = []
    def save(posts, *args, **kwargs):
        calls.append(posts[0]['id'])
        if len(calls) == 1: raise OSError('synthetic manifest write failure')
        return dict(added=1)
    monkeypatch.setattr(module, 'save_posts', save)
    result = discover(tmp_path, session=Session(), collector=Collector(), download=False)
    assert calls == ['123', '456']
    assert [record['status'] for record in result['records']] == ['unavailable', 'collected']
    assert result['stored_posts'] == result['downloaded_images'] == 0
