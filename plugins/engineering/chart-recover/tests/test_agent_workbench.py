import base64
import io
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from chart_recover.server import Handler


def request(payload,path='/api/analyze',origin=None):
    raw=json.dumps(payload).encode();h=Handler.__new__(Handler)
    h.path=path;h.headers={'Content-Length':str(len(raw))}
    if origin:h.headers['Origin']=origin
    h.server=SimpleNamespace(server_port=8769);h.rfile=io.BytesIO(raw)
    responses=[];h._send=lambda data,status=200,**kwargs:responses.append((status,data))
    h.do_POST();return responses[0]


def fixture_agent(monkeypatch,kinds=('first_customer',),capture=None):
    def investigate(path,context,output,strict_only=False):
        if capture is not None:capture.update(context=context,strict=strict_only)
        readers=output/'readers';readers.mkdir(parents=True)
        base=dict(status='needs_evidence_or_review',geometry=dict(series=[dict(id='series_0',points=[dict(x=1,y=2)])]),recovery=[],reasons=['No matching evidence.'])
        attempts=[]
        for name in ('bars','calendar','ticks'):
            p=readers/name;p.mkdir();(p/'result.json').write_text(json.dumps(base));(p/'overlay.png').write_bytes(b'overlay');(p/'data.csv').write_text('value\n')
            attempts.append(dict(reader=name,status=base['status'],result=f'{name}/result.json'))
        (readers/'workflow.json').write_text(json.dumps(dict(attempts=attempts)))
        conditional=[]
        if not strict_only:
            for name in kinds:
                folder='conditional-'+name.replace('_','-');p=output/folder;p.mkdir()
                r=dict(base,status='conditional_calibration',date_assignment='unassigned',assumptions=['Test correspondence.'],
                       recovery=[dict(series='series_0',values=[42.],lower=[40.],upper=[44.],status='conditional_calibration')])
                if name=='first_customer':r['evidence_strength']='caption_and_headline_unchecked'
                (p/'result.json').write_text(json.dumps(r));(p/'overlay.png').write_bytes(name.encode());(p/'data.csv').write_text('value\n42\n')
                conditional.append(dict(reader=name,status=r['status'],result=f'{folder}/result.json',csv=f'{folder}/data.csv',overlay=f'{folder}/overlay.png'))
        return dict(strict_candidates=0,conditional_candidates=len(conditional),conditional_results=conditional,steps=[])
    monkeypatch.setattr('chart_recover.agent.investigate_image',investigate)


@pytest.mark.parametrize('kind',['first_customer','external_daily_revenue','comparison_totals'])
def test_noncalendar_result_without_trace_can_be_selected(monkeypatch,kind):
    fixture_agent(monkeypatch,(kind,))
    status,r=request(dict(image=base64.b64encode(b'image').decode(),config=dict(reader='agent')))
    assert status==200
    assert r['status']=='conditional_calibration' and r['recovery'][0]['values']==[42.]
    assert r['selected_view'].startswith('conditional-')
    assert r['trace']==[]
    assert len(r['agent_views'])==4


def test_all_candidates_and_failures_are_available_for_selection(monkeypatch):
    fixture_agent(monkeypatch,('first_customer','external_daily_revenue'))
    status,r=request(dict(image=base64.b64encode(b'image').decode(),config=dict(reader='agent')))
    assert status==200 and len(r['agent_views'])==5
    assert {v['reader'] for v in r['agent_views']}=={'bars','calendar','ticks','first_customer','external_daily_revenue'}
    for v in r['agent_views']:assert 'result' in v and 'csv' in v and 'overlay' in v
    assert sum(v['status']=='needs_evidence_or_review' for v in r['agent_views'])==3


