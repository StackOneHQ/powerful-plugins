from datetime import date,timedelta
import json
from pathlib import Path
import pytest
from chart_recover.external_evidence import date_axis


def axis_fixture():
    geometry=dict(size=[700,400],roi=[50,100,650,300],series=[dict(points=[dict(x=50,y=300),dict(x=650,y=100)])])
    periods=[(date(2026,9,1)+timedelta(days=i)).isoformat() for i in range(30)]
    tokens=[]
    for day in (2,7,12,17,22,27):
        x=50+(day-1)*20
        tokens.extend([dict(text='Sep',box=[x-18,320,20,12]),dict(text=str(day),box=[x+4,320,14,12])])
    return geometry,periods,tokens


@pytest.mark.parametrize('year',['2025','2028p','2026x'])
def test_contrary_or_ambiguous_year_is_not_silently_ignored(year):
    g,p,t=axis_fixture();t.append(dict(text=year,box=[300,340,40,12]))
    r=date_axis(t,g,p)
    assert r['status']=='needs_review' and 'year' in r['reason']


def test_header_year_is_checked_but_distant_founded_year_is_not():
    g,p,t=axis_fixture();t.append(dict(text='2025',box=[300,70,40,12]))
    assert date_axis(t,g,p)['status']=='needs_review'
    t[-1]['box'][1]=-100
    assert date_axis(t,g,p)['status']=='proposed'


def test_inset_edge_label_is_retained_but_not_used_for_axis_fit():
    g,p,t=axis_fixture();t.extend([dict(text='Sep',box=[634,320,20,12]),dict(text='30',box=[656,320,14,12])])
    r=date_axis(t,g,p)
    assert r['status']=='proposed' and len(r['excluded_edge_labels'])==1
    assert r['pixels_per_day']==pytest.approx(20)
    assert r['pixel_error']==3


def test_partial_trace_does_not_silently_drop_later_axis_labels():
    g,p,t=axis_fixture();g['series'][0]['points'][-1]['x']=350;g['roi'][2]=350
    r=date_axis(t,g,p)
    assert r['status']=='needs_review' and 'does not cover' in r['reason']
    assert r['outside_trace']


def test_agent_strict_policy_does_not_fetch_external_evidence(monkeypatch,tmp_path):
    import chart_recover.agent as agent
    def readers(image,config,output):
        output.mkdir(parents=True);return dict(image_sha256='test',status='needs_evidence_or_review',calibrated_candidates=0)
    monkeypatch.setattr(agent,'recover',readers)
    import chart_recover.public_profile as public
    monkeypatch.setattr(public,'fetch_profile',lambda *a,**k:pytest.fail('strict mode fetched conditional evidence'))
    r=agent.investigate_image('ignored',{'evidence_profile_url':'https://trustmrr.com/startup/lumen'},tmp_path,True)
    assert r['conditional_candidates']==0
    assert any(s.get('status')=='disabled_by_strict_policy' for s in r['steps'])


def test_alignment_selection_never_uses_checking_values(monkeypatch):
    import chart_recover.external_evidence as external
    g,p,t=axis_fixture();axis=date_axis(t,g,p)
    rows=[dict(period=d,status='dated_observation',value=i+100,low=i+99.5,high=i+100.5,
               source='https://example.test/profile',source_line=i) for i,d in enumerate(p)]
    seen=[]
    def fit(coords,anchors,**kwargs):
        seen.extend(a['period'] for a in anchors)
        return dict(status='calibrated',scale='linear',values=[a['low']+.5 for a in anchors])
    monkeypatch.setattr(external,'calibrate',fit)
    first=external.select_alignment(g,rows,axis)
    for r in rows:
        if date.fromisoformat(r['period']).toordinal()%3==1:r.update(value=10**12,low=10**12,high=10**12)
    second=external.select_alignment(g,rows,axis)
    assert first==second and first[0] is not None
    assert all(date.fromisoformat(d).toordinal()%3!=1 for d in seen)


@pytest.mark.parametrize('low,high,pixel,error,informative',[
    (0.,.01,100.,1.,False),   # All checking values are indistinguishable.
    (99.,101.,19.,2.,False), # Distinct values but overlapping pixel intervals.
    (99.,101.,100.,1.,True),
    (.005,.02,100.,1.,False),# Printed rounding intervals overlap.
])
def test_checking_set_must_distinguish_two_levels(low,high,pixel,error,informative):
    from chart_recover.external_evidence import checking_information
    rows=[dict(period='2026-09-01',low=0.,high=.01,pixel=20.,pixel_error=2.),
          dict(period='2026-09-02',low=low,high=high,pixel=pixel,pixel_error=error)]
    r=checking_information(rows)
    assert (r['status']=='informative')==informative


@pytest.mark.parametrize('strong,weak',[
    ((113,101,232),(195,187,244)),
    ((226,42,54),(235,177,182)),
    ((24,170,120),(181,240,215)),
])
def test_faint_visible_segments_connect_without_inventing_pixels(tmp_path,strong,weak):
    import numpy as np
    from PIL import Image,ImageDraw
    from chart_recover.external_evidence import trace_curve
    im=Image.new('RGB',(800,450),'white');draw=ImageDraw.Draw(im)
    expected={x:int(220+60*np.sin(x/65)) for x in range(50,751)}
    for x,y in expected.items():draw.line([(x,y-1),(x,y+1)],fill=weak if x%100<30 else strong)
    path=tmp_path/'curve.png';im.save(path);g,_=trace_curve(path)
    assert len(g['series'])==1
    points=g['series'][0]['points'];assert points[0]['x']==50 and points[-1]['x']==750
    assert .2<g['series'][0]['weak_column_fraction']<.4
    pixels=np.asarray(im)
    for p in points:
        assert abs(p['y']-expected[p['x']])<=2
        assert tuple(pixels[int(p['y']),p['x']]) in (strong,weak)
        assert p['pixel_error']==(3.5 if p['x']%100<30 else 2.5)


