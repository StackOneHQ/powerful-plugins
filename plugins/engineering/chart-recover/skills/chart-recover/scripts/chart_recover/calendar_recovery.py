"""Recover a curve from a separate daily calendar, with explicit correspondence.

The image reader proposes geometry and dates. Numerical calibration requires
matching daily-revenue headings and endpoint date labels, or separately
declared assumptions. A similar shape alone does not establish correspondence.
"""
from pathlib import Path
import csv
import hashlib
import json
import re
import numpy as np
from PIL import Image
from .vision import _masks,_components,extract,overlay
from .calendar_vision import read_calendar,MONTHS,titles
from .autopilot import _center,consensus_tokens
from .calibrate import calibrate
from .ocr import read_text


def detect_curves(path,days):
    im=Image.open(path)
    if im.width*im.height>30_000_000:raise ValueError('Image exceeds 30 megapixels')
    rgb=np.asarray(im.convert('RGB'));candidates=[]
    for color,mask in _masks(rgb):
        _,components=_components(mask)
        for c in components:
            x,y,w,h=c['x'],c['y'],c['w'],c['h']
            if x<3 or y<3 or x+w>=im.width-3 or y+h>=im.height-3:continue
            if w<max(180,im.width*.24) or h<8 or w/h<2 or c['solidity']>.9:continue
            roi=[max(0,x-3),max(0,y-3),min(im.width,x+w+3),min(im.height,y+h+3)]
            candidates.append(dict(roi=roi,color=color,width=w,solidity=c['solidity']))
    candidates.sort(key=lambda c:c['width'],reverse=True)
    dominant=[]
    if candidates:
        dominant=[c for c in candidates if c['width']>=candidates[0]['width']/1.8]
    geometry=dict(image=str(path),size=list(im.size),roi=[0,0,im.width,im.height],series=[],quality_issues=[],warnings=[],method='wide interior hue components + upper-boundary tracing',status='needs_review')
    if len(dominant)==1:
        color=dominant[0]['color'];rgb_color=[int(color[i:i+2],16) for i in (1,3,5)]
        kind='line' if dominant[0]['solidity']<.06 else 'area'
        geometry=extract(path,kind=kind,roi=dominant[0]['roi'],color=rgb_color,samples=days)
        if len(geometry['series'])!=1 or len(geometry['series'][0]['points'])!=days:
            geometry['quality_issues'].append(dict(reason='Need one complete daily trace for the proposed calendar month.'))
        else:
            # A steep segment can move several Y pixels within one X pixel.
            # Retain this uncertainty instead of forcing all points into the
            # same small vertical tolerance. Values never enter this estimate.
            l,t,r,b=geometry['roi'];crop=rgb[t:b,l:r]
            mask=np.linalg.norm(crop.astype(float)-np.array(rgb_color),axis=2)<65
            column_y={x+l:float((np.median if kind=='line' else np.min)(np.where(mask[:,x])[0])+t) for x in range(mask.shape[1]) if mask[:,x].any()}
            series=geometry['series'][0];errors=[]
            for point in series['points']:
                x=round(point['x']);point['y']=column_y[x]
                if 'base' in point:point['extent']=point['base']-point['y']
                errors.append(max(abs(column_y.get(j,point['y'])-point['y']) for j in range(x-1,x+2)))
            series['coordinates']=[p['y'] for p in series['points']]
            q=-np.array(series['coordinates']);series['shape_normalized']=((q-q.min())/np.ptp(q)).tolist() if np.ptp(q) else [0.]*len(q)
            series['x_location_y_error']=errors
            series['uncertainty_note']='Additional Y error is the largest local change within one image column; the calibration adds its raster tolerance.'
    else:geometry['warnings'].append('No unique dominant colored curve was detected.')
    return geometry,candidates


def _metric_heading(tokens,left,right,bottom,lookback):
    found=[]
    for t in tokens:
        if t['text'].lower() not in ('revenue','mrr','arr'):continue
        x,y=_center(t)
        if not left-20<=x<=right+20 or not bottom-lookback<=y<bottom:continue
        row=[r for r in tokens if left-20<=_center(r)[0]<=right+20 and abs(_center(r)[1]-y)<=max(4,t['box'][3]*.6)]
        row.sort(key=lambda r:r['box'][0]);words=[r['text'].lower() for r in row]
        metric=t['text'].lower();aggregation=next((p for p in ('daily','monthly','quarterly','annual') if p in words),None)
        if any(w in words for w in ('cumulative','lifetime','annualized','net','gross','target','forecast')):aggregation='qualified_or_ambiguous'
        found.append(dict(metric=metric,aggregation=aggregation,text=' '.join(r['text'] for r in row),y=y))
    # Multiple preceding headings are ambiguous rather than a ranking shortcut.
    return found[0] if len(found)==1 else None