def test_step_daily_download_is_kept_with_its_selected_reader(monkeypatch):
    fixture_agent(monkeypatch,('external_daily_revenue',))
    import chart_recover.agent as module
    base_agent=module.investigate_image
    daily='proposed_date,conditional_value,date_assignment\n2026-09-04,110,proposed_unverified\n'
    def investigate(path,context,output,strict_only=False):
        agent=base_agent(path,context,output,strict_only)
        (output/'conditional-external-daily-revenue/daily.csv').write_text(daily)
        return agent
    monkeypatch.setattr(module,'investigate_image',investigate)
    status,r=request(dict(image=base64.b64encode(b'image').decode(),config=dict(reader='agent')))
    assert status==200
    assert r.get('daily_csv')==daily
    assert r['csv']=='value\n42\n'
    selected=next(v for v in r['agent_views'] if v['id']==r['selected_view'])
    assert selected['daily_csv']==daily
    assert all(not v.get('daily_csv') for v in r['agent_views'] if v['id']!=r['selected_view'])


def test_browser_evidence_is_allowlisted_and_snapshot_is_request_scoped(monkeypatch):
    capture={};fixture_agent(monkeypatch,capture=capture)
    payload=dict(reader='agent',source='https://x.com/u/status/1',post_text='caption',
                 evidence_profile_url='https://trustmrr.com/startup/example-business',evidence_profile_text='saved public text',
                 evidence_profile_snapshot='/private/forbidden',evidence_cache='/private/cache',retrieval={'path':'/private/corpus'},
                 discover_evidence=False)
    status,r=request(dict(image=base64.b64encode(b'image').decode(),config=payload))
    assert status==200
    context=capture['context'];assert context['post_text']=='caption'
    assert context['evidence_profile_url']==payload['evidence_profile_url']
    assert context['evidence_profile_snapshot']!='/private/forbidden'
    snapshot=Path(context['evidence_profile_snapshot'])
    assert snapshot.name=='profile.md'
    assert not snapshot.exists()  # temporary request files are removed
    json.dumps(context)  # the workflow persists its configuration as JSON
    assert 'evidence_cache' not in context and 'retrieval' not in context


@pytest.mark.parametrize('extra',[
    dict(discover_evidence='false'),dict(post_text=['not','text']),
    dict(evidence_profile_text='text without a URL'),dict(post_text='x'*20001),
    dict(evidence_profile_url='http://127.0.0.1/private'),
    dict(discover_evidence=True,evidence_profile_url='https://trustmrr.com/startup/example-business')])
def test_invalid_evidence_settings_are_rejected_before_agent(monkeypatch,extra):
    monkeypatch.setattr('chart_recover.agent.investigate_image',lambda *a,**k:pytest.fail('invalid input reached agent'))
    status,_=request(dict(image=base64.b64encode(b'image').decode(),config=dict(reader='agent',**extra)))
    assert status==400


def test_public_import_uses_collector_and_preserves_caption_and_source(monkeypatch):
    import chart_recover.collect as collect
    class Collector:
        def lookup(self,url):
            assert url=='https://x.com/u/status/123'
            return [dict(id='123',url=url,text='Original caption',created_at='2026-01-01T00:00:00Z',media=[])]
    def save(posts,folder,download=True,*,max_total_bytes=None):
        assert download and max_total_bytes==20_000_000
        from PIL import Image
        Image.new('RGB',(2,2)).save(folder/'image.png')
        (folder/'posts.jsonl').write_text(json.dumps(dict(posts[0],images=[dict(path='image.png',sha256='fixture')]))+'\n')
    monkeypatch.setattr(collect,'PublicXCollector',Collector);monkeypatch.setattr(collect,'save_posts',save)
    status,r=request(dict(url='https://x.com/u/status/123'),'/api/import-post')
    assert status==200 and r['post']['text']=='Original caption'
    assert r['post']['url']=='https://x.com/u/status/123'
    assert base64.b64decode(r['images'][0]['image']).startswith(b'\x89PNG')
    assert r['images'][0]['mime_type']=='image/png'


def test_cross_origin_import_is_rejected(monkeypatch):
    monkeypatch.setattr('chart_recover.collect.PublicXCollector',lambda:pytest.fail('foreign origin reached collector'))
    assert request(dict(url='https://x.com/u/status/123'),'/api/import-post','https://foreign.example')[0]==403


