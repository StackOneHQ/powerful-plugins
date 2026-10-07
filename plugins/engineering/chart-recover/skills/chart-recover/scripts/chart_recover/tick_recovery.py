"""Bind repeated numeric Y labels to visible gridlines and one local curve.

Coordinates remain image positions and normalized X fractions: this reader
does not invent dates, metric identity, original sample counts or zero ticks.
"""
from pathlib import Path
import csv
import hashlib
import json
import re
import numpy as np
from PIL import Image
from scipy import ndimage
from .autopilot import _center,consensus_tokens
from .ocr import read_text
from .vision import _masks,_components,overlay
from .calibrate import calibrate

NUMBER=re.compile(r'^(?P<currency>[$€£]?)(?P<number>-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(?P<multiple>[kKmMbB]?)(?P<percent>%?)$')


def parse_tick(text):
    m=NUMBER.fullmatch(text)
    if not m or (m['currency'] and m['percent']):return None
    value=float(m['number'].replace(',',''))*{'':1,'k':1e3,'m':1e6,'b':1e9}[m['multiple'].lower()]
    if not np.isfinite(value):return None
    return dict(value=value,unit=m['currency'] or m['percent'] or 'unspecified',text=text)


def horizontal_gridlines(rgb):
    """Long neutral strokes differing from their vertical surroundings."""
    gray=rgb.astype(float).mean(axis=2);height,width=gray.shape
    contrast=np.zeros_like(gray)
    contrast[4:-4]=abs(gray[4:-4]-(gray[:-8]+gray[8:])/2)
    neutral=np.ptp(rgb.astype(float),axis=2)<45
    mask=(contrast>=2)&neutral
    # Remove short glyph strokes before joining curve-interrupted gridlines;
    # otherwise the closing operation can join a nearby label into its grid.
    mask=ndimage.binary_opening(mask,structure=np.ones((1,max(15,int(width*.025)))))
    # Small curve intersections may interrupt a grid stroke.
    mask=ndimage.binary_closing(mask,structure=np.ones((1,max(13,min(61,int(width*.05))))))
    lengths=max(65,int(width*.15));lines=[]
    for y,row in enumerate(mask):
        edges=np.diff(np.r_[False,row,False].astype(int));starts=np.where(edges==1)[0];ends=np.where(edges==-1)[0]
        for l,r in zip(starts,ends):
            if r-l>=lengths:lines.append(dict(y=y,left=int(l),right=int(r)))
    return lines


