from pathlib import Path
import json
import numpy as np
import pytest
from chart_recover.first_customer import caption_claim, propose_first_customer

SOURCE='https://x.com/founder/status/123456'
CAPTION='Got my first paying customer 10 days after I launched a new startup!'


def fixture():
    xs=np.arange(50.,951.,10.);ys=np.interp(xs,[50,850,950],[450,450,150])
    points=[dict(x=float(x),y=float(y),pixel_error=2.5) for x,y in zip(xs,ys)]
    geometry=dict(size=[1000,600],roi=[49,148,952,453],quality_issues=[],series=[
        dict(id='series_0',kind='line',points=points,coordinates=ys.tolist())])
    tokens=[dict(text='Monthly',box=[50,20,90,20]),dict(text='Recurring',box=[150,20,100,20]),
            dict(text='Revenue',box=[260,20,90,20]),dict(text='$178.20',box=[50,65,180,50])]
    return geometry,tokens


def test_customer_pronoun_in_following_sentence_is_not_third_party_attribution():
    caption=CAPTION+' They found one of my articles on Google.'
    assert caption_claim(caption,SOURCE)['status']=='proposed'
    assert caption_claim('They got my first paying customer.',SOURCE)['status']=='unsupported'


def test_caption_and_headline_form_an_explicit_unchecked_hypothesis():
    g,t=fixture();r=propose_first_customer(g,t,CAPTION,SOURCE)
    assert r['status']=='conditional_calibration'
    assert r['date_assignment']=='unassigned' and r['independent_checking_values']==0
    assert r['evidence_strength']=='caption_and_headline_unchecked'
    assert r['recovery'][0]['values'][-1]==pytest.approx(178.2)
    assert max(abs(v) for v in r['recovery'][0]['values'][:70])<1e-7
    assert r['zero_observation']['basis']=='caption_inference_not_observed_zero_tick'
    assert any('same business' in a for a in r['assumptions'])


@pytest.mark.parametrize('caption',[
    'Got my first customer!',
    'I hope I get my first paying customer today.',
    'I did not get my first paying customer.',
    'My friend got my first paying customer.',
    'Got my first paying customer for my second product.',
    'Got my first paying customer last year.',
    'Got my first paying customer back in June.',
    'Got my first paying customer again after losing all customers.',
    'Got my first paying customer? No, this is a forecast.',
    'They said: "Got my first paying customer!"',
    'Got my first paying customer for this plan, after 10 existing subscribers.',
    'Got my first paying customer, but already had revenue from enterprise contracts.',
])
def test_ambiguous_or_contradictory_captions_do_not_create_zero(caption):
    assert caption_claim(caption,SOURCE)['status']=='unsupported'


@pytest.mark.parametrize('source',['','file:///tmp/input','https://example.com/story'])
def test_claim_requires_its_original_public_post(source):
    assert caption_claim(CAPTION,source)['status']=='unsupported'


@pytest.mark.parametrize('issue',['moving_prefix','early_rise','falling_tail','multiple_series','wrong_heading','two_amounts','contested_amount'])
def test_geometry_or_local_evidence_conflicts_abstain(issue):
    g,t=fixture();disagreements=[]
    if issue=='moving_prefix':g['series'][0]['points'][10]['y']-=30
    if issue=='early_rise':
        for p in g['series'][0]['points']:
            p['y']=float(np.interp(p['x'],[50,400,950],[450,450,150]))
    if issue=='falling_tail':g['series'][0]['points'][-5]['y']=100
    if issue=='multiple_series':g['series']*=2
    if issue=='wrong_heading':t[0]['text']='Annual'
    if issue=='two_amounts':t.append(dict(text='$35',box=[450,65,100,50]))
    if issue=='contested_amount':disagreements=[dict(token=t[-1],reason='disagreed')]
    r=propose_first_customer(g,t,CAPTION,SOURCE,disagreements)
    assert r['status']=='needs_evidence_or_review' and not r['recovery']


def test_agent_runs_caption_hypothesis_only_outside_strict_policy(tmp_path,monkeypatch):
    import chart_recover.agent as agent
    import chart_recover.first_customer as module
    monkeypatch.setattr(agent,'recover',lambda *a,**k:dict(image_sha256='x',status='needs_evidence_or_review',calibrated_candidates=0))
    calls=[]
    def reader(image,config,output):
        calls.append(config)
        return dict(status='conditional_calibration',assumptions=['fixture assumption'],
                    date_assignment='unassigned',evidence_strength='caption_and_headline_unchecked')
    monkeypatch.setattr(module,'recover_first_customer',reader)
    cfg=dict(source=SOURCE,post_text=CAPTION)
    from PIL import Image
    image=tmp_path/'blank.png';Image.new('RGB',(80,60),'white').save(image)
    result=agent.investigate_image(image,cfg,tmp_path/'inferred')
    assert result['conditional_candidates']==1 and len(calls)==1
    assert result['conditional_results'][0]['evidence_strength']=='caption_and_headline_unchecked'
    strict=agent.investigate_image(image,cfg,tmp_path/'strict',strict_only=True)
    assert strict['conditional_candidates']==0 and len(calls)==1