def test_comparison_example_supplies_image_and_provenance_without_numeric_anchors(tmp_path,monkeypatch):
    import chart_recover.server as module
    image=tmp_path/'examples/comparison/chart.png';image.parent.mkdir(parents=True);image.write_bytes(b'synthetic-image')
    (image.parent/'config.json').write_text(json.dumps(dict(reader='agent',source='https://example.com/synthetic-comparison')))
    monkeypatch.setattr(module,'ASSETS',tmp_path)
    h=Handler.__new__(Handler);h.path='/api/comparison-example';responses=[]
    h._send=lambda data,*a,**k:responses.append(data);h.do_GET()
    assert 'image' in responses[0]
    assert base64.b64decode(responses[0]['image'])==b'synthetic-image'
    assert set(responses[0]['config'])=={'reader','source'}


def test_comparison_benchmark_keeps_versions_and_assumption_failures_visible(tmp_path,monkeypatch):
    import chart_recover.server as module
    for version,passed in [('v1',8),('v2',15),('v3',18)]:
        folder=tmp_path/f'artifacts/comparison-totals-heldout-{version}';folder.mkdir(parents=True)
        stress=[dict(control='log_axis',status='conditional_calibration',passed=False),
                dict(control='independent_axes',status='conditional_calibration' if version=='v3' else 'needs_evidence_or_review',passed=False)] if version!='v1' else []
        (folder/'summary.json').write_text(json.dumps(dict(charts=60,passed=passed,abstained=60-passed,returned_failures=0,controls=stress)))
    monkeypatch.setattr(module,'ROOT',tmp_path)
    h=Handler.__new__(Handler);h.path='/api/benchmark';responses=[]
    h._send=lambda data,*a,**k:responses.append(data);h.do_GET()
    current=responses[0]['comparison_totals']
    assert current['passed']==18 and current['charts']==60
    assert current['assumption_stress_cases']==2 and current['assumption_stress_failures']==2
    assert [s['passed'] for s in responses[0]['comparison_studies']]==[8,15,18]


def test_rejected_external_proposal_and_its_source_evidence_remain_available(monkeypatch):
    fixture_agent(monkeypatch,kinds=())
    import chart_recover.agent as module
    base_agent=module.investigate_image
    def investigate(path,context,output,strict_only=False):
        agent=base_agent(path,context,output,strict_only)
        folder=output/'conditional-external';folder.mkdir()
        r=dict(status='needs_evidence_or_review',geometry=dict(series=[]),recovery=[],reasons=['Checking failed.'])
        (folder/'result.json').write_text(json.dumps(r));(folder/'overlay.png').write_bytes(b'overlay');(folder/'data.csv').write_text('value\n')
        evidence=output/'external-profile';evidence.mkdir();(evidence/'profile.json').write_text(json.dumps(dict(source='https://trustmrr.com/startup/example-business')))
        agent['steps']=[dict(action='external_public_profile',result='conditional-external/result.json',evidence='external-profile/profile.json')]
        return agent
    monkeypatch.setattr(module,'investigate_image',investigate)
    status,r=request(dict(image=base64.b64encode(b'image').decode(),config=dict(reader='agent')))
    assert status==200
    v=next(v for v in r['agent_views'] if v['reader']=='external_daily_revenue')
    assert v['status']=='needs_evidence_or_review' and v['result']['recovery']==[]
    assert r['agent_evidence']['documents']['external-profile/profile.json']['source'].endswith('/example-business')


def test_strict_policy_is_passed_with_public_context(monkeypatch):
    capture={};fixture_agent(monkeypatch,capture=capture)
    status,r=request(dict(image=base64.b64encode(b'image').decode(),config=dict(reader='agent',strict_only=True,
        source='https://x.com/u/status/1',post_text='Got my first paying customer.',discover_evidence=True)))
    assert status==200 and capture['strict'] is True
    assert capture['context']['discover_evidence'] is True
    assert r['agent']['conditional_candidates']==0
