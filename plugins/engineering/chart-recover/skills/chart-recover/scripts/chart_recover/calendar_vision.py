"""Calendar layout and OCR, preserving image locations and unresolved cells.

The month/year and weekday row determine dates; amount crops are rearranged
into a single-column OCR atlas. This supplies layout to Tesseract without
adding text or numeric values to the source evidence.
"""
from pathlib import Path
import calendar
import datetime as dt
import json
import re
import numpy as np
from PIL import Image,ImageOps
from .ocr import read_text
from .autopilot import MONEY,consensus_tokens,_center

MONTHS={name.lower():i for i in range(1,13) for name in (calendar.month_name[i],calendar.month_abbr[i])}
WEEKDAYS=[['M','T','W','T','F','S','S'],['S','M','T','W','T','F','S']]


def _weekday(text):
    value=text.strip('()[]{}.,').upper()
    return value[0] if value and len(set(value))==1 and value[0] in 'MTWFS' else None


def titles(tokens):
    found=[]
    for month in tokens:
        m=MONTHS.get(month['text'].lower())
        if not m:continue
        x,y,w,h=month['box']
        years=[t for t in tokens if re.fullmatch(r'20\d{2}',t['text']) and 0<=t['box'][0]-x-w<=h*2
               and abs(_center(t)[1]-_center(month)[1])<=h*.6]
        if len(years)==1:
            year=years[0];found.append(dict(month=m,year=int(year['text']),box=[x,y,year['box'][0]+year['box'][2]-x,max(h,year['box'][3])]))
    return found


def weekday_rows(tokens):
    rows=[];seen=set()
    for t in tokens:
        if _weekday(t['text']) is None:continue
        cy=_center(t)[1]
        row=[r for r in tokens if _weekday(r['text']) is not None and abs(_center(r)[1]-cy)<=max(3,t['box'][3]*.5)]
        row.sort(key=lambda r:_center(r)[0])
        # A page can contain another text row at the same y. Search every
        # contiguous seven-token window rather than mixing calendar columns.
        for start in range(max(0,len(row)-6)):
            part=row[start:start+7];letters=[_weekday(r['text']) for r in part]
            if letters not in WEEKDAYS:continue
            xs=[_center(r)[0] for r in part];gap=float(np.median(np.diff(xs)))
            if gap<12 or max(abs(np.diff(xs)-gap))>gap*.18:continue
            key=tuple(round(x) for x in xs)+(round(cy),)
            if key in seen:continue
            seen.add(key);rows.append(dict(centers=xs,y=float(np.mean([_center(r)[1] for r in part])),step=gap,
                                          first_weekday=0 if letters==WEEKDAYS[0] else 6))
    return rows


def locate_calendar(tokens,size):
    candidates=[]
    for title in titles(tokens):
        tx,ty,tw,th=title['box']
        for weekday in weekday_rows(tokens):
            xs=weekday['centers'];step=weekday['step'];wy=weekday['y']
            if not 0<wy-ty<max(100,size[1]*.18) or not xs[0]-step<tx<xs[-1]+step:continue
            money=[t for t in tokens if MONEY.fullmatch(t['text']) and xs[0]-step/2<_center(t)[0]<xs[-1]+step/2
                   and wy+6<_center(t)[1]<min(size[1],wy+step*7)]
            if len(money)<8:continue
            groups=[]
            for t in sorted(money,key=lambda t:_center(t)[1]):
                y=_center(t)[1]
                if groups and abs(y-np.mean([_center(a)[1] for a in groups[-1]]))<max(5,t['box'][3]*.65):groups[-1].append(t)
                else:groups.append([t])
            offset=(dt.date(title['year'],title['month'],1).weekday()-weekday['first_weekday'])%7
            days=calendar.monthrange(title['year'],title['month'])[1];weeks=(offset+days+6)//7
            if not max(3,weeks-1)<=len(groups)<=weeks:continue
            ys=[float(np.median([_center(a)[1] for a in g])) for g in groups]
            rowstep=float(np.median(np.diff(ys)))
            if not step*.55<rowstep<step*1.8 or max(abs(np.diff(ys)-rowstep))>rowstep*.15:continue
            # A final highlighted/hidden week can have no readable amount in
            # whole-image OCR. Its row exists in the calendar model; isolated
            # OCR still has to read each value. Never shift the first week.
            if not 8<ys[0]-wy<step*1.05:continue
            extrapolated=weeks-len(ys)
            if extrapolated:
                ys.append(ys[-1]+rowstep)
                if ys[-1]+rowstep*.5>=size[1]:continue
            glyph=float(np.median([a['box'][3] for a in money]))
            if glyph>rowstep*.42:continue
            candidates.append(dict(**title,weekday=weekday,offset=offset,days=days,weeks=weeks,
                                   row_centers=ys,row_step=rowstep,glyph_height=glyph,extrapolated_trailing_rows=extrapolated))
    # Repeated title proposals for one spatial grid are not separate evidence.
    unique={json.dumps([c['year'],c['month'],c['weekday']['centers'],c['row_centers']]):c for c in candidates}
    return list(unique.values())


