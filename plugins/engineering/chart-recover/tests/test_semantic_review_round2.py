"""Additional review regressions for evidence integrity and affine constraints."""
import json
from pathlib import Path
import numpy as np
import pytest
from chart_recover.calibrate import calibrate
from chart_recover.constraints import calibrate_totals
from chart_recover.evidence import claims_from_text
from chart_recover.growth import derive_previous_month_claims
from chart_recover.pipeline import analyze
from chart_recover.retrieval import CorpusRetriever
from chart_recover.semantic import bind_documents, parse_document


def doc(text, **kw): return dict(text=text, url='https://example.com/disclosure', **kw)

def context(**kw):
    return dict(entity='Acme', metric='mrr', currency='USD', aggregation='snapshot', series='series_0',
        source='Reviewed title', periods=['2026-01','2026-02','2026-03'], period_source='Visible month labels', **kw)

def geometry():
    return dict(series=[dict(id='series_0', kind='bar', points=[dict(x=i,y=y) for i,y in enumerate([200,150,100])], coordinates=[200,150,100])])

def line_fixture():
    root=Path(__file__).resolve().parent.parent/'skills/chart-recover/scripts/chart_recover/assets/examples/line'
    return root/'chart.png', json.loads((root/'config.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('periods,reason', [
    (['2026-02','2026-01','2026-03'], 'nonmonotonic_period_axis'),
    (['2026-01','2026-13','2026-03'], 'invalid_period_axis'),
])
def test_positional_period_axis_must_be_valid_and_chronological(periods, reason):
    cfg=context(); cfg['periods']=periods
    result=bind_documents([doc('Acme MRR was USD 100 in January 2026.')], geometry(), cfg)
    assert not result['anchors']
    assert reason in result['decisions'][0]['reasons']


def test_unknown_total_series_is_never_silently_discarded(tmp_path):
    image,cfg=line_fixture(); cfg['ocr']=False
    cfg['totals']=[dict(series='absent',value=123,point_indices=[0],observation_count=1,source='Reviewed sum',matched=True)]
    with pytest.raises(ValueError, match='Total references an unknown series'):
        analyze(image,cfg,tmp_path)


def test_malformed_publication_date_cannot_rescue_qualified_growth():
    d=doc('Acme MRR was USD 100 in January 2026. MRR was up 10% on last month in January.',created_at='not-a-date')
    assert not derive_previous_month_claims(d,parse_document(d,'Acme'))['claims']


def test_nonfinite_currency_lead_never_breaks_json_export():
    claims=claims_from_text('MRR $'+'9'*500+' and grew '+'9'*500+'x.', 'https://example.com')
    assert claims==[]
    json.dumps(claims,allow_nan=False)


def test_evidence_document_field_aliases_reach_semantic_binding(tmp_path):
    image,cfg=line_fixture(); cfg['ocr']=False
    cfg['chart_context']=context()
    cfg['evidence_documents']=[dict(text_excerpt='Acme MRR was USD 100 in January 2026.',source='https://example.com/disclosure')]
    result=analyze(image,cfg,tmp_path)
    claim=result['evidence_binding']['claims'][0]
    assert claim['source']=='https://example.com/disclosure'
    assert claim['metric']=='mrr' and claim['period']=='2026-01'


def test_post_source_field_preserves_binder_provenance(tmp_path):
    image,cfg=line_fixture(); cfg['ocr']=False
    cfg.update(source='https://example.com/post',post_text='Acme MRR was USD 100 in January 2026.',
        chart_context=dict(context(), periods=[]))
    result=analyze(image,cfg,tmp_path)
    claim=result['evidence_binding']['claims'][0]
    assert claim['source']=='https://example.com/post'
    assert 'missing_public_source_url' not in claim['issues']


@pytest.mark.parametrize('source', ['https://[invalid', 'https://example.com:bad', None])
def test_malformed_provenance_is_recorded_as_rejection(source):
    result=bind_documents([dict(text='Acme MRR was USD 100 in January 2026.',url=source)],geometry(),context())
    assert not result['anchors']
    assert 'missing_public_source_url' in result['decisions'][0]['reasons']


