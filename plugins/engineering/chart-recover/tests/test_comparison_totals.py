import copy
import importlib.util
import numpy as np
import pytest
import shutil


def fixture():
    rng=np.random.default_rng(92);n=31
    arrays=[rng.uniform(160,700,n),rng.uniform(40,350,n)]
    x=np.linspace(40,1000,n);xx=np.arange(40,1001)
    candidates=[dict(color=c,x=xx.tolist(),y=np.interp(xx,x,650-v*.55).tolist(),
                     roi=[38,200,1003,650],trace_mode='thin_strong_stroke_center',pixel_error=[2.5]*len(xx))
                for c,v in zip(('#684cdd','#d477c9'),arrays)]
    def token(text,x,y,w=100):return dict(text=text,box=[x,y,w,22],confidence=99)
    tokens=[token('All',40,30,28),token('revenue',78,30),token(f'${sum(arrays[0]):,.2f}',40,80),
            token('vs.',40,125,25),token(f'${sum(arrays[1]):,.2f}',78,125),token('last',190,125,40),token('period',235,125,65),
            token('1',40,675,10),token('May',58,675,40),token('31',940,675,20),token('May',968,675,35)]
    return candidates,tokens,arrays


def propose(candidates,tokens):
    assert importlib.util.find_spec('chart_recover.comparison_totals') is not None,'Comparison-total reader is not implemented'
    from chart_recover.comparison_totals import propose_comparison
    return propose_comparison(candidates,tokens,'https://x.com/fixture/status/123',[1050,730])


def test_shared_scale_from_two_sums_without_zero_or_point_anchors():
    c,t,values=fixture();r=propose(c,t)
    assert r['status']=='conditional_calibration'
    assert r['evidence_strength']=='two_totals_unchecked'
    assert r['independent_checking_values']==0
    assert r['date_assignment']=='month_day_proposed_year_unknown'
    assert len(r['recovery'])==2
    for got,expected in zip(r['recovery'],values):
        assert np.max(abs(np.array(got['values'])-expected))<3
        assert np.all(np.array(got['lower'])<=expected)
        assert np.all(np.array(got['upper'])>=expected)
    assert all(a['kind']=='sum' for a in r['calibration']['anchors_used'])


def test_curve_order_does_not_determine_total_assignment():
    c,t,values=fixture();r=propose(c[::-1],t)
    assert r['status']=='conditional_calibration'
    assert np.mean(abs(np.array(r['recovery'][0]['values'])-values[1]))<1


def test_pale_comparison_stroke_is_traced_only_when_requested(tmp_path):
    from PIL import Image,ImageDraw
    from chart_recover.external_evidence import trace_curve
    p=tmp_path/'pale.png';im=Image.new('RGB',(800,400),'white');d=ImageDraw.Draw(im)
    d.line([(30,250),(300,140),(760,240)],fill=(235,155,226),width=3);im.save(p)
    _,default=trace_curve(p)
    assert not default
    _,pale=trace_curve(p,min_saturation=65)
    assert len(pale)==1 and pale[0]['x'][0]<=31 and pale[0]['x'][-1]>=759


def test_faint_stroke_hue_variation_keeps_observed_pixels(tmp_path):
    from PIL import Image,ImageDraw
    from chart_recover.external_evidence import trace_curve
    p=tmp_path/'hue.png';im=Image.new('RGB',(900,400),'white');d=ImageDraw.Draw(im)
    for x in range(35,866):
        # A weak short hue shift interrupts a long, otherwise stable pink line.
        hue=208 if 490<x<525 else 220
        col=Image.new('HSV',(1,1),(hue,90,240)).convert('RGB').getpixel((0,0))
        y=round(240-100*np.sin((x-35)/830*np.pi));d.line([(x,y-1),(x,y+1)],fill=col)
    im.save(p)
    _,c=trace_curve(p,min_saturation=65,hue_tolerance=4)
    assert len(c)==1 and c[0]['x'][0]<=36 and c[0]['x'][-1]>=864


def test_short_occlusions_group_strokes_without_inventing_observed_pixels(tmp_path):
    from PIL import Image,ImageDraw
    from chart_recover.external_evidence import trace_curve
    p=tmp_path/'gap.png';im=Image.new('RGB',(900,400),'white');d=ImageDraw.Draw(im)
    d.line([(35,270),(430,120),(865,270)],fill=(230,140,220),width=3)
    d.rectangle([448,80,455,300],fill='white');im.save(p)
    _,c=trace_curve(p,min_saturation=65,hue_tolerance=4,group_radius=7,max_column_gap=15)
    assert len(c)==1 and c[0]['x'][0]<=36 and c[0]['x'][-1]>=864
    assert not any(448<=x<=455 for x in c[0]['x'])


