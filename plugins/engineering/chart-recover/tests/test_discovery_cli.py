import json
from pathlib import Path
import pytest
from chart_recover.cli import main


def test_discover_agent_cli_connects_collection_and_investigation(tmp_path,monkeypatch,capsys):
    calls=[]
    def collect(output,limit,download=True):
        assert download and limit==2
        p=Path(output);p.mkdir();(p/'posts.jsonl').write_text('')
        return dict(discovered_urls=2,records=[])
    def investigate(manifest,output,strict_only,discover_evidence,evidence_cache):
        calls.append((manifest,output,strict_only,discover_evidence,evidence_cache))
        return dict(images=0,images_with_strict_candidates=0,images_with_conditional_candidates=0,results=[])
    monkeypatch.setattr('chart_recover.discovery.discover',collect)
    monkeypatch.setattr('chart_recover.agent.investigate_batch',investigate)
    out=tmp_path/'run';monkeypatch.setattr('sys.argv',['chart-recover','discover','--limit','2','--agent','--discover-evidence','--out',str(out)])
    main();result=json.loads(capsys.readouterr().out)
    assert result==json.loads((out/'workflow.json').read_text())
    assert calls==[(out/'posts.jsonl',out/'agent',False,True,None)]


@pytest.mark.parametrize('flags',[
    ['--agent','--recover'],['--agent','--no-download'],['--discover-evidence'],
    ['--strict-only'],['--agent','--scale','linear']])
def test_invalid_discovery_flags_stop_before_collection(flags,monkeypatch):
    monkeypatch.setattr('chart_recover.discovery.discover',lambda *a,**k:pytest.fail('invalid flags reached network collection'))
    monkeypatch.setattr('sys.argv',['chart-recover','discover',*flags])
    with pytest.raises(SystemExit) as error:main()
    assert error.value.code==2
