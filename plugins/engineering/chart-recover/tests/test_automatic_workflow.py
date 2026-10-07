import json
import pytest
from chart_recover import automatic


def test_success_does_not_hide_other_reader_conflict(tmp_path,monkeypatch):
    image=tmp_path/'image';image.write_bytes(b'fixture')
    def bars(*args):return dict(status='needs_evidence_or_review',recovery=[dict(status='inconsistent',assumptions=[])],geometry=dict(series=[{}]),trace=[dict(next_actions=['Conflicting amounts'])])
    def cal(*args):return dict(status='calibrated',recovery=[dict(status='calibrated',assumptions=['test'])],geometry=dict(series=[{}]),correspondence=dict(reasons=[]))
    monkeypatch.setattr(automatic,'analyze',bars);monkeypatch.setattr(automatic,'analyze_calendar',cal)
    monkeypatch.setattr(automatic,'analyze_ticks',bars)
    r=automatic.recover(image,{},tmp_path/'result')
    assert r['status']=='has_calibrated_candidates' and r['calibrated_candidates']==1
    assert r['attempts'][0]['outcomes']==['inconsistent'] and r['attempts'][1]['status']=='calibrated'


def test_reader_failure_is_retained_and_other_reader_runs(tmp_path,monkeypatch):
    image=tmp_path/'image';image.write_bytes(b'fixture')
    def fail(*args):raise ValueError('Unsupported layout')
    def cal(*args):return dict(status='needs_evidence_or_review',recovery=[],geometry=dict(series=[]),correspondence=dict(reasons=['Need dates']))
    monkeypatch.setattr(automatic,'analyze',fail);monkeypatch.setattr(automatic,'analyze_calendar',cal)
    monkeypatch.setattr(automatic,'analyze_ticks',cal)
    r=automatic.recover(image,{},tmp_path/'result')
    assert len(r['attempts'])==3 and r['attempts'][0]['status']=='failed' and r['attempts'][1]['next_actions']==['Need dates']
    assert r['attempts'][2]['reader']=='ticks' and r['attempts'][2]['next_actions']==['Need dates']


def test_recovery_batch_rejects_paths_outside_manifest(tmp_path):
    p=tmp_path/'posts.jsonl';p.write_text(json.dumps(dict(id='123',url='https://x.com/test/status/123',images=[dict(path='../outside.png')])))
    with pytest.raises(ValueError,match='outside manifest'):automatic.recover_batch(p,tmp_path/'out')