def test_crossing_same_hue_curves_are_not_traced_as_an_envelope(tmp_path):
    import numpy as np
    from PIL import Image,ImageDraw
    from chart_recover.external_evidence import trace_curve
    im=Image.new('RGB',(800,450),'white');draw=ImageDraw.Draw(im)
    for sign in [-1,1]:draw.line([(x,int(220+sign*70*np.sin(x/65))) for x in range(50,751)],fill='#7165e8',width=3)
    path=tmp_path/'two-curves.png';im.save(path);g,_=trace_curve(path)
    assert not g['series']
    assert any('Multiple separated bands' in q['reason'] for q in g['quality_issues'])


def test_missing_curve_pixels_are_not_bridged(tmp_path):
    import numpy as np
    from PIL import Image,ImageDraw
    from chart_recover.external_evidence import trace_curve
    im=Image.new('RGB',(800,450),'white');draw=ImageDraw.Draw(im)
    draw.line([(x,int(220+60*np.sin(x/65))) for x in range(50,751)],fill='#7165e8',width=3)
    draw.rectangle([300,0,500,450],fill='white')
    path=tmp_path/'missing.png';im.save(path);g,_=trace_curve(path)
    assert not g['series']


def test_constant_colored_stroke_abstains_without_nan(tmp_path):
    from PIL import Image,ImageDraw
    from chart_recover.external_evidence import trace_curve
    im=Image.new('RGB',(800,450),'white');ImageDraw.Draw(im).line([(50,220),(750,220)],fill='#7165e8',width=8)
    path=tmp_path/'constant.png';im.save(path);g,_=trace_curve(path)
    assert not g['series'];json.dumps(g,allow_nan=False)


def test_steep_thin_stroke_is_measured_at_its_center(tmp_path):
    # Upper-edge tracing makes this known straight segment tens of pixels high.
    from PIL import Image,ImageDraw
    from chart_recover.external_evidence import trace_curve
    im=Image.new('RGB',(800,450),'white');draw=ImageDraw.Draw(im)
    draw.line([(50,340),(330,340),(355,90),(380,340),(750,340)],fill='#7165e8',width=7)
    path=tmp_path/'steep.png';im.save(path);g,_=trace_curve(path)
    assert len(g['series'])==1
    points={p['x']:p['y'] for p in g['series'][0]['points']}
    assert points[342]==pytest.approx(220,abs=1.5)
    assert points[368]==pytest.approx(220,abs=1.5)


def test_solid_filled_peak_keeps_upper_boundary(tmp_path):
    # A small filled triangle occupies little of the full ROI, so global
    # foreground density alone must not misclassify it as a thin stroke.
    from PIL import Image,ImageDraw
    from chart_recover.external_evidence import trace_curve
    im=Image.new('RGB',(800,450),'white');draw=ImageDraw.Draw(im)
    draw.polygon([(50,340),(330,340),(355,90),(380,340),(750,340)],fill='#7165e8')
    path=tmp_path/'filled-peak.png';im.save(path);g,_=trace_curve(path)
    assert len(g['series'])==1
    points={p['x']:p['y'] for p in g['series'][0]['points']}
    assert points[355]==pytest.approx(90,abs=1)
    # Polygon scan conversion can move a slope-10 boundary by half a pixel
    # horizontally, corresponding to five vertical pixels.
    assert points[342]==pytest.approx(220,abs=5)
    assert points[368]==pytest.approx(220,abs=5)


def test_broad_solid_area_is_not_measured_through_its_interior(tmp_path):
    from PIL import Image,ImageDraw
    from chart_recover.external_evidence import trace_curve
    im=Image.new('RGB',(800,450),'white');draw=ImageDraw.Draw(im)
    draw.polygon([(50,220),(200,120),(400,280),(600,150),(750,220),(750,380),(50,380)],fill='#7165e8')
    path=tmp_path/'broad-area.png';im.save(path);g,_=trace_curve(path)
    assert len(g['series'])==1
    points={p['x']:p['y'] for p in g['series'][0]['points']}
    assert points[200]==pytest.approx(120,abs=1)
    assert points[600]==pytest.approx(150,abs=1)


@pytest.mark.parametrize('fill,accepted', [('#cdc9f6',True), ('#dddddd',False), ('#bce6c5',False)])
def test_faint_same_hue_area_fill_distinguishes_border_from_separate_curve(tmp_path,fill,accepted):
    import numpy as np
    from PIL import Image,ImageDraw
    from chart_recover.external_evidence import trace_curve
    im=Image.new('RGB',(800,450),'white');draw=ImageDraw.Draw(im)
    curve=[(x,int(190+60*np.sin(x/65))) for x in range(50,751)]
    draw.polygon([(50,350),*curve,(750,350)],fill=fill)
    draw.line(curve,fill='#7165e8',width=3)
    draw.line([(50,350),(750,350)],fill='#bcb7f3',width=1)
    draw.line([(50,curve[0][1]),(50,350)],fill='#bcb7f3',width=1)
    draw.line([(750,curve[-1][1]),(750,350)],fill='#bcb7f3',width=1)
    path=tmp_path/'fill.png';im.save(path);g,_=trace_curve(path)
    assert bool(g['series'])==accepted
    if accepted:
        assert all(abs(p['y']-np.interp(p['x'],[q[0] for q in curve],[q[1] for q in curve]))<=2
                   for p in g['series'][0]['points'])
