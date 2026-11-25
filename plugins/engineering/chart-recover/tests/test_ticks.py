import numpy as np
import pytest
from PIL import Image,ImageDraw,ImageFont
from chart_recover.tick_recovery import parse_tick,bind_ticks,horizontal_gridlines,trace_axis_curve,analyze_ticks


@pytest.mark.parametrize('text,value,unit',[('$5K',5000,'$'),('€1.2m',1200000,'€'),('25%',25,'%'),('-12.5',-12.5,'unspecified'),('£2,000',2000,'£')])
def test_tick_units(text,value,unit):
    assert parse_tick(text)['value']==value
    assert parse_tick(text)['unit']==unit


@pytest.mark.parametrize('text',['Jul 12','1,23','$10%','NaN','4OO','$-','1.2.3'])
def test_tick_grammar_does_not_repair_numbers(text):assert parse_tick(text) is None


def fixture(tmp_path,values=(400,300,200,100,0),second=False):
    im=Image.new('RGB',(600,400),'white');draw=ImageDraw.Draw(im);tokens=[]
    for i,value in enumerate(values):
        y=80+i*60;draw.line((70,y,500,y),fill='#cccccc')
        tokens.append(dict(text=f'${value}',box=[515,y-8,40,16],confidence=95))
    points=[(70,280),(175,170),(290,245),(395,125),(499,200)]
    draw.line(points,fill='#725ade',width=3)
    if second:draw.line([(x,y+25) for x,y in points],fill='#19a57c',width=3)
    path=tmp_path/'chart.png';im.save(path)
    return path,np.array(im),tokens


def test_tick_grid_correspondence_and_unknown_scale(tmp_path):
    path,rgb,tokens=fixture(tmp_path)
    binding=bind_ticks(tokens,horizontal_gridlines(rgb),(600,400),'fixture')
    assert len(binding['axes'])==1
    assert binding['axes'][0]['calibration_status']=='calibrated'
    assert [a['value'] for a in binding['axes'][0]['anchors']]==[400,300,200,100,0]
    candidates,_=trace_axis_curve(rgb,binding['axes'][0])
    assert len(candidates)==1 and len(candidates[0]['points'])==101


def test_conflicting_axis_is_retained(tmp_path):
    path,rgb,tokens=fixture(tmp_path,values=(400,300,280,100,0))
    binding=bind_ticks(tokens,horizontal_gridlines(rgb),(600,400),'fixture')
    assert binding['axes'][0]['calibration_status']=='inconsistent'
    assert len(binding['axes'][0]['anchors'])==5


def test_repeated_or_mixed_units_reject_axis(tmp_path):
    path,rgb,tokens=fixture(tmp_path)
    tokens[2]['text']='€200'
    assert not bind_ticks(tokens,horizontal_gridlines(rgb),(600,400),'fixture')['axes']
    tokens[2]['text']='$300'
    assert not bind_ticks(tokens,horizontal_gridlines(rgb),(600,400),'fixture')['axes']


def test_no_grid_does_not_bind_headline_amounts(tmp_path):
    path,rgb,tokens=fixture(tmp_path)
    assert not bind_ticks(tokens,[],(600,400),'fixture')['axes']


def test_grid_is_not_joined_to_nearby_rendered_tick_text(tmp_path):
    from matplotlib import font_manager
    path,rgb,tokens=fixture(tmp_path)
    im=Image.fromarray(rgb);draw=ImageDraw.Draw(im);font=ImageFont.truetype(font_manager.findfont('DejaVu Sans'),17)
    for token in tokens:draw.text((515,token['box'][1]+8),token['text'],font=font,fill='#566475',anchor='lm')
    binding=bind_ticks(tokens,horizontal_gridlines(np.array(im)),im.size,'fixture')
    assert len(binding['axes'])==1


def test_two_curves_are_not_merged(tmp_path):
    path,rgb,tokens=fixture(tmp_path,second=True)
    axis=bind_ticks(tokens,horizontal_gridlines(rgb),(600,400),'fixture')['axes'][0]
    assert len(trace_axis_curve(rgb,axis)[0])==2


def test_curve_occlusion_at_far_grid_end_does_not_split_axis(tmp_path):
    path,rgb,tokens=fixture(tmp_path)
    lines=[dict(y=80+i*60,left=90 if i==2 else 70,right=500) for i in range(5)]
    binding=bind_ticks(tokens,lines,(600,400),'fixture')
    assert len(binding['axes'])==1 and len(binding['axes'][0]['anchors'])==5
    assert binding['axes'][0]['left']==70


def test_reader_uses_tick_values_and_preserves_disagreement(tmp_path,monkeypatch):
    path,rgb,tokens=fixture(tmp_path)
    def scan(*args,**kwargs):return dict(tokens=tokens,available=True,text='',preprocessing={})
    monkeypatch.setattr('chart_recover.tick_recovery.read_text',scan)
    result=analyze_ticks(path,output=tmp_path/'ok')
    assert result['status']=='calibrated' and result['recovery'][0]['scale']=='linear'
    # First sample y=280 represents exactly 66.667 units on this axis.
    assert abs(result['recovery'][0]['values'][0]-400/6)<2
    calls=[]
    def disagree(*args,**kwargs):
        calls.append(1);copy=[dict(t) for t in tokens]
        if len(calls)==2:copy[2]=dict(copy[2],text='$210')
        return dict(tokens=copy,available=True,text='',preprocessing={})
    monkeypatch.setattr('chart_recover.tick_recovery.read_text',disagree)
    result=analyze_ticks(path,output=tmp_path/'conflict')
    assert result['status']=='needs_evidence_or_review'
    assert result['recovery'][0]['values'] is None and result['binding']['contested_axis_tokens']
