"""Conditional shared linear-axis recovery from two period-total disclosures.

No zero baseline or numeric point anchors are invented. Two sums determine
two affine parameters only after accepting shared units, scale and membership.
There are no unused monetary observations with which to verify those claims.
"""
from pathlib import Path
import calendar
import csv
import hashlib
import json
import re
import numpy as np
from .autopilot import MONEY,consensus_tokens,_center
from .calendar_vision import MONTHS
from .constraints import calibrate_totals
from .external_evidence import trace_curve
from .ocr import read_text
from .vision import overlay
from .curve_grid import fit_shared_grid


def propose_comparison(candidates,tokens,source,size):
    geometry=dict(size=size,roi=[0,0,*size],series=[],warnings=[],quality_issues=[],method='Two hue-separated stroke centers fitted to straight segments on a proposed shared daily grid')
    result=dict(status='needs_evidence_or_review',geometry=geometry,recovery=[],reasons=[],
                evidence_strength='two_totals_unchecked',independent_checking_values=0,
                date_assignment='month_day_proposed_year_unknown')
    def reject(reason):result['reasons'].append(reason);return result
    if len(candidates)!=2:return reject('Need exactly two complete, separately colored curves.')
    if not source:return reject('Need image or post provenance.')
    if any(c['trace_mode']!='thin_strong_stroke_center' for c in candidates):return reject('Only two thin continuous strokes are supported.')
    left=max(c['x'][0] for c in candidates);right=min(c['x'][-1] for c in candidates)
    if any(abs(c['x'][0]-left)>3 or abs(c['x'][-1]-right)>3 for c in candidates):return reject('Curves do not share observed horizontal endpoints.')
    top=min(min(c['y']) for c in candidates);bottom=max(max(c['y']) for c in candidates)
    header=[t for t in tokens if _center(t)[1]<top-8]
    words=[t['text'].lower() for t in header]
    if any(w in words for w in ('mrr','arr','recurring','cumulative')):return reject('Snapshot or cumulative metrics cannot be treated as period sums.')
    if words.count('revenue')!=1 and not ('gross' in words and 'volume' in words):return reject('Need one revenue or gross-volume heading.')
    amounts=[t for t in header if MONEY.fullmatch(t['text'])]
    amounts.sort(key=lambda t:(_center(t)[1],_center(t)[0]))
    if len(amounts)!=2:return reject('Need exactly two consensus monetary totals above the curves.')
    current,previous=amounts
    py=_center(previous)[1]
    comparison=[t['text'].lower().rstrip('.') for t in header if abs(_center(t)[1]-py)<=max(previous['box'][3],12)]
    if not all(w in comparison for w in ('vs','last','period')):return reject('The second amount must explicitly identify the last comparison period.')
    parsed=[MONEY.fullmatch(t['text']) for t in amounts]
    if len({m['currency'] for m in parsed})!=1:return reject('Comparison amounts use different currencies.')
    totals=[]
    for m,t in zip(parsed,amounts):
        number=m['number'].replace(',','');value=float(number)
        if value<=0:return reject('Need two positive totals.')
        decimals=len(number.split('.')[1]) if '.' in number else 0
        totals.append(dict(value=value,low=value-.5*10**-decimals,high=value+.5*10**-decimals,label=t['text'],box=t['box']))
    if abs(totals[0]['value']-totals[1]['value'])<=totals[0]['high']-totals[0]['low']+totals[1]['high']-totals[1]['low']:
        return reject('Equal totals do not provide a separated shared-axis calibration.')
    footer=[t for t in tokens if bottom+3<_center(t)[1]<bottom+max(100,size[1]*.16)]
    labels=[]
    for month in footer:
        m=MONTHS.get(month['text'].lower())
        if not m:continue
        near=[t for t in footer if re.fullmatch(r'\d{1,2}',t['text']) and abs(_center(t)[1]-_center(month)[1])<8
              and 0<=month['box'][0]-t['box'][0]-t['box'][2]<month['box'][3]*1.5]
        if len(near)==1:
            d=near[0];labels.append(dict(month=m,day=int(d['text']),left=d['box'][0],right=month['box'][0]+month['box'][2]))
    labels.sort(key=lambda l:l['left'])
    if len(labels)!=2 or labels[0]['month']!=labels[1]['month'] or not 1<=labels[0]['day']<labels[1]['day']<=31:
        return reject('Need two unambiguous increasing day/month endpoint labels in the same month.')
    if labels[1]['day']>calendar.monthrange(2000,labels[1]['month'])[1]:return reject('The endpoint day is invalid for its month.')
    if not labels[0]['left']-15<=left<=labels[0]['right']+15 or not labels[1]['left']-15<=right<=labels[1]['right']+15:
        return reject('Date labels do not enclose the observed curve endpoints.')
    n=labels[1]['day']-labels[0]['day']+1
    if n<8 or (right-left)/(n-1)<8:return reject('Need at least eight resolvable proposed daily observations.')
    grid=fit_shared_grid(candidates,left,right,n)
    result['sampling_grid']=grid;result['sampling_checks']=grid.get('checks',[])
    if grid['status']!='supported':return reject(grid['reason'])
    xs=np.asarray(grid['xs']);ys=[];checks=grid['checks']
    for i,c in enumerate(candidates):
        daily=np.asarray(grid['ys'][i])
        ys.append(daily)
        q=-daily;spread=float(np.ptp(q))
        geometry['series'].append(dict(id=f'series_{i}',kind='line',color=c['color'],
            points=[dict(x=float(x),y=float(y),month_day=f"{labels[0]['month']:02d}-{labels[0]['day']+j:02d}") for j,(x,y) in enumerate(zip(xs,daily))],
            coordinates=daily.tolist(),shape_normalized=((q-q.min())/spread).tolist() if spread else [0.]*n))
    # Evaluate both assignments. Magnitude correspondence is a hypothesis, not
    # a legend observation; exactly one increasing affine fit must survive.
    fits=[]
    for order in ((0,1),(1,0)):
        constraints=[dict(kind='sum',point_indices=list(range(i*n,(i+1)*n)),observation_count=n,
                          low=totals[k]['low'],high=totals[k]['high'],source=source,matched=True,
                          proposed_series=f'series_{i}',label=totals[k]['label']) for i,k in enumerate(order)]
        cal=calibrate_totals(np.concatenate(ys),totals=constraints,pixel_error=2.5)
        if cal['status']=='calibrated':fits.append((order,cal))
    if len(fits)!=1:return reject('Totals do not select one bounded increasing shared linear-axis hypothesis.')
    order,cal=fits[0]
    assumptions=['Both curves share one increasing linear Y axis; logarithmic and independent axes are not evaluated.',
                 'The two headlines are sums of these curves, in the same currency and metric.',
                 'Both periods contain the same number of daily observations, including their displayed endpoints.',
                 'Piecewise-linear corners and the two date labels locate the daily observations; the year is unknown.',
                 'Daily knot heights fit the observed straight segments; shared endpoints may move within 2.5 pixels of the stroke extent. The outer 5.5 pixels are excluded from fitting to avoid line caps.',
                 'Short missing runs at curve crossings are linearly interpolated; those columns are not observed pixels.',
                 'Curve-to-total assignment is inferred from feasibility, not established by a legend.',
                 'Two agreeing OCR passes can share errors; displayed totals are rounded to their printed precision.',
                 'The two sums fit the two axis parameters. There are zero independent numerical checking values.']
    result.update(status='conditional_calibration',totals=totals,proposed_total_assignment=list(order),
                  proposed_observation_count=n,sampling_checks=checks,assumptions=assumptions,calibration=cal)
    for i,s in enumerate(geometry['series']):
        result['recovery'].append(dict(series=s['id'],status='conditional_calibration',scale='linear',
            **{key:cal[key][i*n:(i+1)*n] for key in ('values','lower','upper')},
            assumptions=assumptions,coefficients=cal['coefficients'],bound_meaning=cal['bound_meaning']))
    return result


