"""Regression cases for the semantic, retrieval and calibration PR review."""
import json
from pathlib import Path
import pytest
from chart_recover.calibrate import calibrate
from chart_recover.growth import derive_previous_month_claims
from chart_recover.pipeline import analyze
from chart_recover.retrieval import CorpusRetriever, plan_queries
from chart_recover.semantic import bind_documents, parse_document


def document(text, **kwargs):
    return dict(text=text, url='https://example.com/disclosure', **kwargs)


def context(**kwargs):
    return dict(entity='Acme', metric='mrr', currency='USD', aggregation='snapshot',
                series='series_0', source='Reviewed chart title', periods=['2026-05', '2026-06'],
                period_source='Visible month labels', **kwargs)


def geometry():
    return dict(series=[dict(id='series_0', kind='bar', points=[dict(x=10, y=200), dict(x=20, y=100)], coordinates=[200, 100])])


@pytest.mark.parametrize('text,metadata,literal', [
    ('Beta MRR was USD 1000 in June 2026.', 'Acme', 'Beta'),
    ('Acme MRR was USD 1000 in June 2026.', 'Beta', 'Acme'),
    ("Beta's MRR was USD 1000 in June 2026.", 'Acme', 'Beta'),
    ('Beta was at USD 1000 MRR in June 2026.', 'Acme', 'Beta'),
])
def test_metadata_cannot_replace_a_conflicting_literal_entity(text, metadata, literal):
    result=bind_documents([document(text, entity=metadata, entity_source='Reviewed source heading')], geometry(), context())
    assert not result['anchors']
    assert result['claims'][0]['entity']==literal
    assert 'conflicting_entity_evidence' in result['decisions'][0]['reasons']


def test_entity_alias_can_agree_with_provenance():
    d=document('Acme Labs MRR was USD 1000 in June 2026.', entity='Acme', entity_source='Reviewed source heading')
    assert bind_documents([d], geometry(), context(aliases=['Acme Labs']))['anchors']


@pytest.mark.parametrize('text', [
    "Acme MRR hasn't reached USD 1000 in June 2026.", "Acme MRR doesn’t equal USD 1000 in June 2026.",
    "Acme MRR can't be USD 1000 in June 2026.", "Acme MRR won't be USD 1000 in June 2026.",
    'Was Acme MRR USD 1000 in June 2026?', 'Acme MRR was USD 1000 in June 2026?',
    'Did Acme reach USD 1000 MRR in June 2026',
])
def test_nonassertions_cannot_bind(text):
    result=bind_documents([document(text)], geometry(), context())
    assert result['claims'] and not result['anchors']
    assert set(result['decisions'][0]['reasons']) & {'negation_or_disputed_claim', 'interrogative_claim'}


@pytest.mark.parametrize('qualifier', ['cumulative', 'lifetime', 'all-time', 'since launch'])
def test_recurring_metric_cumulative_qualifiers_are_not_snapshots(qualifier):
    result=bind_documents([document(f'Acme MRR {qualifier} was USD 1000 in June 2026.')], geometry(), context())
    assert result['claims'][0]['aggregation']=='cumulative'
    assert not result['anchors'] and 'aggregation_mismatch' in result['decisions'][0]['reasons']


def derive(suffix):
    d=document('Acme MRR was USD 110 in June 2026.\n'+suffix)
    return derive_previous_month_claims(d, parse_document(d, 'Acme'))


@pytest.mark.parametrize('suffix', [
    'MRR was up 10% on last month for Beta.', 'MRR was up 10% on last month, allegedly.',
    'MRR was up 10% on last month?', 'MRR was up 10% on last month, if the estimate is accurate.',
])
def test_growth_requires_whole_unqualified_clause(suffix):
    result=derive(suffix)
    assert not result['claims']
    assert result['decisions'] and result['decisions'][0]['status']=='rejected'


def test_vs_abbreviation_remains_one_growth_clause():
    result=derive('MRR was up 10% vs. last month.')
    assert result['claims'][0]['period']=='2026-05'
    assert result['claims'][0]['value']==pytest.approx(100)