def _date_ticks(tokens,roi,month,days):
    left,top,right,bottom=roi;found=[]
    for t in tokens:
        x,y,w,h=t['box'];cy=y+h/2
        if not bottom<cy<bottom+max(90,(right-left)*.15) or not left-35<x<right+35:continue
        combined=re.fullmatch(r'([A-Za-z]+)\s*(\d{1,2})',t['text'])
        if combined:
            if MONTHS.get(combined[1].lower())==month:found.append(dict(day=int(combined[2]),x=x+w/2,box=t['box']))
        elif MONTHS.get(t['text'].lower())==month:
            # Tesseract can return slightly overlapping word boxes for a month
            # and a narrow digit, even when both text readings agree.
            nums=[n for n in tokens if re.fullmatch(r'\d{1,2}',n['text']) and -max(h,n['box'][3])*.75<=n['box'][0]-x-w<=h*1.5
                  and n['box'][0]>x+w*.5 and abs(_center(n)[1]-cy)<h*.6]
            if len(nums)==1:
                n=nums[0];found.append(dict(day=int(n['text']),x=(x+n['box'][0]+n['box'][2])/2,box=[x,y,n['box'][0]+n['box'][2]-x,max(h,n['box'][3])]))
    return [t for t in found if 1<=t['day']<=days]


def correspondence(calendar,geometry,config):
    reasons=[];assumptions=[];tokens=calendar['consensus_tokens'];layout=calendar['layout'];roi=geometry['roi']
    left,top,right,bottom=roi;lookback=max(80,calendar['size'][1]*.22)
    curve_heading=_metric_heading(tokens,left,right,top,lookback)
    xs=layout['weekday']['centers'];step=layout['weekday']['step']
    calendar_heading=_metric_heading(tokens,xs[0]-step/2,xs[-1]+step/2,layout['weekday']['y']-5,80)
    same_metric=bool(curve_heading and calendar_heading and curve_heading['metric']==calendar_heading['metric']=='revenue'
                     and curve_heading['aggregation']==calendar_heading['aggregation']=='daily')
    contrary_metric=any(h and (h['metric']!='revenue' or h['aggregation'] in ('monthly','quarterly','annual','qualified_or_ambiguous')) for h in (curve_heading,calendar_heading))
    if contrary_metric:reasons.append('A visible heading contradicts the shared daily-revenue interpretation.')
    elif not same_metric:
        if config.get('assume_shared_daily_revenue'):
            assumptions.append('The separate calendar and selected curve both represent daily revenue in the same currency; supplied assumption, not established by the image headings.')
        else:reasons.append('Confirm that the calendar and curve represent the same daily revenue metric and currency.')
    visible_periods=[t for t in titles(tokens) if left-20<=t['box'][0]<=right+20 and top-lookback<=t['box'][1]<top]
    period=[t for t in visible_periods if t['year']==layout['year'] and t['month']==layout['month']]
    ticks=_date_ticks(tokens,roi,layout['month'],layout['days'])
    points=geometry['series'][0]['points'];tol=max(8,(points[-1]['x']-points[0]['x'])*.025)
    first=[t for t in ticks if t['day']==1 and abs(t['x']-points[0]['x'])<=tol]
    last=[t for t in ticks if t['day']==layout['days'] and abs(t['x']-points[-1]['x'])<=tol]
    full_period=len(period)==1 and len(first)==len(last)==1
    contrary_period=any(t['year']!=layout['year'] or t['month']!=layout['month'] for t in visible_periods)
    contrary_endpoint=any((abs(t['x']-points[0]['x'])<=tol and t['day']!=1) or (abs(t['x']-points[-1]['x'])<=tol and t['day']!=layout['days']) for t in ticks)
    if contrary_period or contrary_endpoint:reasons.append('A visible plot period or endpoint date contradicts the full calendar-month interpretation.')
    elif not full_period:
        if config.get('assume_full_month'):
            assumptions.append('The complete calendar month spans the curve endpoints with one equally spaced daily observation; supplied assumption, not established by exact endpoint date ticks.')
        else:reasons.append('Confirm that the curve spans this full calendar month with one equally spaced observation per day.')
    return dict(status='matched' if not reasons else 'needs_review',reasons=reasons,assumptions=assumptions,
                curve_heading=curve_heading,calendar_heading=calendar_heading,date_ticks=ticks,
                metric_from_image=same_metric,full_period_from_image=full_period)