def recover_comparison(image,config,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    geometry,candidates=trace_curve(image,min_saturation=65,hue_tolerance=4,group_radius=7,max_column_gap=15)
    scans=[];tokens=[];disagreements=[]
    if len(candidates)==2:
        w,h=geometry['size']
        # Large headlines lose currency glyphs when the entire image is
        # magnified 3x. Read the spatially separate header as one text block at
        # native/2x size; keep sparse endpoint labels at 2x/3x. Region choice
        # uses traced pixels alone and never a recognized monetary value.
        header_end=min(h,max(1,int(min(min(c['y']) for c in candidates)-8)))
        regions=[('header',[0,0,w,header_end],(1.,2.),6),
                 ('outside_header',[0,0,w,h],(2.,3.),11)]
        for role,region,scales,psm in regions:
            cap=(28_000_000/(w*(region[3]-region[1])))**.5
            pair=[read_text(image,scale=min(s,cap),region=region,psm=psm) for s in scales]
            for scan in pair:scan['comparison_region']=role
            token_sets=[scan['tokens'] if role=='header' else
                        [t for t in scan['tokens'] if _center(t)[1]>=header_end] for scan in pair]
            accepted,rejected=consensus_tokens(*token_sets)
            scans.extend(pair);tokens.extend(accepted);disagreements.extend(rejected)
    digest=hashlib.sha256(Path(image).read_bytes()).hexdigest()
    result=propose_comparison(candidates,tokens,config.get('source') or f'image_sha256:{digest}',geometry['size'])
    if result['recovery'] and any(MONEY.fullmatch(d['token']['text']) for d in disagreements):
        result.update(status='needs_evidence_or_review',recovery=[])
        result['reasons'].append('A monetary token failed OCR consensus.')
    result.update(image=str(image),image_sha256=digest,curve_candidates=candidates,ocr=scans,ocr_disagreements=disagreements)
    (out/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False), encoding="utf-8");overlay(image,result['geometry'],out/'overlay.png')
    with (out/'data.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['series','day_index','proposed_month_day','plot_date','pixel_x','pixel_y','conditional_value','lower','upper','status','evidence_strength'])
        for s,r in zip(result['geometry']['series'],result['recovery']):
            for i,p in enumerate(s['points']):writer.writerow([s['id'],i,p['month_day'],'',p['x'],p['y'],r['values'][i],r['lower'][i],r['upper'][i],result['status'],result['evidence_strength']])
    return result