def test_growth_period_is_derived_with_explicit_antecedent_policy():
    d=document('Acme MRR was USD 110 in June 2026.\nMRR was up 10% on last month.')
    result=bind_documents([d], geometry(), context())
    derived=next(c for c in result['claims'] if c.get('derivation'))
    assert derived['period_basis']=='derived_previous_month'
    assert derived['derivation']['current_period_basis']=='explicit'
    assert len(result['anchors'])==2
    assert 'derived_previous_month' in result['anchors'][1]['assumptions']
    d['text']=d['text'].replace('June 2026', 'June'); d['created_at']='2026-06-30'
    assert not bind_documents([d], geometry(), context())['anchors']
    assert len(bind_documents([d], geometry(), context(allow_inferred_periods=True))['anchors'])==2


@pytest.mark.parametrize('index', [1.9, -0.9, True, '1', float('nan'), float('inf')])
def test_fractional_or_non_numeric_point_index_is_rejected(tmp_path, index):
    root=Path(__file__).resolve().parent.parent/'skills/chart-recover/scripts/chart_recover/assets/examples/line'
    cfg=json.loads((root/'config.json').read_text(encoding='utf-8')); cfg['ocr']=False
    cfg['anchors'][0].pop('pixel', None); cfg['anchors'][0]['point_index']=index
    with pytest.raises(ValueError, match='point_index must be an integer'):
        analyze(root/'chart.png', cfg, tmp_path/'out')


def test_exact_anchor_tolerances_can_bound_close_anchor_positions():
    anchors=[dict(pixel=p, value=v, pixel_error=0, source='Reviewed label', matched=True) for p,v in [(100, 100), (99, 200)]]
    result=calibrate([99.5], anchors, scale='linear', pixel_error=2.5)
    assert result['status']=='calibrated'
    assert result['values']==pytest.approx([150])
    assert result['lower'][0]<=150<=result['upper'][0]


def test_overlapping_anchor_positions_remain_unidentifiable():
    anchors=[dict(pixel=p, value=v, pixel_error=1, source='Reviewed label', matched=True) for p,v in [(100, 100), (99, 200)]]
    assert calibrate([99.5], anchors, scale='linear', pixel_error=0)['status']=='unidentifiable'


@pytest.mark.parametrize('field,value', [('pixel', float('nan')), ('pixel', float('inf')), ('pixel_error', -1),
    ('pixel_error', float('nan')), ('pixel_error', float('inf')), ('pixel_error', None)])
def test_invalid_baseline_is_rejected_before_optimization(field, value):
    anchor=dict(pixel=10, value=100, source='Reviewed label', matched=True)
    baseline=dict(pixel=100, pixel_error=0, source='Reviewed zero tick', verified=True); baseline[field]=value
    with pytest.raises(ValueError, match='Baseline needs a finite pixel and finite nonnegative pixel_error'):
        calibrate([50], [anchor], scale='linear', baseline=baseline)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), None])
def test_invalid_anchor_tolerance_is_rejected_before_optimization(value):
    anchors=[dict(pixel=p, value=v, pixel_error=0, source='Reviewed label', matched=True) for p,v in [(100, 100), (99, 200)]]
    anchors[0]['pixel_error']=value
    with pytest.raises(ValueError, match='Anchor pixel_error must be finite and nonnegative'):
        calibrate([99.5], anchors, scale='linear')


def test_utf8_corpus_does_not_depend_on_locale(tmp_path, monkeypatch):
    path=tmp_path/'corpus.jsonl'
    path.write_text(json.dumps(document('Café earned EUR 100 in June 2026.'), ensure_ascii=False)+'\n', encoding='utf-8')
    original=Path.open
    def locale_open(self, mode='r', buffering=-1, encoding=None, errors=None, newline=None):
        return original(self, mode, buffering, encoding=encoding or 'ascii', errors=errors, newline=newline)
    monkeypatch.setattr(Path, 'open', locale_open)
    result=CorpusRetriever.from_jsonl(path).retrieve(dict(entity='Café', metric='revenue'))
    assert result[0]['text']=='Café earned EUR 100 in June 2026.'


@pytest.mark.parametrize('verb', ['made', 'generated', 'earned'])
def test_revenue_retrieval_shares_parser_fallback_vocabulary(verb):
    cfg=dict(entity='Acme', metric='revenue')
    assert verb in plan_queries(cfg)[0]
    disclosures=[document(f'Acme {verb} USD 100 in June 2026.')]
    distractions=[dict(document('Acme launched a new feature.'), url=f'https://example.com/{i:02d}') for i in range(30)]
    result=CorpusRetriever(distractions+disclosures).retrieve(cfg, limit=1)
    assert result[0]['text']==disclosures[0]['text']
