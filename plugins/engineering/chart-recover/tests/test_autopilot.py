from chart_recover.autopilot import consensus_tokens,bind_bar_labels
from chart_recover.calibrate import calibrate
from chart_recover.layout import detect_bars
from PIL import Image,ImageDraw


def token(text,x,y=210,confidence=95):
    return dict(text=text,confidence=confidence,box=[x,y,40,12])


def card():
    return dict(roi=[20,30,280,180],points=[dict(x=x,y=y,base=180,width=50) for x,y in zip([50,150,250],[130,90,30])])


def tokens():
    return [token('Revenue',30,5),token('Jan',30,190),token('Feb',130,190),token('Mar',230,190),token('$100.00',30),token('$300.00',230)]


def test_ocr_disagreement_does_not_become_anchor():
    agreed,rejected=consensus_tokens([token('$100.00',30)],[token('$700.00',30)])
    assert not agreed and rejected
    agreed,_=consensus_tokens([token('$100.00',30)],[token('$100.00',30,confidence=40)])
    assert not agreed


def test_amount_in_only_second_pass_is_recorded():
    agreed,rejected=consensus_tokens([],[token('$700.00',30)])
    assert not agreed and len(rejected)==1


def test_bar_labels_supply_calibration_without_zero_assumption():
    bound=bind_bar_labels(card(),tokens(),'fixture source',[300,280])
    assert len(bound['anchors'])==2 and bound['labels']==['Jan','Feb','Mar']
    anchors=[dict(a,pixel=card()['points'][a['point_index']]['y']) for a in bound['anchors']]
    r=calibrate([130,90,30],anchors,scale='linear')
    assert r['status']=='calibrated' and abs(r['values'][1]-180)<.01
    assert calibrate([130,90,30],anchors)['status']=='ambiguous_scale'


def test_mixed_currency_and_repeated_categories_abstain():
    ts=tokens();ts[-1]['text']='€300.00'
    assert not bind_bar_labels(card(),ts,'fixture',[300,280])['anchors']
    ts=tokens();ts[2]['text']='Jan'
    assert not bind_bar_labels(card(),ts,'fixture',[300,280])['anchors']


def test_multiple_amounts_in_column_are_not_cherry_picked():
    ts=tokens()+[token('$999.00',30,225)]
    result=bind_bar_labels(card(),ts,'fixture',[300,280])
    assert not result['anchors']


def test_gray_and_colored_bars_form_one_layout_and_two_cards_stay_ambiguous(tmp_path):
    im=Image.new('RGB',(500,500),'white');d=ImageDraw.Draw(im)
    for x,y,color in [(50,120,'#999999'),(150,80,'#999999'),(250,40,'#7788ee')]:d.rectangle([x,y,x+50,210],fill=color)
    path=tmp_path/'bars.png';im.save(path)
    r=detect_bars(path)
    assert len(r['candidates'])==1 and len(r['candidates'][0]['points'])==3
    for x,y in [(50,370),(150,330),(250,290)]:d.rectangle([x,y,x+50,460],fill='#66aa88')
    im.save(path);r=detect_bars(path)
    assert len(r['candidates'])==2 and r['status']=='needs_review'


def test_small_bar_and_jpeg_colors_are_preserved(tmp_path):
    im=Image.new('RGB',(600,400),'white');d=ImageDraw.Draw(im)
    for x,y in [(60,295),(180,220),(300,130),(420,60)]:d.rectangle([x,y,x+60,300],fill='#8389ee')
    path=tmp_path/'bars.jpg';im.save(path,quality=50)
    r=detect_bars(path)
    assert len(r['candidates'])==1 and len(r['candidates'][0]['points'])==4
    assert abs(r['candidates'][0]['points'][0]['y']-295)<=2


def test_batch_preserves_publication_date_and_applies_explicit_defaults(tmp_path,monkeypatch):
    import json
    import chart_recover.investigate as investigation
    manifest=tmp_path/'posts.jsonl'
    manifest.write_text(json.dumps(dict(id='123',url='https://x.com/example/status/123',created_at='2026-07-31T12:00:00Z',images=[{'path':'chart.png'}])))
    seen=[]
    def fake(image,config,output):
        seen.append(config);return dict(status='needs_evidence_or_review',rounds=[])
    monkeypatch.setattr(investigation,'investigate',fake)
    r=investigation.batch(manifest,tmp_path/'batch',defaults=dict(auto_layout=True,scale='unknown'))
    assert r['images']==1 and r['calibrated']==0
    assert seen[0]['auto_layout'] and seen[0]['post_date']=='2026-07-31T12:00:00Z'
