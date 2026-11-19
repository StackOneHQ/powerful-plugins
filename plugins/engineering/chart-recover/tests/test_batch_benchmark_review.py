import importlib
import json
import sys
from types import SimpleNamespace

import pytest


def manifest_with_two_images(tmp_path):
    path=tmp_path/'posts.jsonl'
    path.write_text(json.dumps(dict(id='1',url='https://example.com/post',images=[{'path':'bad.png'},{'path':'good.png'}]))+'\n',encoding='utf-8')
    return path


@pytest.mark.parametrize('error', [ValueError('bad input'),OSError('unreadable image'),RuntimeError('rate limit')])
def test_agent_batch_preserves_failed_image_and_continues(tmp_path,monkeypatch,error):
    from chart_recover import agent
    def investigate(path,*args):
        if path.name=='bad.png':raise error
        return dict(status='needs_evidence_or_review',strict_candidates=0,conditional_candidates=0)
    monkeypatch.setattr(agent,'investigate_image',investigate)
    result=agent.investigate_batch(manifest_with_two_images(tmp_path),tmp_path/'out')
    assert [r['status'] for r in result['results']]==['failed','needs_evidence_or_review']
    assert json.loads((tmp_path/'out/batch.json').read_text())==result


def test_evidence_batch_continues_after_unavailable_api(tmp_path,monkeypatch):
    from chart_recover import investigate
    def run(path,*args):
        if path.name=='bad.png':raise RuntimeError('API access unavailable')
        return dict(status='calibrated')
    monkeypatch.setattr(investigate,'investigate',run)
    result=investigate.batch(manifest_with_two_images(tmp_path),tmp_path/'out')
    assert result['calibrated']==1
    assert [r['status'] for r in result['results']]==['failed','calibrated']


def test_empty_benchmark_has_no_coverage_or_vacuous_success(tmp_path):
    from chart_recover.benchmark import run_benchmark
    result=run_benchmark(tmp_path,per_kind=0,render_holdout=False)
    assert result['mean_interval_coverage'] is None
    assert result['all_evaluated_unanchored_series_abstained'] is False
    json.dumps(result,allow_nan=False)


def test_automatic_benchmark_preserves_nonempty_output(tmp_path):
    from chart_recover.automatic_benchmark import run
    marker=tmp_path/'summary.json';marker.write_text('previous run')
    with pytest.raises(ValueError,match='fresh empty'):
        run(tmp_path,per_renderer=0)
    assert marker.read_text()=='previous run'


def test_aggregate_benchmark_requires_an_explicit_output():
    from chart_recover.aggregate_benchmark import run
    with pytest.raises(ValueError,match='explicit output'):
        run(per_kind=0)


def test_frozen_package_resolves_dependencies_from_snapshot(tmp_path):
    from chart_recover.step_benchmark import frozen_package
    (tmp_path/'__init__.py').write_text('')
    (tmp_path/'dependency.py').write_text('VALUE = "frozen"\n')
    (tmp_path/'reader.py').write_text('from .dependency import VALUE\n')
    with frozen_package(tmp_path) as namespace:
        reader=importlib.import_module(namespace+'.reader')
        assert reader.VALUE=='frozen'
        assert str(tmp_path) in reader.__file__
        assert str(tmp_path) in sys.modules[namespace+'.dependency'].__file__
    assert not any(k==namespace or k.startswith(namespace+'.') for k in sys.modules)


@pytest.mark.parametrize('fails',[False,True])
def test_step_study_withholds_truth_and_restores_it_even_on_failure(tmp_path,fails):
    from chart_recover.step_benchmark import recover_withheld
    truth=tmp_path/'truth.json';raw=b'{"private": 42}'
    truth.write_bytes(raw);seen=[]
    def read(image,*args):
        assert not truth.exists()
        seen.append(image)
        if fails:raise ValueError('reader failed')
        return {'status':'needs_evidence_or_review'}
    readers={name:SimpleNamespace(recover_external=read) for name in ('baseline','revised')}
    if fails:
        with pytest.raises(ValueError,match='reader failed'):recover_withheld(tmp_path,{},readers)
    else:
        results,private=recover_withheld(tmp_path,{},readers)
        assert len(results)==len(seen)==2 and private=={'private':42}
    assert truth.read_bytes()==raw