def bind_ticks(tokens,gridlines,size,source):
    """Require at least three labels sharing one local grid extent and side."""
    observations=[];rejected=[];width,height=size
    for token in tokens:
        number=parse_tick(token['text'])
        if not number:continue
        x,y,w,h=token['box'];cy=y+h/2
        matches=[]
        for line in gridlines:
            if abs(line['y']-cy)>max(3,h*.4):continue
            # Labels must be immediately outside the horizontal grid extent.
            side='left' if 0<=line['left']-(x+w)<=max(45,width*.04) else 'right' if 0<=x-line['right']<=max(45,width*.04) else None
            if side:matches.append(dict(line,side=side))
        if not matches:continue
        # Adjacent raster rows represent the same thin grid stroke.
        # Raster noise changes endpoints by a few pixels. Shorter contained
        # spans can be fragments interrupted by a crossing curve.
        longest=max(matches,key=lambda m:m['right']-m['left'])
        tolerance=max(8,width*.01)
        incompatible=[m for m in matches if m['side']!=longest['side'] or m['left']<longest['left']-tolerance or m['right']>longest['right']+tolerance]
        near=[m for m in matches if abs(m['left']-longest['left'])<=tolerance and abs(m['right']-longest['right'])<=tolerance]
        if incompatible:
            rejected.append(dict(token=token,reason='More than one adjacent grid extent.'));continue
        line=min(near,key=lambda m:abs(m['y']-cy))
        observations.append(dict(number,box=token['box'],confidence=token['confidence'],**line))
    groups=[]
    for observation in observations:
        # Near-label ends establish the axis column; a curve can obscure part
        # of the far end. Preserve the union of supported grid extents.
        left_tolerance=max(8,width*(.10 if observation['side']=='right' else .01))
        right_tolerance=max(8,width*(.10 if observation['side']=='left' else .01))
        matches=[g for g in groups if g['side']==observation['side']
                 and abs(g['left']-observation['left'])<=left_tolerance
                 and abs(g['right']-observation['right'])<=right_tolerance]
        if len(matches)==1:
            group=matches[0];group['observations'].append(observation)
            group['left']=min(group['left'],observation['left']);group['right']=max(group['right'],observation['right'])
        elif not matches:groups.append(dict(left=observation['left'],right=observation['right'],side=observation['side'],observations=[observation]))
        else:rejected.append(dict(token=observation,reason='Ambiguous grid group.'))
    axes=[]
    for group in groups:
        obs=sorted(group['observations'],key=lambda o:o['y'])
        reason=None;grid_top=obs[0]['y'];grid_bottom=obs[-1]['y']
        if len(obs)<3:reason='At least three consensus labels on aligned gridlines are required.'
        elif len({o['unit'] for o in obs})!=1:reason='Different currency or unit labels share this axis.'
        elif any(b['y']-a['y']<max(8,a['box'][3]) for a,b in zip(obs,obs[1:])):reason='Tick positions overlap.'
        elif any(b['value']>=a['value'] for a,b in zip(obs,obs[1:])):reason='Tick values do not increase upward.'
        if reason is None:
            # Include grid strokes whose label failed consensus: a missing OCR
            # reading is not a spatial panel gap. Merge adjacent raster rows.
            grid_ys=sorted({line['y'] for line in gridlines
                            if abs(line['left']-group['left'])<=max(8,width*(.10 if group['side']=='right' else .01))
                            and abs(line['right']-group['right'])<=max(8,width*(.10 if group['side']=='left' else .01))})
            strokes=[]
            for y in grid_ys:
                if strokes and y-strokes[-1][-1]<=4:strokes[-1].append(y)
                else:strokes.append([y])
            centers=[float(np.median(stroke)) for stroke in strokes]
            inside=[i for i,y in enumerate(centers) if obs[0]['y']-3<=y<=obs[-1]['y']+3]
            gaps=np.diff([centers[i] for i in inside])
            if len(gaps)<2:
                reason='Need three distinct grid strokes with one consistent extent before tracing.'
            else:
                typical=float(np.median(sorted(gaps)[:max(1,(len(gaps)+1)//2)]))
                if max(gaps)>typical*1.8:
                    reason='Aligned grid labels have a large vertical gap; separate panels or missing ticks need review.'
                else:
                    # Extend across unlabeled strokes in this contiguous grid,
                    # stopping at any separate panel rather than at tick text.
                    first,last=inside[0],inside[-1]
                    while first>0 and centers[first]-centers[first-1]<=typical*1.8:first-=1
                    while last+1<len(centers) and centers[last+1]-centers[last]<=typical*1.8:last+=1
                    grid_top,grid_bottom=centers[first],centers[last]
        if reason:
            rejected.append(dict(group=group,reason=reason));continue
        assumptions=['Numeric labels immediately outside repeated horizontal gridlines denote their Y-axis coordinates.',
                     'Tick labels denote exact values, including printed K/M/B multipliers; display-format rounding beyond these values is not modeled.',
                     'Two agreeing OCR rescalings can share recognition errors.']
        anchors=[dict(pixel=o['y'],value=o['value'],source=f'{source} — Y tick {o["text"]}',matched=True,
                      pixel_error=2.,label_box=o['box'],unit=o['unit'],assumptions=assumptions) for o in obs]
        axis=dict(group,observations=obs,anchors=anchors,unit=obs[0]['unit'],top=obs[0]['y'],bottom=obs[-1]['y'],
                  grid_top=grid_top,grid_bottom=grid_bottom)
        fit=calibrate([axis['top'],axis['bottom']],anchors,scale='unknown',pixel_error=2.)
        axis['calibration_status']=fit['status'];axes.append(axis)
    return dict(axes=axes,rejected=rejected,observations=observations)


def trace_axis_curve(rgb,axis,samples=101):
    """Trace a single continuous colored component local to a numeric axis."""
    height,width=rgb.shape[:2];l,r=axis['left'],axis['right']
    ys=[o['y'] for o in axis['observations']];pad=max(12,int(np.median(np.diff(ys))*.5))
    t=max(0,int(axis.get('grid_top',axis['top'])-pad));b=min(height,int(axis.get('grid_bottom',axis['bottom'])+pad))
    crop=rgb[t:b,l:r];candidates=[]
    for color,mask in _masks(crop):
        labels,components=_components(mask)
        for component in components:
            if component['w']<.90*(r-l) or component['h']<5 or component['solidity']>.35:continue
            if component['y']<=1 or component['y']+component['h']>=b-t-1:continue
            cmask=labels==component['label'];cols=np.where(cmask.any(axis=0))[0]
            if len(cols)<.97*(cols[-1]-cols[0]+1):continue
            # Multiple separated strands in the same component can be crossing
            # curves. Never take a median through widely separated branches.
            branches=sum(bool(np.any(np.diff(np.where(cmask[:,x])[0])>4)) for x in cols)
            if branches>max(2,len(cols)*.01):continue
            points=[];errors=[]
            column_y={int(x):float(np.median(np.where(cmask[:,x])[0])+t) for x in cols}
            for x in np.unique(np.round(np.linspace(cols[0],cols[-1],min(samples,len(cols)))).astype(int)):
                if x not in column_y:continue
                y=column_y[x];points.append(dict(x=float(x+l),y=y,x_fraction=float((x+l-l)/(r-l-1))))
                errors.append(max(abs(column_y.get(j,y)-y) for j in range(x-1,x+2)))
            if len(points)!=min(samples,len(cols)):continue
            candidates.append(dict(color=color,kind='line',points=points,coordinates=[p['y'] for p in points],
                                   x_location_y_error=errors,component=component))
    return candidates,[l,t,r,b]


def analyze_ticks(image,config=None,output='artifacts/ticks'):
    config=dict(config or {});out=Path(output);out.mkdir(parents=True,exist_ok=True)
    with Image.open(image) as im:
        if im.width*im.height>30_000_000:raise ValueError('Image exceeds 30 megapixels')
        rgb=np.asarray(im.convert('RGB'));size=list(im.size)
    invert=float(np.median(rgb))<100
    scales=[min(s,(budget/(size[0]*size[1]))**.5) for s,budget in [(2.,15_000_000),(3.,28_000_000)]]
    scans=[read_text(image,scale=s,invert=invert) for s in scales]
    tokens,disagreements=consensus_tokens(scans[0]['tokens'],scans[1]['tokens'])
    # Retain rejected bare/abbreviated ticks too, beyond the bar reader grammar.
    for scan in scans:
        for token in scan['tokens']:
            if parse_tick(token['text']) and not any(t['text']==token['text'] and np.linalg.norm(np.array(_center(t))-_center(token))<4 for t in tokens):
                disagreements.append(dict(token=token,reason='Numeric token lacks two-pass consensus.'))
    lines=horizontal_gridlines(rgb);binding=bind_ticks(tokens,lines,size,config.get('source') or config.get('post_url') or str(image))
    geometry=dict(image=str(image),size=size,roi=[0,0,*size],series=[],warnings=[],quality_issues=[],status='needs_review',method='local numeric grid labels + continuous colored component')
    recovery=[];reasons=[];candidates=[]
    # One matching axis may belong to one panel of a larger dashboard; multiple
    # numeric axes are left for panel/series disambiguation.
    if len(binding['axes'])!=1:reasons.append('Need one unambiguous numeric axis with at least three grid-aligned labels.')
    else:
        axis=binding['axes'][0];candidates,roi=trace_axis_curve(rgb,axis);geometry['roi']=roi
        contested=[]
        for d in disagreements:
            token=d['token'];x,y,w,h=token['box']
            edge=x+w if axis['side']=='left' else x
            positions=[o['box'][0]+o['box'][2] if axis['side']=='left' else o['box'][0] for o in axis['observations']]
            if min(abs(edge-p) for p in positions)<max(12,w*.25) and roi[1]<=y+h/2<=roi[3]:contested.append(d)
        binding['contested_axis_tokens']=contested
        if contested:reasons.append('A numeric reading on this axis lacks OCR consensus; review it before calibration.')
        if len(candidates)!=1:reasons.append('Need exactly one complete, continuous colored curve in the local axis region.')
        if not reasons:
            series=dict(candidates[0],id='series_0');geometry.update(series=[series],status='extracted')
            tolerance=config.get('pixel_error',2.5)+max(series['x_location_y_error'])
            cal=calibrate(series['coordinates'],axis['anchors'],scale=config.get('scale','unknown'),pixel_error=tolerance)
            cal['assumptions']+=['Recovered samples follow the rendered curve at normalized X positions; original observation dates and counts are not inferred.',
                                  'Output bounds add one image-column location error, using the largest local Y change.']
            recovery=[dict(series='series_0',unit=axis['unit'],**cal)]
            if cal['status']!='calibrated':reasons.append(cal.get('reason','Axis calibration remains unresolved.'))
    if not recovery:recovery=[dict(series='series_0',status='needs_correspondence',values=None,anchors_used=[],assumptions=[],reason=' '.join(reasons))]
    result=dict(image=str(image),image_sha256=hashlib.sha256(Path(image).read_bytes()).hexdigest(),config=config,
                status='calibrated' if recovery[0]['status']=='calibrated' else 'needs_evidence_or_review',geometry=geometry,recovery=recovery,
                correspondence=dict(status='matched' if not reasons else 'needs_review',reasons=reasons),binding=binding,curve_candidates=candidates,
                ocr=dict(passes=scans,tokens=tokens,rejected=disagreements),trace=[dict(step='read_y_ticks',axes=len(binding['axes']),next_actions=reasons)])
    (out/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False), encoding="utf-8");overlay(image,geometry,out/'overlay.png')
    with (out/'data.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f);writer.writerow(['x_fraction','pixel_x','pixel_y','value','lower','upper','unit','status'])
        if geometry['series']:
            cal=recovery[0]
            for i,p in enumerate(geometry['series'][0]['points']):
                value=lambda k:cal[k][i] if cal.get(k) is not None else ''
                writer.writerow([p['x_fraction'],p['x'],p['y'],value('values'),value('lower'),value('upper'),cal['unit'],cal['status']])
    return result
