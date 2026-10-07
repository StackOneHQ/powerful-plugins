"""Image-only layout and label correspondence for isolated bar cards.

OCR is replicated with two rescalings. Agreement is a quality gate, not
independent corroboration. Unknown scale and missing amounts still abstain.
"""
import re
import numpy as np
from PIL import Image
from .layout import detect_bars
from .ocr import read_text

MONEY=re.compile(r'^(?P<currency>[$€£])(?P<number>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)$')
MONTH=re.compile(r'^(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|M\d{1,2})$',re.I)
METRICS={'revenue':'revenue','mrr':'mrr','arr':'arr','sales':'sales'}


def _center(token):
    x,y,w,h=token['box'];return x+w/2,y+h/2


def consensus_tokens(first,second):
    """Only exact text agreements at the same location survive."""
    accepted=[];rejected=[]
    for a in first:
        x,y=_center(a)
        matches=[b for b in second if abs(_center(b)[0]-x)<=max(3,a['box'][2]*.15)
                 and abs(_center(b)[1]-y)<=max(3,a['box'][3]*.4)]
        same=[b for b in matches if b['text']==a['text'] and min(a['confidence'],b['confidence'])>=55]
        if len(same)==1:
            accepted.append(dict(a,confidence=min(a['confidence'],same[0]['confidence']),passes=2))
        elif MONEY.fullmatch(a['text']) or MONTH.fullmatch(a['text']) or a['text'].lower() in METRICS:
            rejected.append(dict(token=a,reason='Two OCR scales did not agree confidently at this location.',alternatives=[b['text'] for b in matches]))
    for b in second:
        if MONEY.fullmatch(b['text']) and not any(a['text']==b['text'] and abs(_center(a)[0]-_center(b)[0])<3 and abs(_center(a)[1]-_center(b)[1])<3 for a in accepted):
            rejected.append(dict(token=b,reason='Amount in the second OCR pass lacks consensus.',alternatives=[]))
    return accepted,rejected


def bind_bar_labels(candidate,tokens,source,size):
    points=candidate['points'];left,top,right,base=candidate['roi'];height=size[1]
    headers=[t for t in tokens if t['text'].lower() in METRICS and left-20<=_center(t)[0]<=right+20
             and max(0,top-height*.35)<=_center(t)[1]<top-4]
    decisions=[];anchors=[];labels=[]
    if len(headers)!=1:
        return dict(anchors=[],decisions=[dict(status='rejected',reason='Need one unambiguous metric heading above the candidate bars.')],labels=[])
    near=[t for t in tokens if base+2<=_center(t)[1]<=base+min(120,height*.22)]
    for i,p in enumerate(points):
        lo=left-5 if i==0 else (points[i-1]['x']+p['x'])/2
        hi=right+5 if i==len(points)-1 else (p['x']+points[i+1]['x'])/2
        column=[t for t in near if lo<=_center(t)[0]<hi]
        periods=[t for t in column if MONTH.fullmatch(t['text'])]
        amounts=[t for t in column if MONEY.fullmatch(t['text'])]
        if len(periods)!=1:
            return dict(anchors=[],decisions=[dict(status='rejected',point_index=i,reason='Need exactly one date/category label beneath every bar.')],labels=[])
        period=periods[0];labels.append(period['text'])
        # Amount belongs immediately below its own category row, not a distant
        # footer or another card. Multiple amounts are ambiguous.
        amounts=[t for t in amounts if 0<_center(t)[1]-_center(period)[1]<max(38,period['box'][3]*3)]
        if len(amounts)>1:
            return dict(anchors=[],decisions=[dict(status='rejected',point_index=i,reason='Multiple amounts beneath one category; automatic correspondence is ambiguous.')],labels=labels)
        if len(amounts)!=1:
            decisions.append(dict(status='rejected',point_index=i,reason='No unique consensus amount immediately below the category label.'))
            continue
        token=amounts[0];m=MONEY.fullmatch(token['text']);number=m['number'].replace(',','')
        value=float(number);decimals=len(number.split('.')[1]) if '.' in number else 0
        half=.5*10**-decimals
        anchors.append(dict(series='series_0',point_index=i,low=value-half,high=value+half,
                            source=f'{source} — image label {token["text"]} under {period["text"]}',matched=True,
                            currency=m['currency'],label_box=token['box'],period_label=period['text'],
                            assumptions=['Two OCR rescalings agree; correlated recognition errors remain possible.',
                                         'The amount immediately below a bar category denotes that bar on the single detected metric card.',
                                         'Displayed monetary values are rounded to the nearest shown decimal place.']))
        decisions.append(dict(status='accepted',point_index=i,text=token['text'],period_label=period['text'],box=token['box']))
    if len(set(x.lower() for x in labels))!=len(labels):
        return dict(anchors=[],decisions=[dict(status='rejected',reason='Repeated category labels cannot establish unique correspondence.')],labels=labels)
    currencies={a['currency'] for a in anchors}
    if len(currencies)>1:
        return dict(anchors=[],decisions=[dict(status='rejected',reason='Mixed currency symbols under one candidate series.')],labels=labels)
    return dict(anchors=anchors,decisions=decisions,labels=labels,metric=METRICS[headers[0]['text'].lower()],
                currency=next(iter(currencies),None),date_note='Printed labels retained verbatim; no year or publication-relative date inferred.')


