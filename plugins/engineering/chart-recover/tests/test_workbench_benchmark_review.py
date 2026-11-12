import copy
import importlib
import json
import sys
from pathlib import Path

import pytest

from test_agent_workbench import request


@pytest.mark.parametrize('payload',[[],None,42,'text'])
@pytest.mark.parametrize('endpoint',['/api/analyze','/api/import-post'])
def test_api_rejects_nonobject_json_as_client_error(payload,endpoint):
    status,result=request(payload,endpoint)
    assert status==400 and 'object' in result['error']


def test_portable_evidence_removes_nested_paths_but_keeps_urls(tmp_path):
    from chart_recover.server import portable_evidence
    value={'config':{'evidence_profile_snapshot':str(tmp_path/'profile.md')},
           'workflow':{'image':str(tmp_path/'input.image')},
           'documents':[{'path':r'C:\Users\Person\private\file.md',
                         'source':'https://example.com/source',
                         'reason':'OCR of '+str(tmp_path/'input.image')}],
           'result':'readers/calendar/result.json'}
    result=portable_evidence(value,tmp_path)
    encoded=json.dumps(result)
    assert str(tmp_path) not in encoded and 'Person' not in encoded
    assert result['documents'][0]['source']=='https://example.com/source'
    assert result['result']=='readers/calendar/result.json'
    assert value['workflow']['image']==str(tmp_path/'input.image')


@pytest.mark.parametrize('module',['benchmark','aggregate_benchmark','calendar_benchmark','automatic_benchmark','comparison_benchmark'])
def test_evaluations_refuse_stale_output_before_generation(tmp_path,module):
    benchmark=importlib.import_module('chart_recover.'+module)
    marker=tmp_path/'earlier-result.json';marker.write_text('keep')
    run=benchmark.run_benchmark if module=='benchmark' else benchmark.run
    with pytest.raises(ValueError,match='fresh'):
        run(output=tmp_path)
    assert marker.read_text()=='keep' and len(list(tmp_path.iterdir()))==1


@pytest.mark.parametrize('module',['tick_benchmark','evidence_discovery_benchmark'])
def test_ocr_evaluation_records_no_cases_when_executable_missing(tmp_path,monkeypatch,module):
    from chart_recover import benchmark_support
    monkeypatch.setattr(benchmark_support.shutil,'which',lambda _:None)
    out=tmp_path/'evaluation'
    with pytest.raises(ValueError,match='requires Tesseract'):
        importlib.import_module('chart_recover.'+module).run(out)
    assert not out.exists()


@pytest.mark.parametrize('count',['0','-1'])
def test_cli_rejects_empty_benchmark_protocol(tmp_path,monkeypatch,count):
    from chart_recover.cli import main
    monkeypatch.setattr(sys,'argv',['chart-recover','benchmark','--per-kind',count,'--out',str(tmp_path/'out')])
    with pytest.raises(SystemExit) as error:main()
    assert error.value.code==2 and not (tmp_path/'out').exists()


def test_evidence_rounds_continue_through_multiple_empty_packets(tmp_path,monkeypatch):
    from chart_recover import investigate
    def analyze(image,config,output):
        status='calibrated' if config.get('anchors') else 'needs_evidence_or_review'
        return {'status':status,'recovery':[{'status':status}], 'trace':[{'next_actions':[]}]}
    monkeypatch.setattr(investigate,'analyze',analyze)
    result=investigate.investigate('unused.png',{'evidence_rounds':[{}, {}, {'anchors':[{'value':1}]}]},tmp_path)
    assert result['status']=='calibrated' and result['final_result']=='round-3/result.json'
    assert [r.get('action') for r in result['rounds'][1:3]]==['skip','skip']


def test_agent_batch_supports_single_image_and_reserves_stdout_for_json(tmp_path,monkeypatch,capsys):
    from chart_recover import agent
    monkeypatch.setattr(agent,'investigate_image',lambda *a:dict(status='needs_evidence_or_review',strict_candidates=0,conditional_candidates=0))
    path=tmp_path/'posts.jsonl';path.write_text(json.dumps({'id':'123','url':'https://example.com/post','image':'one.png'})+'\n')
    result=agent.investigate_batch(path,tmp_path/'results')
    output=capsys.readouterr()
    assert result['images']==1 and output.out=='' and '123' in output.err


@pytest.mark.parametrize('change',['complete','missing','leaked','duplicate'])
def test_calendar_scoring_requires_visible_coverage_and_no_truth_leak(change):
    from chart_recover.calendar_benchmark import score
    values=[100.,200.,300.];points=[{'x':x} for x in (10,20,30)]
    dates=['2026-09-01','2026-09-02','2026-09-03']
    truth=dict(seed=1,renderer='fixture',style='light',kind='line',year=2026,month=9,
               days=3,values=values,points=points,hidden_indices=[1],
               cells=[{'date':date,'amount_visible':i!=1} for i,date in enumerate(dates)])
    observations=[{'date':dates[i],'value':values[i]} for i in (0,2)]
    if change=='missing':observations.pop()
    elif change=='leaked':observations.append({'date':dates[1],'value':values[1]})
    elif change=='duplicate':observations.append(copy.deepcopy(observations[0]))
    result=dict(status='calibrated',calendar={'observations':observations},geometry={'series':[{'points':points}]},
                recovery=[dict(values=values,lower=values,upper=values,scale='linear')])
    assert score(result,truth)['success']==(change=='complete')


def test_pillow_truncated_bars_end_at_visible_plot_boundary(tmp_path):
    from chart_recover.synthetic import generate_one
    truth=generate_one(tmp_path,31001,'bar','linear','truncated','pillow')
    from PIL import Image
    with Image.open(tmp_path/'chart.png') as image:
        # The visible baseline stays inside the image rather than extrapolating
        # the hidden numerical zero past the bottom of the plotting area.
        assert 0<truth['baseline_pixel']<image.height
