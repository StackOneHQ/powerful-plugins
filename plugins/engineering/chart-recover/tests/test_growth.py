import json
import pytest
from chart_recover.growth import derive_previous_month_claims,previous_amount_interval,previous_month
from chart_recover.semantic import parse_document,bind_documents
from chart_recover.calibrate import calibrate
from chart_recover.investigate import investigate
from chart_recover.retrieval import CorpusRetriever
from chart_recover.synthetic import collision_demo


def document(text):return {'url':'https://example.com/synthetic/growth','text':text}
def derive(text):
    d=document(text);return derive_previous_month_claims(d,parse_document(d,'Acme'))


def test_rounding_interval_contains_all_four_arithmetic_corners():
    interval=previous_amount_interval(9193.10,.01,'9.63','down')
    corners=[amount/(1-percent/100) for amount in [9193.095,9193.105] for percent in [9.625,9.635]]
    assert interval['low']==pytest.approx(min(corners))
    assert interval['high']==pytest.approx(max(corners))
    assert interval['low']<10172.56<interval['high']
    assert previous_month('2026-01')=='2025-12'


@pytest.mark.parametrize('text',[
    'Acme revenue target USD 100 in July 2026.\nRevenue was up 10% on last month.',
    'Acme revenue was USD 100 in July 2026.\nRevenue was up 10% on last month, but that was incorrect.',
    'Acme revenue was USD 100 in July 2026.\nRevenue was up 10% on last month in May 2026.',
    'Acme revenue was USD 100 in July 2026.\nRevenue was up 10% on last month for their competitor.',
    'Acme revenue was USD 100 in July 2026. Acme revenue was USD 90 in June 2026.\nRevenue was up 10% on last month.',
    'Acme MRR was USD 100 in July 2026.\nRevenue was up 10% on last month.',
    'Acme revenue was USD 100 in July 2026.\nRevenue was down 100% on last month.',
    'Acme revenue was USD 100 in July 2026.\nRevenue was up 10% year over year.',
    'Acme revenue was USD 100 in July 2026.\nRevenue was up 10%.',
    'Acme revenue was USD 100 in July 2026.\nRevenue was not up 10% on last month.',
])
def test_ambiguous_or_invalid_growth_does_not_create_prior_claim(text):
    assert not derive(text)['claims']


def test_derived_claim_preserves_dependency_and_value_interval():
    g=derive('Acme MRR was USD 80.00 in June 2026.\nMRR was up 63.27% on last month.')
    c=g['claims'][0]
    assert c['period']=='2026-05' and c['metric']=='mrr'
    assert c['interval_low']<49<c['interval_high']
    assert c['derivation']['independent_evidence'] is False
    assert c['derivation']['current_claim_id'] and c['operator']=='derived_range'


def test_growth_evidence_recovers_a_chart_without_second_absolute_disclosure(tmp_path):
    collision_demo(tmp_path)
    ctx={'entity':'Acme','metric':'mrr','currency':'USD','aggregation':'snapshot','series':'series_0',
         'source':'Fixture title','periods':[f'2026-{i:02d}' for i in range(1,7)],'period_source':'Fixture date labels'}
    doc=document('Acme MRR was USD 80.00 in June 2026.\nMRR was up 63.27% on last month.')
    r=investigate(tmp_path/'scale_1.png',{'kind':'bar','scale':'linear','ocr':False,'chart_context':ctx},tmp_path/'run',retriever=CorpusRetriever([doc]))
    result=json.loads((tmp_path/'run'/r['final_result']).read_text())
    assert r['status']=='calibrated'
    cal=result['recovery'][0];expected=[10,15,22,31,49,80]
    # Adjacent anchors amplify integer-pixel rounding. Judge chart error in
    # axis-range units and require the declared feasible bounds to cover truth.
    assert sum(abs(a-b) for a,b in zip(cal['values'],expected))/len(expected)<.01*(80-10)
    assert all(lo<=v<=hi for lo,v,hi in zip(cal['lower'],expected,cal['upper']))
    claims=result['evidence_binding']['claims'];assert len(claims)==2
    assert sum(bool(c.get('derivation')) for c in claims)==1
    assert any('not independent' in a for a in result['recovery'][0]['assumptions'])


def test_conflicting_growth_is_kept_instead_of_picking_a_convenient_ratio():
    d=document('Acme MRR was USD 100 in July 2026.\nMRR was up 25% on last month.\nMRR was up 100% on last month.')
    geometry={'series':[{'id':'series_0','kind':'bar','points':[{'x':1,'y':200},{'x':2,'y':100}],'coordinates':[200,100]}]}
    ctx={'entity':'Acme','metric':'mrr','currency':'USD','aggregation':'snapshot','series':'series_0','source':'Fixture title',
         'periods':['2026-06','2026-07'],'period_source':'Fixture labels'}
    b=bind_documents([d],geometry,ctx)
    assert len(b['anchors'])==3
    assert calibrate([200,100],b['anchors'],scale='linear')['status']=='inconsistent'