def inspect_bar_card(path,source=None):
    layout=detect_bars(path);size=layout['size']
    with Image.open(path) as im:
        invert=float(np.median(np.asarray(im.convert('L'))))<100
    # Bound enlarged inputs while improving small dashboard typography.
    s1=min(2.,(15_000_000/(size[0]*size[1]))**.5)
    s2=min(3.,(28_000_000/(size[0]*size[1]))**.5)
    passes=[read_text(path,scale=s,invert=invert) for s in (s1,s2)]
    tokens,rejected=consensus_tokens(passes[0]['tokens'],passes[1]['tokens'])
    if len(layout['candidates'])==1:
        left,top,right,base=layout['candidates'][0]['roi']
        region=[max(0,int(left)-15),min(size[1]-1,int(base)+3),min(size[0],int(right)+16),min(size[1],int(base+min(120,size[1]*.22))+1)]
        footer=[read_text(path,scale=s,invert=invert,region=region,psm=11) for s in (s1,s2)]
        feet,disagreements=consensus_tokens(footer[0]['tokens'],footer[1]['tokens'])
        tokens=[t for t in tokens if _center(t)[1]<region[1]]+feet
        rejected=[d for d in rejected if _center(d['token'])[1]<region[1]]+disagreements
        passes+=footer
    ocr=dict(available=all(p['available'] for p in passes),tokens=tokens,text=' '.join(t['text'] for t in tokens),
             passes=passes,rejected=rejected,warning='Agreement between OCR passes is not independent factual verification.')
    geometry=dict(image=str(path),size=size,roi=[0,0,*size],series=[],quality_issues=[],warnings=[],
                  status='needs_review',method=layout['method'])
    binding=dict(anchors=[],decisions=[],labels=[])
    if len(layout['candidates'])!=1:
        geometry['warnings'].append('Automatic mode supports one isolated vertical bar card; no unique layout was found.')
    else:
        candidate=layout['candidates'][0]
        geometry.update(roi=candidate['roi'],series=[dict(candidate,id='series_0')],status='extracted')
        binding=bind_bar_labels(candidate,tokens,source or 'Input image',size)
        # Do not obtain a convenient calibration by silently discarding a
        # monetary reading that disagrees between passes in the label strip.
        contested=[d for d in rejected if MONEY.fullmatch(d['token']['text'])
                   and candidate['roi'][3]<_center(d['token'])[1]<candidate['roi'][3]+min(120,size[1]*.22)]
        if contested:
            binding['anchors']=[]
            binding['decisions'].append(dict(status='rejected',reason='Unresolved monetary OCR disagreement beneath the bars; automatic calibration withheld.',tokens=contested))
    return dict(geometry=geometry,layout=layout,ocr=ocr,binding=binding)
