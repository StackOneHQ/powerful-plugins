import json
from pathlib import Path
from chart_recover.pipeline import analyze
from chart_recover.synthetic import collision_demo,generate_one
from chart_recover.evidence import claims_from_text,match_reference


def test_identical_images_different_values(tmp_path):
    r=collision_demo(tmp_path);assert r['identical_images']
    assert r['examples'][0]['values']!=r['examples'][1]['values']
    a=analyze(tmp_path/'scale_1.png',{'kind':'bar','ocr':False},tmp_path/'out')
    assert len(a['geometry']['series'][0]['points'])==6
    assert a['recovery'][0]['status']=='unidentifiable'
    assert a['recovery'][0]['values'] is None


def test_synthetic_calibrated_chart_pipeline(tmp_path):
    root=Path(__file__).resolve().parent.parent
    config=json.loads((root/'skills/chart-recover/scripts/chart_recover/assets/examples/line/config.json').read_text())
    r=analyze(root/'skills/chart-recover/scripts/chart_recover/assets/examples/line/chart.png',config,tmp_path)
    assert r['status']=='calibrated'
    assert len(r['geometry']['series'])==1
    assert abs(r['recovery'][0]['values'][-1]-config['anchors'][-1]['value'])<1
    assert (tmp_path/'data.csv').exists() and (tmp_path/'overlay.png').exists()


def test_money_leads_do_not_become_anchors():
    claims=claims_from_text('MRR is $2.7k. We grew 8x. ARR target $1M.','https://example.com')
    assert claims[0]['value']==2700
    assert all(not c['matched'] for c in claims)
    assert any(c.get('ratio')==8 for c in claims)


def test_shape_correlation_cannot_establish_identity():
    r=match_reference([0,1,4,9,16],[{'id':'same-shape','values':[10,20,50,100,170],'source':'test'},
                                  {'id':'wrong','values':[16,9,4,1,0]}])
    assert r[0]['id']=='same-shape' and r[0]['status']=='candidate_only'
    assert abs(r[0]['correlation']-1)<1e-6


def test_evidence_loop_stops_after_sufficient_evidence(tmp_path):
    from chart_recover.investigate import investigate
    root=Path(__file__).resolve().parent.parent
    cfg=json.loads((root/'skills/chart-recover/scripts/chart_recover/assets/examples/line/config.json').read_text())
    anchors=cfg.pop('anchors');cfg['evidence_rounds']=[{'anchors':[a]} for a in anchors]
    r=investigate(root/'skills/chart-recover/scripts/chart_recover/assets/examples/line/chart.png',cfg,tmp_path)
    assert [x['status'] for x in r['rounds']]==['needs_evidence_or_review','needs_evidence_or_review','calibrated']
    assert (tmp_path/r['final_result']).exists()


def test_evidence_loop_stops_on_no_new_information(tmp_path):
    from chart_recover.investigate import investigate
    root=Path(__file__).resolve().parent.parent
    r=investigate(root/'skills/chart-recover/scripts/chart_recover/assets/examples/line/chart.png',{'kind':'line','ocr':False,'evidence_rounds':[{}]},tmp_path)
    assert r['rounds'][-1]['reason']=='No new evidence'
