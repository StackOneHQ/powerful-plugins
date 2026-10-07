"""Conditional zero-history inference from an original first-customer caption.

This is a bounded English grammar and a geometric hypothesis, not established
source identity or an independent numerical check. A headline alone is never
enough. Output points are samples of the drawn line, with no dates assigned.
"""
from pathlib import Path
import csv
import hashlib
import json
import re
import numpy as np
from .collect import POST_URL
from .autopilot import MONEY, _center, consensus_tokens
from .calibrate import calibrate
from .external_evidence import trace_curve
from .ocr import read_text
from .vision import overlay


def caption_claim(text,source):
    result=dict(status='unsupported',source=source,reasons=[],quote=None,
                basis='caption_inference_not_observed_zero_tick')
    if not isinstance(source,str) or not POST_URL.fullmatch(source):
        result['reasons'].append('Need the original public X post URL for its accompanying caption.')
    if not isinstance(text,str) or not text.strip():
        result['reasons'].append('No accompanying caption.');return result
    if len(text)>20000:
        result['reasons'].append('Caption exceeds the bounded grammar.');return result
    forbidden=r'\b(?:not|never|didn.t|wasn.t|isn.t|hope|hoping|goal|target|forecast|will|would|could|should|if|wish|friend|their|says|said|again|another|second|existing|already|previous|former|restarted|last\s+(?:year|month|week)|back\s+in|years?\s+ago|months?\s+ago|days?\s+ago|this\s+plan)\b'
    if re.search(forbidden,text,re.I) or any(c in text for c in ('?','"','“','”')):
        result['reasons'].append('Caption has retrospective, hypothetical, quoted, repeated or conflicting customer scope.')
    pattern=r'^(?:\W)*(?:(?:I|we)\s+)?(?:(?:just|finally)\s+)?(?:got|landed|acquired)\s+(?:my|our)\s+(?:very\s+)?first\s+paying\s+customer\b'
    clauses=re.split(r'(?<=[.!?])\s+|[\n;]+',text)
    matches=[c.strip() for c in clauses if re.search(pattern,c,re.I)]
    if len(matches)!=1:result['reasons'].append('Need one direct first-person statement of a first paying customer.')
    if not result['reasons']:result.update(status='proposed',quote=matches[0])
    return result


def _rows(tokens):
    rows=[]
    for t in sorted(tokens,key=lambda t:(_center(t)[1],t['box'][0])):
        y=_center(t)[1];h=t['box'][3]
        row=next((r for r in rows if abs(r['y']-y)<=max(4,min(h,r['height'])*.6)),None)
        if row is None:row=dict(y=y,height=h,tokens=[]);rows.append(row)
        row['tokens'].append(t)
    for r in rows:
        r['tokens'].sort(key=lambda t:t['box'][0])
        r['text']=' '.join(t['text'] for t in r['tokens'])
    return rows


