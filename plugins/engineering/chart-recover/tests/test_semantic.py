import json
import pytest
from chart_recover.semantic import parse_document, bind_documents
from chart_recover.retrieval import CorpusRetriever, plan_queries
from chart_recover.synthetic import collision_demo
from chart_recover.investigate import investigate


def context(**kw):
    return dict(entity='Acme', metric='mrr', currency='USD', aggregation='snapshot',
                series='series_0', source='Chart title Acme MRR, USD',
                periods=['2026-01', '2026-02', '2026-03'], period_source='Visible month labels', **kw)


def geometry(kind='bar'):
    return {'series': [dict(id='series_0', kind=kind, coordinates=[200, 150, 100],
                           points=[{'x': 10, 'y': 200}, {'x': 20, 'y': 150}, {'x': 30, 'y': 100}])]}


def doc(text, **kw):
    return dict(text=text, url='https://example.com/disclosure', **kw)


def test_explicit_dated_claim_becomes_anchor_without_point_number():
    result=bind_documents([doc('Acme MRR was USD 1,000 in January 2026.')],geometry(),context())
    assert result['anchors'][0]['pixel']==200
    assert result['anchors'][0]['low']==1000
    assert result['anchors'][0]['correspondence']['period']=='2026-01'


@pytest.mark.parametrize('text,reason',[
    ('Acme ARR was USD 1000 in January 2026.', 'metric_mismatch'),
    ('Acme MRR was EUR 1000 in January 2026.', 'currency_mismatch'),
    ('Acme MRR was $1000 in January 2026.', 'currency_mismatch'),
    ('Beta MRR was USD 1000 in January 2026.', 'entity_not_bound'),
    ('Acme MRR target USD 1000 in January 2026.', 'target_or_forecast'),
    ('Acme expects MRR will be USD 1000 in January 2026.', 'target_or_forecast'),
    ('Acme MRR was not USD 1000 in January 2026.', 'negation_or_disputed_claim'),
    ('Acme MRR increased by USD 1000 in January 2026.', 'change_or_unit_amount_not_total'),
    ('Acme MRR was USD 1000 in January 2025.', 'period_not_on_chart'),
    ('Acme MRR was USD 1000 in January.', 'missing_year'),
    ('Acme MRR was USD 1000.', 'missing_period'),
    ('Acme MRR was over USD 1000 in January 2026.', 'lower_bound_not_point_value'),
    ('Acme MRR was about USD 1000 in January 2026.', 'approximate_not_point_value'),
    ('Acme MRR was under USD 1000 in January 2026.', 'upper_bound_not_point_value'),
    ('Acme MRR went from USD 1000 to USD 2000 in January 2026.', 'multiple_amounts_in_clause'),
    ('Acme MRR was USD 1000 in January 2026 and February 2026.', 'multiple_periods'),
    ('Acme MRR and ARR were USD 1000 in January 2026.', 'missing_or_ambiguous_metric'),
    ('Acme MRR was USD 1000 on 2026-02-30.', 'invalid_date'),
    ('Acme MRR was USD 1k in January 2026.', 'abbreviated_amount_needs_rounding_policy'),
    ('Acme net revenue was USD 1000 in January 2026.', 'metric_definition_qualifier_needs_review'),
    ('Acme MRR was USD 10 per seat in January 2026.', 'change_or_unit_amount_not_total'),
    ('Acme says Beta MRR was USD 1000 in January 2026.', 'entity_relationship_needs_review'),
    ('Acme MRR was -USD 1000 in January 2026.', 'signed_amount_needs_review'),
    ('Acme MRR was USD 1,00 in January 2026.', 'ambiguous_number_format'),
    ('Acme valuation at 10x MRR was USD 1000 in January 2026.', 'other_financial_measure_in_clause'),
])
def test_unsafe_correspondences_abstain(text,reason):
    result=bind_documents([doc(text)],geometry(),context())
    assert not result['anchors']
    assert reason in result['decisions'][0]['reasons']


def test_rounding_is_an_explicit_interval_assumption():
    result=bind_documents([doc('Acme MRR was USD 2.7k in February 2026.')],geometry(),context(rounding_policy='nearest'))
    assert result['anchors'][0]['low']==2650
    assert result['anchors'][0]['high']==2750
    assert 'rounded' in result['anchors'][0]['assumptions'][1]


def test_publication_date_is_not_silently_used_as_observation_date():
    d=doc('Acme MRR was USD 1000 in December.',created_at='2026-01-02')
    claim=parse_document(d,'Acme')[0]
    assert claim['period']=='2025-12'
    result=bind_documents([d],geometry(),context())
    assert 'inferred_period_needs_review' in result['decisions'][0]['reasons']


def test_monthly_revenue_never_becomes_recurring_revenue():
    d=doc('Acme made USD 1000 in January 2026.')
    claim=parse_document(d,'Acme')[0]
    assert claim['metric']=='revenue' and claim['aggregation']=='monthly_total'
    assert not bind_documents([d],geometry(),context())['anchors']


def test_metadata_entity_needs_provenance_and_cannot_override_other_company():
    d=doc('MRR was USD 1000 in January 2026.',entity='Acme')
    assert not bind_documents([d],geometry(),context())['anchors']
    d['entity_source']='Reviewed source heading Acme'
    assert bind_documents([d],geometry(),context())['anchors']
    d['entity']='Beta'
    assert not bind_documents([d],geometry(),context())['anchors']


