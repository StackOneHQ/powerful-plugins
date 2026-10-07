import copy
import csv
import json
import numpy as np
import pytest
from PIL import Image
from chart_recover.hypotheses import propose_calendar,candidate_result,date_label_audit


def fixture():
    values=np.random.default_rng(911).uniform(150,1400,31);ys=500-values*.2
    points=[dict(x=float(50+i*25),y=float(y)) for i,y in enumerate(ys)]
    observations=[dict(date=f'2026-07-{i+1:02d}',value=float(v),low=float(v-.5),high=float(v+.5),currency='$',box=[0,0,10,10],source=f'fixture cell {i+1}') for i,v in enumerate(values)]
    return dict(status='needs_evidence_or_review',calendar=dict(status='read',layout=dict(year=2026,month=7,days=31),observations=observations,assumptions=[]),
                geometry=dict(series=[dict(id='series_0',kind='line',points=points,coordinates=ys.tolist(),x_location_y_error=[.2]*31)],quality_issues=[]),
                correspondence=dict(reasons=['Confirm identity and dates.'],curve_heading=dict(metric='revenue',aggregation=None),calendar_heading=None,date_ticks=[]),
                trace=[],recovery=[dict(status='needs_correspondence',values=None)])


def test_irregular_pattern_supports_only_a_conditional_candidate():
    r=fixture();p=propose_calendar(r);assert p['status']=='one_supported_conditional_hypothesis'
    h=p['hypotheses'][0];assert h['fit_observations']==21 and h['check_observations']==10
    assert h['check']['nmae']<1e-8
    candidate=candidate_result(r,p)
    assert candidate['status']=='conditional_calibration'
    assert candidate['correspondence']['status']=='inferred_not_verified'
    assert candidate['correspondence']['date_assignment']=='unassigned'
    assert r['recovery'][0]['values'] is None


def test_unused_checking_cells_can_reject_a_fitted_model():
    r=fixture()
    for i,o in enumerate(r['calendar']['observations']):
        if i%3==1:o.update(value=o['value']+1200,low=o['low']+1200,high=o['high']+1200)
    p=propose_calendar(r);h=p['hypotheses'][0]
    assert h['fit_status']=='calibrated' and h['status']=='rejected'
    assert h['check']['nmae']>.02
    assert candidate_result(r,p) is None


@pytest.mark.parametrize('case',['wrong_metric','wrong_period','no_heading','few_cells','smooth'])
def test_weak_or_contradictory_associations_are_not_promoted(case):
    r=fixture()
    if case=='wrong_metric':r['correspondence']['calendar_heading']=dict(metric='mrr',aggregation=None)
    if case=='wrong_period':r['correspondence']['reasons']=['A visible period contradicts the full month.']
    if case=='no_heading':r['correspondence']['curve_heading']=None
    if case=='few_cells':r['calendar']['observations']=r['calendar']['observations'][:13]
    if case=='smooth':
        for i,o in enumerate(r['calendar']['observations']):o['value']=i*100
    p=propose_calendar(r);assert p['status']=='no_supported_hypothesis' and p['rejections']


def test_numerically_similar_panel_does_not_prove_identity():
    # An unrelated panel can be an affine transformation of the same pattern.
    # Numerical checks cannot distinguish it, so identity is still unverified.
    r=fixture()
    for o in r['calendar']['observations']:
        for key in ('value','low','high'):o[key]=o[key]*1000+50000
    p=propose_calendar(r);candidate=candidate_result(r,p)
    assert candidate['status']=='conditional_calibration'
    assert p['numerical_agreement_is_not_identity']
    assert any('does not prove' in s for s in candidate['correspondence']['assumptions'])


def test_date_centers_can_conflict_without_creating_false_plot_dates():
    r=fixture();points=r['geometry']['series'][0]['points']
    ticks=[dict(day=day,x=points[day-1]['x']+68,box=[points[day-1]['x']+55,350,26,12]) for day in (6,16,26)]
    r['correspondence']['date_ticks']=ticks;p=propose_calendar(r)
    assert p['date_label_audit']['status']=='label_centers_disagree'
    assert abs(p['date_label_audit']['pixels_per_day']-25)<1e-8
    assert p['hypotheses'][1]['status']=='rejected'
    candidate=candidate_result(r,p);assert candidate['correspondence']['date_assignment']=='unassigned'
    assert any('decorative' in s for s in candidate['correspondence']['assumptions'])


def test_consistent_inner_labels_agree_with_full_month():
    r=fixture();points=r['geometry']['series'][0]['points']
    ticks=[dict(day=d,x=points[d-1]['x'],box=[points[d-1]['x']-12,350,24,12]) for d in (6,16,26)]
    assert date_label_audit(r['geometry'],ticks,31)['status']=='compatible'


def test_agent_exports_conditional_values_without_plot_dates(tmp_path,monkeypatch):
    from chart_recover.agent import investigate_image
    image=tmp_path/'input.png';Image.new('RGB',(900,600),'white').save(image)
    def readers(path,config,output):
        output.mkdir(parents=True);folder=output/'calendar';folder.mkdir();(folder/'result.json').write_text(json.dumps(dict(fixture(),image_sha256='fixture')))
        return dict(image_sha256='fixture',status='needs_evidence_or_review',calibrated_candidates=0,attempts=[dict(reader='calendar',status='needs_evidence_or_review',result='calendar/result.json')])
    monkeypatch.setattr('chart_recover.agent.recover',readers)
    result=investigate_image(image,{},tmp_path/'result')
    assert result['status']=='has_conditional_candidates' and result['strict_candidates']==0
    rows=list(csv.DictReader((tmp_path/'result/conditional-calendar/data.csv').open()))
    assert len(rows)==31 and all(r['plot_date']=='' and r['conditional_value'] for r in rows)
    assert all(r['status']=='conditional_calibration' for r in rows)
    strict=investigate_image(image,{},tmp_path/'strict',strict_only=True)
    assert strict['conditional_candidates']==0 and not (tmp_path/'strict/conditional-calendar').exists()