def propose_first_customer(geometry,tokens,caption,source,disagreements=()):
    claim=caption_claim(caption,source)
    result=dict(status='needs_evidence_or_review',geometry=geometry,caption_claim=claim,
                reasons=list(claim['reasons']),assumptions=[],recovery=[],date_assignment='unassigned',
                evidence_strength='caption_and_headline_unchecked',independent_checking_values=0)
    if claim['status']!='proposed':return result
    if len(geometry.get('series',[]))!=1 or geometry.get('quality_issues'):
        result['reasons'].append('Need one complete unambiguous curve.');return result
    series=geometry['series'][0];points=series['points']
    xs=np.array([p['x'] for p in points]);ys=np.array([p['y'] for p in points])
    if len(xs)<20 or np.any(np.diff(xs)<=0) or np.ptp(xs)<80:
        result['reasons'].append('Need a sufficiently sampled continuous trace.');return result
    left,top,right,_=geometry['roi']
    rows=_rows([t for t in tokens if _center(t)[1]<top-5])
    headings=[r for r in rows if r['text'].casefold() in ('mrr','monthly recurring revenue')]
    if len(headings)!=1:
        result['reasons'].append('Need one consensus MRR heading above the curve.');return result
    heading=headings[0]
    eligible=lambda t:left-20<=_center(t)[0]<=right+20 and heading['y']+heading['height']/2<_center(t)[1]<top-5
    amounts=[t for t in tokens if MONEY.fullmatch(t['text']) and eligible(t)]
    if len(amounts)!=1 or any(MONEY.fullmatch(d['token']['text']) and eligible(d['token']) for d in disagreements):
        result['reasons'].append('Need one uncontested headline amount between the MRR heading and curve.');return result
    amount=amounts[0];match=MONEY.fullmatch(amount['text']);number=match['number'].replace(',','')
    value=float(number);decimals=len(number.split('.')[1]) if '.' in number else 0
    half=.5*10**-decimals
    if value<=half:
        result['reasons'].append('Headline must be positive and distinguishable from zero.');return result
    span=np.ptp(xs);prefix=xs<=xs[0]+span*.7
    baseline=float(np.median(ys[prefix]));error=max(2.5,max(p.get('pixel_error',2.5) for p in points))
    rise=baseline-ys[-1]
    if rise<max(20,8*error) or np.max(np.abs(ys[prefix]-baseline))>error:
        result['reasons'].append('The initial 70% of the curve must support one flat level, with a separated positive endpoint.');return result
    moved=np.flatnonzero(np.abs(ys-baseline)>error)
    if not len(moved) or xs[moved[0]]<xs[0]+.8*span:
        result['reasons'].append('The first visible change is too early for the supported recent-first-customer hypothesis.');return result
    tail=ys[max(0,moved[0]-1):]
    if np.max(tail-np.minimum.accumulate(tail))>2*error:
        result['reasons'].append('The tail contains a decline inconsistent with the supported simple first-customer pattern.');return result
    assumptions=[
        'The caption and MRR chart describe the same business and its first ever paying customer.',
        'The initial flat history is assumed to be zero recurring revenue before that first customer; no zero tick was observed.',
        'The headline denotes the rightmost observed MRR endpoint, not a sum, average or another reporting period.',
        'The displayed headline is rounded to the nearest shown decimal place.',
        'MRR is nonnegative; a zero observation excludes a standard logarithmic axis. Other nonlinear or broken axes are unsupported.',
        'There are only two inferred anchors and no unused numerical checking values. This is an unchecked correspondence hypothesis.',
        'Curve samples have no assigned dates and are not daily accounting records.',
        'Agreement between two OCR rescalings does not independently verify the amount or source truth.']
    anchors=[dict(pixel=baseline,value=0.,source=source,matched=True,pixel_error=error,
                  correspondence_basis='caption_zero_history_hypothesis',quote=claim['quote']),
             dict(pixel=float(ys[-1]),low=value-half,high=value+half,source=source,matched=True,pixel_error=error,
                  correspondence_basis='headline_endpoint_hypothesis',label_box=amount['box'])]
    cal=calibrate(ys,anchors,scale='unknown',pixel_error=error)
    if cal['status']!='calibrated':
        result['reasons'].append(cal.get('reason','The inferred anchors do not establish one scale.'));return result
    # The explicit MRR domain excludes negative raster-tolerance excursions.
    for key in ('values','lower','upper'):cal[key]=[max(0.,v) for v in cal[key]]
    cal.update(status='conditional_calibration',assumptions=assumptions)
    result.update(status='conditional_calibration',assumptions=assumptions,recovery=[dict(series=series['id'],**cal)],
        headline=dict(text=amount['text'],value=value,currency=match['currency'],box=amount['box']),
        zero_observation=dict(pixel=baseline,basis=claim['basis'],quote=claim['quote'],source=source),
        geometry_check=dict(flat_prefix_fraction=.7,first_change_relative_x=float((xs[moved[0]]-xs[0])/span),
                            endpoint_rise_pixels=float(rise),pixel_error=error))
    return result


def recover_first_customer(image,config,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    geometry,candidates=trace_curve(image)
    width,height=geometry['size']
    scans=[read_text(image,scale=min(s,(28_000_000/(width*height))**.5)) for s in (2.,3.)]
    tokens,disagreements=consensus_tokens(scans[0]['tokens'],scans[1]['tokens'])
    result=propose_first_customer(geometry,tokens,config.get('post_text',''),config.get('source') or config.get('post_url'),disagreements)
    result.update(image=str(image),image_sha256=hashlib.sha256(Path(image).read_bytes()).hexdigest(),
                  curve_candidates=candidates,ocr=scans,consensus_tokens=tokens,ocr_disagreements=disagreements)
    (out/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False), encoding="utf-8");overlay(image,geometry,out/'overlay.png')
    with (out/'data.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['point','relative_position','plot_date','pixel_x','pixel_y','conditional_value','lower','upper','status','evidence_strength'])
        if result['recovery']:
            points=geometry['series'][0]['points'];cal=result['recovery'][0]
            for i,p in enumerate(points):writer.writerow([i,(p['x']-points[0]['x'])/(points[-1]['x']-points[0]['x']),'',p['x'],p['y'],
                cal['values'][i],cal['lower'][i],cal['upper'][i],result['status'],result['evidence_strength']])
    return result
