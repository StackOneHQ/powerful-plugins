"""Daily values belong to plateaus; a vertical stroke is not an observation."""
from copy import deepcopy
from datetime import date, timedelta

import numpy as np
import pytest

from chart_recover.external_evidence import map_observations, select_alignment
from chart_recover.external_benchmark import generate, score, URL
from chart_recover.external_evidence import recover_external
from chart_recover.public_profile import parse_profile
from PIL import Image


LEVELS = np.array([120,310,180,390,140,280,210,350,110,240,
                   380,160,290,200,330,130,360,220,300,170,
                   260,400,150,320,190,370,230,340,100,250.])


def fixture(convention='post', levels=LEVELS, irregular=False, scale='linear'):
    xs = np.arange(50, 921, dtype=float)
    nodes = np.arange(50, 921, 30, dtype=float)
    phase = .5 if convention == 'mid' else 0.
    edges = nodes[:-1] + 30*phase if convention != 'post' else nodes[1:]
    if irregular:
        edges = edges + np.resize([-5., 5.], len(edges))
    ys = levels[np.searchsorted(edges, xs, side='right')]
    # A raster trace at a vertical stroke reads its middle, not either day.
    for i, edge in enumerate(edges):
        ys[abs(xs-edge) <= 1] = (levels[i]+levels[i+1])/2
    geometry = dict(size=[1000,600], roi=[49,80,922,420], series=[dict(
        points=[dict(x=float(x), y=float(y), pixel_error=2.5) for x,y in zip(xs,ys)])])
    axis = dict(origin='2026-09-01', origin_x=51.25, pixels_per_day=29.95,
                pixel_error=3., fit_labels=[])
    rows = []
    for i, y in enumerate(levels):
        period = (date(2026,9,1)+timedelta(days=i)).isoformat()
        value = 500-y if scale == 'linear' else 10**(4-y/150)
        rows.append(dict(period=period, value=float(value), low=float(value-.005),
                         high=float(value+.005), source='fixture', source_line=i+1,
                         status='redacted' if i in (3,8,13,19,23,27) else 'dated_observation'))
        if i in (0,5,10,15,20,25,29):
            x = 51.25+29.95*i
            axis['fit_labels'].append(dict(date=period, x=x,
                month_box=[x-25,490,24,16], day_box=[x+1,490,24,16]))
    return geometry, rows, axis


@pytest.mark.parametrize('convention', ['pre','post','mid'])
@pytest.mark.parametrize('scale', ['linear','log'])
def test_step_boundaries_locate_dates_and_choose_the_correct_plateau(convention, scale):
    # Monetary agreement within a plateau must not stretch or translate dates.
    geometry, rows, axis = fixture(convention, scale=scale)
    selected, ledger = select_alignment(geometry, rows, axis)
    assert selected is not None
    assert selected['origin_x'] == pytest.approx(50, abs=.75)
    assert selected['pixels_per_day'] == pytest.approx(30, abs=.03)
    assert selected['sampling']['convention'] == convention
    mapped = map_observations(geometry, [dict(rows[3], status='dated_observation')], selected)[0]
    assert mapped['pixel_x'] == pytest.approx(140, abs=.75)
    assert mapped['pixel'] == pytest.approx(390, abs=.5)
    assert mapped['pixel_error'] < 4
    assert ledger['strategy'] == 'image_steps'


def test_checking_and_redacted_amounts_cannot_choose_step_convention():
    geometry, rows, axis = fixture()
    selected, ledger = select_alignment(geometry, rows, axis)
    changed = deepcopy(rows)
    for r in changed:
        if date.fromisoformat(r['period']).toordinal()%3 == 1 or r['status'] == 'redacted':
            r.update(value=999999., low=999998., high=1000000.)
    other, other_ledger = select_alignment(geometry, changed, axis)
    assert selected is not None and selected.get('sampling')
    assert selected == other
    assert ledger == other_ledger


def test_affine_trend_cannot_identify_pre_versus_post_step_values():
    geometry, rows, axis = fixture(levels=np.linspace(100,390,30))
    # Both adjacent plateaus calibrate perfectly with a different intercept.
    assert select_alignment(geometry, rows, axis)[0] is None


def test_irregular_step_boundaries_cannot_establish_regular_daily_positions():
    geometry, rows, axis = fixture(irregular=True)
    assert select_alignment(geometry, rows, axis)[0] is None


def test_step_sampling_does_not_extrapolate_past_the_last_visible_plateau():
    geometry, rows, axis = fixture()
    axis.update(origin_x=50., pixels_per_day=30., sampling=dict(convention='post'))
    last = map_observations(geometry, [rows[-1]], axis)[0]
    assert not last['eligible']


@pytest.mark.parametrize('convention,expected_indices', [('pre',(4,4)),('post',(3,3)),('mid',(3,4))])
def test_generated_step_images_show_the_declared_plateaus(tmp_path, convention, expected_indices):
    truth = generate(tmp_path, 410001, values=500-LEVELS, axis_scale='linear',
                     curve='step', step_where=convention)
    rgb = np.asarray(Image.open(tmp_path/'chart.png').convert('RGB'))
    for fraction, index in zip((.25,.75), expected_indices):
        x = round(90+(3+fraction)*830/29)
        color_rows = np.where(np.max(abs(rgb[:,x].astype(float)-[113,101,232]),axis=1)<10)[0]
        assert len(color_rows)
        assert np.median(color_rows) == pytest.approx(truth['points'][index]['y'], abs=2)


def test_recovered_step_exports_daily_values_separately_from_vertical_trace(tmp_path):
    # Full reader, including OCR, must expose usable predictions for redacted
    # dates. Merely moving X while retaining vertical midpoints is insufficient.
    truth = generate(tmp_path, 410002, 'matplotlib', values=500-LEVELS, axis_scale='linear', curve='step')
    profile = parse_profile((tmp_path/'profile.md').read_text(), URL)
    result = recover_external(tmp_path/'chart.png', profile, tmp_path/'analysis')
    assert result['status'] == 'conditional_calibration'
    daily = result.get('daily_recovery', [])
    assert len(daily) >= 28
    hidden = next(r for r in daily if r['proposed_date']=='2026-09-04')
    assert hidden['conditional_value'] == pytest.approx(110, abs=2)
    assert hidden['pixel_x'] == pytest.approx(90+3*830/29, abs=2)
    assert hidden['sample_x'] > hidden['pixel_x']+4
    assert all(r['status']=='conditional_calibration' for r in daily)
    assert (tmp_path/'analysis'/'daily.csv').is_file()
    # Scoring uses these actual returned predictions, not private true pixels.
    row = score(result, truth)
    assert row['success']
    corrupt = deepcopy(result)
    for r in corrupt['daily_recovery']:
        r['conditional_value'] += 500
    assert not score(corrupt, truth)['success']
    missing = deepcopy(result)
    missing['daily_recovery'] = [r for r in daily if r['proposed_date']!='2026-09-04']
    assert not score(missing, truth)['success']
