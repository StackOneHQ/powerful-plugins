"""Frozen procedural test of the explicitly unchecked caption hypothesis."""
from pathlib import Path
from .render_cache import configure_cache
configure_cache()
from matplotlib import font_manager
from datetime import datetime,timezone
import hashlib
import io
import json
import os
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from .first_customer import recover_first_customer

ROOT=Path(__file__).resolve().parent.parent
SOURCE='https://x.com/synthetic_fixture/status/123456789'
CAPTION='Got my first paying customer 10 days after I launched a new startup!'


def generate(folder,seed,renderer,style):
    p=Path(folder);p.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(seed)
    w,h=1000,620;dark=style=='dark';bg='#15191d' if dark else '#ffffff'
    fg='#edf2f7' if dark else '#202b3a';color=['#4b71d2','#8362d6','#26a47b'][seed%3]
    left,right,top,bottom=65,940,265,540
    amount=round(float(rng.uniform(30,900)),2);start=float(rng.uniform(.85,.95))
    xs=np.array([left,left+start*(right-left),right]);ys=np.array([bottom,bottom,top])
    if renderer=='pillow':
        im=Image.new('RGB',(w,h),bg);d=ImageDraw.Draw(im)
        font=lambda n:ImageFont.truetype(font_manager.findfont('DejaVu Sans'),n)
        d.text((65,45),'Monthly Recurring Revenue',font=font(26),fill=fg)
        d.text((65,100),f'${amount:,.2f}',font=font(55),fill=fg)
        d.text((65,195),'September 2026',font=font(20),fill=fg)
        if style=='filled':d.polygon([(left,bottom),*zip(xs,ys),(right,bottom)],fill='#dbe5ff')
        d.line(list(zip(xs,ys)),fill=color,width=3)
        d.text((55,560),'Sep 1',font=font(18),fill=fg);d.text((875,560),'Sep 30',font=font(18),fill=fg)
    else:
        from .render_cache import configure_cache
        configure_cache()
        import matplotlib
        matplotlib.use('Agg')
        from matplotlib import pyplot as plt
        fig=plt.figure(figsize=(10,6.2),dpi=100,facecolor=bg)
        ax=fig.add_axes([0,0,1,1]);ax.set_xlim(0,w);ax.set_ylim(h,0);ax.axis('off')
        ax.text(65,65,'Monthly Recurring Revenue',fontsize=20,color=fg)
        ax.text(65,155,f'${amount:,.2f}',fontsize=42,color=fg)
        ax.text(65,215,'September 2026',fontsize=15,color=fg)
        if style=='filled':ax.fill_between(xs,ys,bottom,color=color,alpha=.16)
        ax.plot(xs,ys,color=color,lw=2)
        ax.text(55,580,'Sep 1',fontsize=14,color=fg);ax.text(875,580,'Sep 30',fontsize=14,color=fg)
        buffer=io.BytesIO();fig.savefig(buffer,format='png',dpi=100);plt.close(fig);buffer.seek(0);im=Image.open(buffer).convert('RGB')
    factor=.65 if style=='small' else 1.
    if factor!=1:im=im.resize((int(w*factor),int(h*factor)),Image.Resampling.LANCZOS)
    if style=='jpeg':
        buffer=io.BytesIO();im.save(buffer,format='JPEG',quality=45);buffer.seek(0);im=Image.open(buffer).convert('RGB')
    im.save(p/'chart.png')
    truth=dict(seed=seed,renderer=renderer,style=style,amount=amount,xs=(xs*factor).tolist(),ys=(ys*factor).tolist(),
               meaning='Private continuous drawn-line values. Interpolated samples are not daily accounting truth.')
    (p/'truth.json').write_text(json.dumps(truth,indent=2), encoding="utf-8")
    (p/'context.json').write_text(json.dumps(dict(source=SOURCE,post_text=CAPTION,synthetic_fixture=True),indent=2), encoding="utf-8")