def test_calendar_axis_maps_date_without_y_coordinate_or_point_index():
    cfg=context(); del cfg['periods']
    cfg['time_axis']={'scale':'calendar_days','source':'Visible x-axis dates',
                      'ticks':[{'date':'2026-01-01','pixel_x':10},{'date':'2026-01-11','pixel_x':30}]}
    result=bind_documents([doc('Acme MRR was USD 1000 on January 6, 2026.')],geometry('line'),cfg)
    assert result['anchors'][0]['pixel']==pytest.approx(150)
    assert result['anchors'][0]['correspondence']['pixel_x']==pytest.approx(20)
    assert result['anchors'][0]['pixel_error']>=12
    cfg['time_axis']['ticks'].append({'date':'2026-01-21','pixel_x':100})
    assert not bind_documents([doc('Acme MRR was USD 1000 on 2026-01-06.')],geometry('line'),cfg)['anchors']


@pytest.mark.parametrize('change', ['no_series','no_source','wrong_period_count','stacked'])
def test_incomplete_chart_context_abstains(change):
    cfg=context(); geo=geometry()
    if change=='no_series':del cfg['series']
    if change=='no_source':del cfg['source']
    if change=='wrong_period_count':cfg['periods'].pop()
    if change=='stacked':geo=geometry('stacked_bar')
    assert not bind_documents([doc('Acme MRR was USD 1000 in January 2026.')],geo,cfg)['anchors']


def test_corpus_retrieval_and_binding_recovers_with_no_manual_numeric_anchors(tmp_path):
    collision_demo(tmp_path)
    cfg=context(); cfg['periods']=[f'2026-{i:02d}' for i in range(1,7)]
    cfg['period_source']='Known fixture month labels, in bar order'
    corpus=CorpusRetriever([
        doc('Acme MRR was USD 10 in January 2026.'),
        doc('Acme MRR was USD 80 in June 2026.'),
        doc('Acme ARR was USD 960 in June 2026.'),
        doc('Acme MRR target USD 8000 in June 2026.'),
        doc('Beta MRR was USD 99999 in June 2026.'),
    ])
    result=investigate(tmp_path/'scale_1.png',{'kind':'bar','scale':'linear','ocr':False,'chart_context':cfg},tmp_path/'run',retriever=corpus)
    assert [r['status'] for r in result['rounds']]==['needs_evidence_or_review','calibrated']
    final=json.loads((tmp_path/'run'/result['final_result']).read_text())
    assert len(final['evidence_binding']['anchors'])==2
    assert final['recovery'][0]['values']==pytest.approx([10,15,22,31,49,80],abs=.25)
    assert sum(x['status']=='rejected' for x in final['evidence_binding']['decisions'])==2
    assert (tmp_path/'run/retrieval.json').exists()


def test_later_conflicting_retrieved_claim_is_not_hidden_by_early_success(tmp_path):
    collision_demo(tmp_path)
    cfg=context(); cfg['periods']=[f'2026-{i:02d}' for i in range(1,7)]
    corpus=CorpusRetriever([doc('Acme MRR was USD 10 in January 2026.'),doc('Acme MRR was USD 80 in June 2026.'),
                            doc('Acme MRR was USD 800 in June 2026.')])
    result=investigate(tmp_path/'scale_1.png',{'kind':'bar','scale':'linear','ocr':False,'chart_context':cfg},tmp_path/'run',retriever=corpus)
    final=json.loads((tmp_path/'run'/result['final_result']).read_text())
    assert final['recovery'][0]['status']=='inconsistent'


def test_query_plan_uses_only_public_context_and_deduplicates_corpus():
    cfg=context(); cfg['secret']='do-not-transmit'
    assert 'do-not-transmit' not in str(plan_queries(cfg))
    d=doc('Acme MRR was USD 1000 in January 2026.')
    assert len(CorpusRetriever([d,d,doc('Other Acmeish MRR USD 2')]).retrieve(cfg))==1


def test_one_round_limit_does_not_claim_retrieved_evidence_was_checked(tmp_path):
    collision_demo(tmp_path)
    cfg=context();cfg['periods']=[f'2026-{i:02d}' for i in range(1,7)]
    corpus=CorpusRetriever([doc('Acme MRR was USD 10 in January 2026.')])
    result=investigate(tmp_path/'scale_1.png',{'kind':'bar','ocr':False,'chart_context':cfg},tmp_path/'run',max_rounds=1,retriever=corpus)
    assert not result['retrieval_evaluated']


def test_partial_curve_blocks_automatic_calibration(tmp_path):
    from PIL import Image,ImageDraw
    from chart_recover.vision import extract
    im=Image.new('RGB',(400,240),'white')
    ImageDraw.Draw(im).line([(250,200),(390,40)],fill='#4263eb',width=3)
    im.save(tmp_path/'partial.png')
    geo=extract(tmp_path/'partial.png',kind='line',roi=[0,0,400,240])
    assert geo['status']=='needs_review' and geo['quality_issues']
    result=bind_documents([doc('Acme MRR was USD 1000 in January 2026.')],geo,context())
    assert 'geometry_needs_review' in result['decisions'][0]['reasons']