def weekday_strip_proposals(tokens,size):
    """Use seven regularly spaced money columns to isolate tiny weekday text."""
    proposals=[]
    for title in titles(tokens):
        tx,ty,tw,th=title['box']
        money=[t for t in tokens if MONEY.fullmatch(t['text']) and _center(t)[1]>ty+th+20]
        groups=[]
        for t in sorted(money,key=lambda t:_center(t)[0]):
            x=_center(t)[0]
            if groups and abs(x-np.median([_center(a)[0] for a in groups[-1]]))<max(8,t['box'][3]*.6):groups[-1].append(t)
            else:groups.append([t])
        for start in range(max(0,len(groups)-6)):
            part=groups[start:start+7];xs=[float(np.median([_center(a)[0] for a in g])) for g in part]
            step=float(np.median(np.diff(xs)))
            if step<15 or max(abs(np.diff(xs)-step))>step*.15:continue
            if not xs[0]-step<tx<xs[-1]+step:continue
            marks=[a for g in part for a in g];first_y=min(_center(a)[1] for a in marks);glyph=float(np.median([a['box'][3] for a in marks]))
            if not th+20<first_y-ty<step*2.5:continue
            region=[max(0,int(xs[0]-step*.52)),int(ty+th+5),min(size[0],int(xs[-1]+step*.52)+1),int(first_y-glyph)]
            if region[3]-region[1]>=8:proposals.append(region)
    return list({tuple(r):r for r in proposals}.values())


def _atlas_readings(ocr,cells,stride,pad):
    readings=[]
    for i,cell in enumerate(cells):
        row=[t for t in ocr['tokens'] if pad+i*stride<=_center(t)[1]<pad+i*stride+cell['height']]
        row.sort(key=lambda t:t['box'][0]);text=''.join(t['text'] for t in row)
        m=MONEY.fullmatch(text)
        readings.append(dict(text=text,confidence=min((t['confidence'] for t in row),default=0),
                             value=float(m['number'].replace(',','')) if m else None,
                             currency=m['currency'] if m else None,tokens=row))
    return readings