def analyze_calendar(image,config=None,output='artifacts/calendar-recovery'):
    config=config or {};out=Path(output);out.mkdir(parents=True,exist_ok=True)
    calendar=read_calendar(image,out/'calendar',config.get('source'))
    days=calendar.get('layout',{}).get('days',31)
    geometry,candidates=detect_curves(image,days)
    binding=dict(status='needs_review',reasons=[],assumptions=[]);cal=None;anchors=[]
    if calendar['status']!='read':binding['reasons'].append('Calendar layout or monetary readings remain uncertain.')
    if len(geometry['series'])!=1 or geometry.get('quality_issues'):binding['reasons'].append('Need one complete curve trace before matching calendar dates.')
    if not binding['reasons']:
        ticks=_date_ticks(calendar['consensus_tokens'],geometry['roi'],calendar['layout']['month'],days)
        if not {1,days}.issubset({t['day'] for t in ticks}):
            l,t,r,b=geometry['roi'];w,h=calendar['size']
            region=[max(0,l-40),b+4,min(w,r+40),min(h,int(b+max(90,(r-l)*.15)))]
            if region[1]<region[3]:
                invert=calendar['full_image_ocr'][0]['preprocessing']['invert']
                scans=[read_text(image,scale=s,invert=invert,region=region,psm=6) for s in (2.,3.)]
                accepted,rejected=consensus_tokens(scans[0]['tokens'],scans[1]['tokens'])
                calendar['plot_date_ocr']=dict(region=region,ocr=scans,rejected=rejected)
                calendar['consensus_tokens']=[t for t in calendar['consensus_tokens'] if not region[1]<=_center(t)[1]<=region[3]]+accepted
        binding=correspondence(calendar,geometry,config)
        if binding['status']=='matched':
            coords=geometry['series'][0]['coordinates']
            errors=[config.get('pixel_error',2.5)+e for e in geometry['series'][0]['x_location_y_error']]
            for o in calendar['observations']:
                day=int(o['date'][-2:]);anchors.append(dict(pixel=coords[day-1],low=o['low'],high=o['high'],source=o['source'],matched=True,
                    pixel_error=errors[day-1],assumptions=binding['assumptions']+calendar['assumptions']+['Daily X positions have one image-column uncertainty; bounds include its local Y effect.'],date=o['date'],label_box=o['box']))
            cal=calibrate(coords,anchors,scale=config.get('scale','unknown'),pixel_error=max(errors))
            cal['point_pixel_errors']=errors
            cal['location_bound_note']='Each anchor uses its own raster-plus-X-location tolerance. Output intervals conservatively use the largest tolerance across the curve.'
    if cal is None:cal=dict(status='needs_correspondence',values=None,reason=' '.join(binding['reasons']),anchors_used=[],assumptions=binding['assumptions'])
    result=dict(image=str(image),image_sha256=hashlib.sha256(Path(image).read_bytes()).hexdigest(),config=config,
                status='calibrated' if cal['status']=='calibrated' else 'needs_evidence_or_review',geometry=geometry,
                curve_candidates=candidates,calendar=calendar,correspondence=binding,recovery=[dict(series='series_0',**cal)],
                trace=[dict(step='read_calendar',observations=len(calendar['observations']),days=days),dict(step='locate_curve',candidates=len(candidates)),
                       dict(step='check_correspondence',**binding),dict(step='calibrate',status=cal['status'],anchors=len(anchors))])
    (out/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False), encoding="utf-8");overlay(image,geometry,out/'overlay.png')
    with (out/'data.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['date','pixel_x','pixel_y','value','lower','upper','status'])
        if len(geometry['series'])==1:
            for i,p in enumerate(geometry['series'][0]['points']):
                layout=calendar.get('layout',{});date=f"{layout['year']:04d}-{layout['month']:02d}-{i+1:02d}" if layout else ''
                val=lambda k:cal[k][i] if cal.get(k) is not None else ''
                writer.writerow([date,p['x'],p['y'],val('values'),val('lower'),val('upper'),cal['status']])
    return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('image');p.add_argument('--out',default='artifacts/calendar-recovery');p.add_argument('--source')
    p.add_argument('--scale',choices=['unknown','linear','log'],default='unknown')
    p.add_argument('--assume-shared-daily-revenue',action='store_true');p.add_argument('--assume-full-month',action='store_true')
    a=p.parse_args();r=analyze_calendar(a.image,dict(source=a.source,scale=a.scale,assume_shared_daily_revenue=a.assume_shared_daily_revenue,assume_full_month=a.assume_full_month),a.out)
    print(json.dumps(dict(status=r['status'],outcomes=[c['status'] for c in r['recovery']],calendar_values=len(r['calendar']['observations']),
                         reasons=r['correspondence']['reasons'],assumptions=r['correspondence']['assumptions']),indent=2))
