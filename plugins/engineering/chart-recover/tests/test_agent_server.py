import base64
import io
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from chart_recover.server import Handler


@pytest.mark.parametrize('strict',[False,True])
def test_agent_api_preserves_reader_evidence_and_respects_strict_policy(tmp_path,monkeypatch,strict):
    def investigate(path,context,output,strict_only=False):
        assert strict_only is strict
        assert set(context)=={'source'}  # manual anchors and file paths do not reach the agent
        readers=output/'readers';readers.mkdir(parents=True)
        result=dict(status='needs_evidence_or_review',image=str(path),geometry=dict(image=str(path),series=[dict(points=[dict(x=0,y=1)])]),
                    recovery=[dict(status='needs_correspondence',values=None)],trace=[])
        for name in ('bars','calendar','ticks'):
            folder=readers/name;folder.mkdir();(folder/'result.json').write_text(json.dumps(result));(folder/'overlay.png').write_bytes(b'overlay');(folder/'data.csv').write_text('value\n\n')
        (readers/'workflow.json').write_text(json.dumps(dict(attempts=[dict(reader=n,status='needs_evidence_or_review',result=f'{n}/result.json') for n in ('bars','calendar','ticks')])))
        conditional=[]
        if not strict:
            folder=output/'conditional-calendar';folder.mkdir();candidate=dict(result,status='conditional_calibration',recovery=[dict(status='conditional_calibration',values=[42])])
            (folder/'result.json').write_text(json.dumps(candidate));(folder/'overlay.png').write_bytes(b'candidate');(folder/'data.csv').write_text('conditional_value,plot_date\n42,\n');conditional=[dict(result='conditional-calendar/result.json')]
        return dict(strict_candidates=0,conditional_candidates=len(conditional),conditional_results=conditional,steps=[])
    monkeypatch.setattr('chart_recover.agent.investigate_image',investigate)
    payload=json.dumps(dict(image=base64.b64encode(b'fixture image').decode(),config=dict(reader='agent',source='https://example.com/source',strict_only=strict,anchors=[dict(value=999)],retrieval=dict(path='/private/not-allowed')))).encode()
    handler=Handler.__new__(Handler);handler.path='/api/analyze';handler.headers={'Content-Length':str(len(payload))};handler.rfile=io.BytesIO(payload)
    responses=[];handler._send=lambda data,status=200,**kwargs:responses.append((status,data))
    handler.do_POST();status,result=responses[0]
    assert status==200
    assert set(result['agent_evidence']['reader_results'])=={'bars','calendar','ticks'}
    assert result['image']=='local upload'
    assert result['status']==('needs_evidence_or_review' if strict else 'conditional_calibration')
    assert result['recovery'][0]['values']==(None if strict else [42])