def read_calendar(path,output,source=None):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    im=Image.open(path)
    if im.width*im.height>30_000_000:raise ValueError('Image exceeds 30 megapixels')
    im=im.convert('RGB');size=list(im.size);invert=float(np.median(np.asarray(im.convert('L'))))<100
    scales=[min(s,(28_000_000/(im.width*im.height))**.5) for s in (2.,3.)]
    passes=[read_text(path,scale=s,invert=invert) for s in scales]
    # Weekday glyphs have a common OCR capitalization/duplication variant.
    normalized=[]
    for p in passes:
        normalized.append([dict(t,text='W' if t['text'].upper()=='WW' else t['text'].upper() if len(t['text'])==1 and t['text'].upper() in 'MTWFS' else t['text']) for t in p['tokens']])
    tokens,rejected=consensus_tokens(*normalized)
    # Grid proposals can use the first pass's money locations, never its values.
    # Missing OCR agreement is resolved separately in isolated amount crops.
    layout_tokens=list(tokens)
    for t in normalized[0]:
        proposed_weekday=t['text'].upper() in ('M','T','W','F','S') and t['confidence']>=70
        if (proposed_weekday or MONEY.fullmatch(t['text'])) and not any(t['text']==a['text'] and abs(_center(t)[0]-_center(a)[0])<3 and abs(_center(t)[1]-_center(a)[1])<3 for a in layout_tokens):
            layout_tokens.append(t)
    candidates=locate_calendar(layout_tokens,size);header_passes=[]
    if not candidates:
        for region in weekday_strip_proposals(layout_tokens,size):
            scans=[read_text(path,scale=s,invert=invert,region=region,psm=6) for s in (3.,4.)]
            header_passes.append(dict(region=region,ocr=scans))
            rows=[weekday_rows(p['tokens']) for p in scans]
            if len(rows[0])==len(rows[1])==1 and rows[0][0]['first_weekday']==rows[1][0]['first_weekday'] and max(abs(np.array(rows[0][0]['centers'])-rows[1][0]['centers']))<4:
                # The complete seven-day pattern agrees even when isolated
                # letter confidence is low; monetary thresholds are unchanged.
                region_tokens=[t for t in layout_tokens if not region[1]<=_center(t)[1]<=region[3]]+scans[0]['tokens']
                candidates.extend(locate_calendar(region_tokens,size))
    result=dict(image=str(path),size=size,source=source or 'Input image',status='needs_review',
                full_image_ocr=passes,weekday_strip_ocr=header_passes,consensus_tokens=tokens,ocr_disagreements=rejected,
                layout_candidates=candidates,observations=[],decisions=[])
    if len(candidates)!=1:
        result['reason']='No unique month/year, weekday row and regular monetary grid found.'
        (out/'calendar.json').write_text(json.dumps(result,indent=2), encoding="utf-8");return result
    layout=candidates[0];step=layout['weekday']['step'];glyph=layout['glyph_height'];cells=[]
    for row,y in enumerate(layout['row_centers']):
        for col,x in enumerate(layout['weekday']['centers']):
            day=row*7+col-layout['offset']+1
            box=[max(0,int(x-step*.47)),max(0,int(y-glyph*.85)),min(im.width,int(x+step*.47)+1),min(im.height,int(y+glyph*.85)+1)]
            date=f"{layout['year']:04d}-{layout['month']:02d}-{day:02d}" if 1<=day<=layout['days'] else None
            cells.append(dict(date=date,box=box,width=box[2]-box[0],height=box[3]-box[1],row=row,column=col))
    pad=12;stride=max(c['height'] for c in cells)+18
    atlas=Image.new('RGB',(max(c['width'] for c in cells)+pad*2,len(cells)*stride+pad*2),'white')
    for i,cell in enumerate(cells):
        crop=im.crop(cell['box']).convert('L')
        if float(np.median(np.asarray(crop)))<128:crop=ImageOps.invert(crop)
        atlas.paste(crop.convert('RGB'),(pad,pad+i*stride))
    atlas_path=out/'amount-atlas.png';atlas.save(atlas_path)
    atlas_passes=[read_text(atlas_path,scale=s,psm=6) for s in (3.,4.)]
    reads=[_atlas_readings(p,cells,stride,pad) for p in atlas_passes]
    result.update(layout=layout,atlas=dict(path=str(atlas_path),cells=cells,stride=stride,padding=pad,ocr=atlas_passes))
    outside=False
    for cell,a,b in zip(cells,*reads):
        accepted=a['value'] is not None and a['text']==b['text'] and min(a['confidence'],b['confidence'])>=55
        decision=dict(date=cell['date'],box=cell['box'],readings=[a,b],status='accepted' if accepted else 'unresolved')
        if accepted and cell['date'] is None:
            outside=True;decision.update(status='rejected',reason='A monetary cell falls outside the printed month; adjacent-month layout needs review.')
        elif accepted:
            number=MONEY.fullmatch(a['text'])['number'];digits=len(number.split('.')[1]) if '.' in number else 0;half=.5*10**-digits
            result['observations'].append(dict(date=cell['date'],value=a['value'],low=a['value']-half,high=a['value']+half,
                                               currency=a['currency'],box=cell['box'],text=a['text'],confidence=min(a['confidence'],b['confidence']),
                                               source=f"{result['source']} — calendar cell {cell['date']}"))
        result['decisions'].append(decision)
    currencies={o['currency'] for o in result['observations']}
    result['status']='read' if not outside and len(currencies)==1 and len(result['observations'])>=8 else 'needs_review'
    result['assumptions']=['Grid dates follow the printed month/year and weekday order.',
                           'The weekday grid may use a confident first-pass glyph where the second OCR pass is uncertain; monetary observations require agreement.',
                           'A regular grid can extend to one trailing week with no whole-image money readings; isolated cell OCR is still required for every observation.',
                           'Displayed amounts are rounded to the nearest printed decimal place.',
                           'Two OCR rescalings agree; correlated recognition errors remain possible.',
                           'The calendar metric and its correspondence to a plot are not established by OCR alone.']
    (out/'calendar.json').write_text(json.dumps(result,indent=2), encoding="utf-8");return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('image');p.add_argument('--out',default='artifacts/calendar');p.add_argument('--source')
    a=p.parse_args();r=read_calendar(a.image,a.out,a.source)
    print(json.dumps(dict(status=r['status'],observations=len(r['observations']),dates=[o['date'] for o in r['observations']],reason=r.get('reason')),indent=2))