def score(result,truth):
    row={k:truth[k] for k in ('seed','renderer','style')};row.update(status=result['status'],success=False)
    if not result['recovery']:return row
    points=result['geometry']['series'][0]['points'];cal=result['recovery'][0]
    xx=np.array([p['x'] for p in points]);yy=np.array([p['y'] for p in points])
    tx=np.array(truth['xs']);ty=np.array(truth['ys']);true_y=np.interp(xx,tx,ty)
    ref=(ty[0]-true_y)/(ty[0]-ty[-1])*truth['amount'];pred=np.array(cal['values'])
    # Exclude the zero plateau and headline endpoint anchors. Score the
    # interior of the visible connecting segment separately; this remains
    # a deliberately simple, non-daily numerical test.
    mask=(xx>tx[1]+4)&(xx<tx[-1]-4)
    if mask.sum()<5:row['reason']='Insufficient interior rise samples';return row
    nmae=float(np.mean(np.abs(pred[mask]-ref[mask]))/truth['amount'])
    coverage=float(np.mean((np.array(cal['lower'])[mask]<=ref[mask])&(ref[mask]<=np.array(cal['upper'])[mask])))
    complete=abs(xx[0]-tx[0])<=4 and abs(xx[-1]-tx[-1])<=4
    row.update(nmae=nmae,interior_curve_samples=int(mask.sum()),interval_coverage=coverage,
               complete_trace=bool(complete),max_trace_error=float(np.max(np.abs(yy-true_y))),
               success=bool(nmae<.02 and complete and cal['scale']=='linear'))
    return row


def run(output,seed=240000):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    if (out/'protocol.json').exists():raise ValueError('Use a fresh output directory')
    (out/'source').mkdir()
    for p in (ROOT/'chart_recover').glob('*.py'):(out/'source'/p.name).write_bytes(p.read_bytes())
    protocol=dict(frozen_at=datetime.now(timezone.utc).isoformat(),seed=seed,cases=20,
        source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (out/'source').glob('*.py')},
        input='Image plus original-source-shaped synthetic URL and first-customer caption; no values, geometry, baseline or scale supplied.',
        scoring='After inference read private truth. Require complete trace within 4px, linear scale and <2% normalized error on interior rise samples excluding zero/endpoint anchors.',
        limitations='Simple flat-then-rising cards only. Source claims are true by construction. No daily accounting truth or independent public accuracy. The hypothesis has no unused numerical checks.')
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2), encoding="utf-8");rows=[];controls=[]
    styles=['light','dark','filled','jpeg','small']
    for ri,renderer in enumerate(['pillow','matplotlib']):
        for j in range(10):
            case_seed=seed+ri*1000+j;p=out/f'{renderer}-{case_seed}'
            generate(p,case_seed,renderer,styles[j%5]);config=json.loads((p/'context.json').read_text(encoding="utf-8"))
            r=recover_first_customer(p/'chart.png',config,p/'analysis')
            rows.append(score(r,json.loads((p/'truth.json').read_text(encoding="utf-8"))))
            print(renderer,case_seed,rows[-1]['status'],rows[-1]['success'],flush=True)
            (out/'cases.json').write_text(json.dumps(rows,indent=2), encoding="utf-8")
    # Reuse existing images: controls add no unique chart images.
    negative=['I hope I get my first paying customer.','Got my first paying customer last year.',
              'Got my first paying customer for my second product.','Got my first paying customer again.',
              'Got my first paying customer? This is a forecast.','We already had subscribers, but got my first paying customer.',
              'Got my first customer.','Just hit $800 MRR.']
    for i,caption in enumerate(negative):
        image=out/f'pillow-{seed+i}'/'chart.png'
        r=recover_first_customer(image,dict(source=SOURCE,post_text=caption),out/f'control-{i}')
        controls.append(dict(caption=caption,status=r['status'],abstained=not r['recovery']))
    summary=dict(protocol=protocol,cases=len(rows),passed=sum(r['success'] for r in rows),
        abstentions=sum(r['status']!='conditional_calibration' for r in rows),
        returned_failures=sum(r['status']=='conditional_calibration' and not r['success'] for r in rows),rows=rows,controls=controls)
    (out/'summary.json').write_text(json.dumps(summary,indent=2), encoding="utf-8");return summary


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--seed',type=int,default=240000)
    a=p.parse_args();r=run(a.out,a.seed)
    print(json.dumps({k:v for k,v in r.items() if k not in ('protocol','rows','controls')},indent=2))