@pytest.mark.parametrize('token',['8x','8×','8 ×'])
def test_ratio_leads_support_both_multiplication_spellings(token):
    assert claims_from_text('We grew '+token+'.','https://example.com')[0]['ratio']==8


@pytest.mark.parametrize('amount', ['100–200', '100 to 200', '100 or more', '100 or less', '100 minimum', '100 maximum'])
def test_ranges_and_postfixed_bounds_are_not_point_anchors(amount):
    result=bind_documents([doc(f'Acme MRR was USD {amount} in January 2026.')],geometry(),context())
    assert not result['anchors']
    assert set(result['decisions'][0]['reasons']) & {'range_not_point_value','lower_bound_not_point_value','upper_bound_not_point_value'}


@pytest.mark.parametrize('amount',['1 thousand','1 million','1 billion'])
def test_word_multipliers_are_not_parsed_as_unscaled_units(amount):
    result=bind_documents([doc(f'Acme MRR was USD {amount} in January 2026.')],geometry(),context())
    assert not result['anchors']
    assert 'word_multiplier_needs_review' in result['decisions'][0]['reasons']


def test_corpus_dedup_preserves_later_provenance_through_binding():
    text='Acme dashboard. MRR was USD 100 in January 2026.'
    records=[doc(text),doc(text,entity='Acme',entity_source='Reviewed source title')]
    retrieved=CorpusRetriever(records).retrieve(context())
    assert len(retrieved)==2
    result=bind_documents(retrieved,geometry(),context())
    assert len(result['anchors'])==1
    assert len(result['decisions'])==2


def test_lead_metrics_do_not_cross_sentence_boundaries():
    claims=claims_from_text('Revenue $100. ARR $1200.', 'https://example.com')
    assert [(c['value'],c['metric']) for c in claims]==[(100,'revenue'),(1200,'arr')]


@pytest.mark.parametrize('amount',['$1,00','$1,,000','-$100','−$100','($100)'])
def test_malformed_or_signed_amounts_do_not_become_positive_leads(amount):
    assert not claims_from_text('MRR '+amount+'.', 'https://example.com')


def test_finite_domain_still_bounds_values_when_pixel_objectives_are_unbounded():
    result=calibrate_totals([0],value_domain=dict(low=0,high=100,source='Reviewed domain'),pixel_error=2.5)
    assert result['status']=='bounded_only'
    assert result['values'] is None and result['lower']==[0] and result['upper']==[100]


def test_domain_representative_is_one_affine_curve_without_point_clipping():
    points=[1,0,-1]
    anchors=[dict(pixel=p,value=-p,pixel_error=2,source='Reviewed off-plot tick',matched=True) for p in [3,-3]]
    result=calibrate_totals(points,anchors=anchors,value_domain=dict(low=0,source='Nonnegative plotted values'),pixel_error=2)
    assert result['status']=='calibrated'
    prediction=result['coefficients']['a']*(-np.array(points))+result['coefficients']['b']
    assert result['values']==pytest.approx(prediction)
    assert min(result['values'])>=-1e-7


def test_aggregate_fit_uses_constrained_least_squares_in_constraint_units():
    points=[0,-1,-2]
    anchors=[dict(pixel=p,value=v,pixel_error=e,source='Reviewed label',matched=True) for p,v,e in zip(points,[0,2,2],[0,1,.5])]
    total=dict(value=5,point_indices=[1,2],observation_count=2,pixel_error=1,source='Reviewed total',matched=True)
    result=calibrate_totals(points,anchors=anchors,totals=[total],pixel_error=0)
    assert result['status']=='calibrated'
    assert result['coefficients']==pytest.approx(dict(a=4/3,b=0),abs=1e-7)
    assert result['point_estimator']['method']=='constrained_least_squares'