@pytest.mark.parametrize('change',['mrr','mixed_currency','missing_comparison','wrong_count','invalid_day','smooth','third_curve','incomplete','equal_totals'])
def test_unsupported_correspondence_abstains(change):
    c,t,_=fixture()
    if change=='mrr':t[1]['text']='MRR'
    if change=='mixed_currency':t[4]['text']=t[4]['text'].replace('$','€')
    if change=='missing_comparison':t=[a for a in t if a['text'] not in ('vs.','last','period')]
    if change=='wrong_count':t[-2]['text']='30'
    if change=='invalid_day':
        for tok in t:
            if tok['text']=='May':tok['text']='Apr'
    if change=='smooth':
        for s in c:s['y']=(380+100*np.sin(np.linspace(0,24,len(s['x'])))).tolist()
    if change=='third_curve':c.append(copy.deepcopy(c[0]))
    if change=='incomplete':c[0]['x']=c[0]['x'][90:];c[0]['y']=c[0]['y'][90:]
    if change=='equal_totals':t[4]['text']=t[2]['text']
    r=propose(c,t)
    assert r['status']!='conditional_calibration'
    assert not r['recovery']


def test_agent_runs_comparison_and_strict_policy_suppresses_it(tmp_path,monkeypatch):
    from PIL import Image
    from chart_recover.agent import investigate_image
    c,t,_=fixture();proposal=propose(c,t);calls=[]
    image=tmp_path/'image.png';Image.new('RGB',(60,60),'white').save(image)
    monkeypatch.setattr('chart_recover.agent.recover',lambda *a,**k:dict(image_sha256='fixture',status='needs_evidence_or_review',calibrated_candidates=0))
    def comparison(*args):calls.append(args);return proposal
    monkeypatch.setattr('chart_recover.comparison_totals.recover_comparison',comparison)
    r=investigate_image(image,{},tmp_path/'agent')
    assert len(calls)==1 and r['conditional_candidates']==1
    assert r['conditional_results'][0]['reader']=='comparison_totals'
    strict=investigate_image(image,{},tmp_path/'strict',strict_only=True)
    assert len(calls)==1 and strict['conditional_candidates']==0


@pytest.mark.skipif(not shutil.which('tesseract'),reason='Real OCR regression requires Tesseract')
def test_large_headline_is_read_without_losing_its_currency_symbol(tmp_path):
    """A reviewed v1 failure becomes a development regression, never a new holdout."""
    from chart_recover.comparison_benchmark import generate
    from chart_recover.comparison_totals import recover_comparison
    generate(tmp_path/'chart',540000,'pillow','light',28,'dense')
    result=recover_comparison(tmp_path/'chart/chart.png',{'source':'https://x.com/fixture/status/123'},tmp_path/'result')
    # Keep this regression focused on reading amounts. The subsequent grid
    # fitter can now resolve the old spacing failure without changing OCR.
    assert result.get('sampling_checks'),result['reasons']
    from chart_recover.autopilot import consensus_tokens, MONEY
    header=[s for s in result['ocr'] if s.get('comparison_region')=='header']
    accepted,_=consensus_tokens(header[0]['tokens'],header[1]['tokens'])
    assert [t['text'] for t in accepted if MONEY.fullmatch(t['text'])]==['$14,859.37','$10,829.33']
    assert result['independent_checking_values']==0


@pytest.mark.skipif(not shutil.which('tesseract'),reason='Real OCR regression requires Tesseract')
def test_thick_endpoint_pixels_do_not_shift_daily_corner_positions(tmp_path):
    import json
    from chart_recover.comparison_benchmark import generate,score
    from chart_recover.comparison_totals import recover_comparison
    generate(tmp_path/'chart',560002,'pillow','light',30,'dense')
    result=recover_comparison(tmp_path/'chart/chart.png',{'source':'https://x.com/fixture/status/123'},tmp_path/'result')
    assert result['status']=='conditional_calibration',result['reasons']
    assert score(result,json.loads((tmp_path/'chart/truth.json').read_text()))['passed']
