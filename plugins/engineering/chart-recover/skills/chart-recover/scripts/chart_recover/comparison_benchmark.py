"""Frozen image-only evaluation of the explicitly linear two-total hypothesis."""
from pathlib import Path
from .render_cache import configure_cache
configure_cache()
from matplotlib import font_manager
from datetime import datetime,timezone
import hashlib
import io
import itertools
import json
import os
import shutil
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageColor
from .comparison_totals import recover_comparison

ROOT=Path(__file__).resolve().parent.parent


def generate(folder,seed,renderer,style,n,pattern,control=None):
    out=Path(folder);out.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(seed)
    w,h=1100,720;left,right,top,bottom=55,1045,255,640
    dark=style=='dark';bg='#111820' if dark else '#ffffff';fg='#f5f5ef' if dark else '#25334b'
    colors=[('#7352cf','#ef9bdf'),('#327cc9','#d58235'),('#348c63','#bd5195')][seed%3]
    if style=='pale':colors=(colors[0],'#%02x%02x%02x'%tuple(round(.2*255+.8*c) for c in ImageColor.getrgb(colors[1])))
    values=rng.lognormal(5.4,.62,(2,n));values[0]*=1.65
    if pattern=='sparse':values[rng.random((2,n))<.65]=0
    else:values+=float(rng.uniform(35,200))
    if control=='equal_totals':values[1]*=values[0].sum()/values[1].sum()
    totals=values.sum(axis=1)
    axis='log' if control=='log_axis' else 'linear'
    if axis=='log':values+=25;totals=values.sum(axis=1)
    transformed=np.log10(values) if axis=='log' else values
    low=float(transformed.min());high=float(transformed.max());span=high-low
    low-=span*rng.uniform(.07,.2);high+=span*rng.uniform(.02,.12)
    ys=bottom-(transformed-low)/(high-low)*(bottom-top);xs=np.linspace(left,right,n)
    if control=='irregular_spacing':xs[1:-1]+=rng.uniform(-.2,.2,n-2)*(right-left)/(n-1)
    if control=='independent_axes':ys[1]=bottom-30-(values[1]-values[1].min())/np.ptp(values[1])*(bottom-top-80)
    month={28:'Feb',30:'Apr',31:'May'}[n]
    heading='MRR' if control=='mrr' else 'All revenue'
    second=f"vs. {'€' if control=='mixed_currency' else '$'}{totals[1]:,.2f} last period"
    if control=='missing_comparison':second=f'${totals[1]:,.2f}'
    displayed_n=n-1 if control=='wrong_count' else n
    labels=[(left,40,heading,24),(left,92,f'${totals[0]:,.2f}',38),(left,160,second,23),
            (left,670,f'1 {month}',20),(right-70,670,f'{displayed_n} {month}',20)]
    if control=='missing_total':labels.pop(2)
    if renderer=='pillow':
        im=Image.new('RGB',(w,h),bg);d=ImageDraw.Draw(im)
        for x,y,text,size in labels:d.text((x,y),text,font=ImageFont.truetype(font_manager.findfont('DejaVu Sans'),size),fill=fg)
        for j in range(2):
            x=xs;y=ys[j]
            if control=='incomplete' and j==1:x=x[3:];y=y[3:]
            if control=='smooth':
                from scipy.interpolate import PchipInterpolator
                xx=np.linspace(x[0],x[-1],1000);y=PchipInterpolator(x,y)(xx);x=xx
            d.line(list(zip(x,y)),fill=colors[j],width=3)
        if control=='third_curve':d.line(list(zip(xs,(ys[0]+ys[1])/2)),fill='#da4438',width=3)
    else:
        from .render_cache import configure_cache
        configure_cache()
        import matplotlib
        matplotlib.use('Agg')
        from matplotlib import pyplot as plt
        fig=plt.figure(figsize=(w/100,h/100),dpi=100,facecolor=bg)
        ax=fig.add_axes([0,0,1,1]);ax.set_xlim(0,w);ax.set_ylim(h,0);ax.axis('off')
        for x,y,text,size in labels:ax.text(x,y,text,fontsize=size*.72,color=fg,va='top',fontfamily='DejaVu Sans')
        for j in range(2):ax.plot(xs,ys[j],color=colors[j],lw=2,solid_capstyle='butt')
        b=io.BytesIO();fig.savefig(b,format='png',dpi=100);plt.close(fig);b.seek(0);im=Image.open(b).convert('RGB')
    factor=.7 if style=='small' else 1.
    if factor!=1:im=im.resize((round(w*factor),round(h*factor)),Image.Resampling.LANCZOS)
    if style=='jpeg':
        b=io.BytesIO();im.save(b,format='JPEG',quality=45);b.seek(0);im=Image.open(b).convert('RGB')
    im.save(out/'chart.png')
    truth=dict(seed=seed,renderer=renderer,style=style,count=n,pattern=pattern,control=control,axis=axis,
               values=values.tolist(),xs=(xs*factor).tolist(),ys=(ys*factor).tolist(),totals=totals.tolist())
    (out/'truth.json').write_text(json.dumps(truth,indent=2), encoding="utf-8")


def score(result,truth):
    row={k:truth[k] for k in ('seed','renderer','style','count','pattern','control')}
    row.update(status=result['status'],passed=False,reasons=result['reasons'])
    if result['status']!='conditional_calibration':return row
    s=result['geometry']['series'];rs=result['recovery'];n=truth['count']
    if len(s)!=2 or any(len(a['points'])!=n for a in s):row['reason']='Wrong curve or observation count';return row
    actual=np.asarray(truth['values']);true_y=np.asarray(truth['ys'])
    y=np.array([[p['y'] for p in a['points']] for a in s]);x=np.array([[p['x'] for p in a['points']] for a in s])
    order=min(itertools.permutations(range(2)),key=lambda ids:float(np.mean(abs(y-true_y[list(ids)]))))
    ref=actual[list(order)];pred=np.array([r['values'] for r in rs]);lower=np.array([r['lower'] for r in rs]);upper=np.array([r['upper'] for r in rs])
    nmae=np.mean(abs(pred-ref),axis=1)/np.ptp(ref,axis=1)
    x_error=float(np.max(abs(x-np.array(truth['xs']))));pixel_error=float(np.mean(abs(y-true_y[list(order)])))
    row.update(nmae=nmae.tolist(),max_x_error=x_error,mean_pixel_error=pixel_error,
               interval_coverage=float(np.mean((lower<=ref)&(ref<=upper))),evaluated_values=2*n,
               passed=bool(np.max(nmae)<.02 and x_error<=3 and truth['axis']=='linear' and truth['control']!='independent_axes'))
    return row


def run(output,seed=540000):
    out=Path(output)
    if out.exists():raise ValueError('Use a fresh output directory for a frozen evaluation')
    out.mkdir(parents=True)
    source=out/'source';source.mkdir()
    files=[p for p in (ROOT/'chart_recover').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    hashes={}
    for p in files:
        name=p.relative_to(ROOT);target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        hashes[str(name)]=hashlib.sha256(p.read_bytes()).hexdigest()
    protocol=dict(frozen_at=datetime.now(timezone.utc).isoformat(),seed=seed,cases=60,source_hashes=hashes,
        input='Image and synthetic source URL only; no numeric anchor, zero, ROI, colors, count or scale flag.',
        hypothesis='The reader explicitly assumes a shared linear axis and equal daily counts for the comparison periods.',
        scoring='Read private truth only after inference. Require both series, correct count, <=3px x error and <2% NMAE per series on every daily value. Report conditional coverage descriptively.',
        controls='Ten semantic/geometry controls, including smooth curves and irregular spacing, should abstain. Logarithmic and independent-axis stress cases deliberately violate unverified assumptions; report their outcomes separately, never as verified recoveries.',
        limitations='Procedural dashboard family; no independent public daily accounting truth. Image generation uses known truthful headline sums in the 60 linear cases.')
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2), encoding="utf-8");rows=[];controls=[]
    combinations=list(itertools.product(('pillow','matplotlib'),('light','dark','jpeg','small','pale'),(28,30,31),('dense','sparse')))
    for index,(renderer,style,n,pattern) in enumerate(combinations):
        folder=out/f'case-{index:03d}';generate(folder,seed+index,renderer,style,n,pattern)
        result=recover_comparison(folder/'chart.png',{'source':'https://example.com/synthetic_fixture/status/123'},folder/'recovery')
        row=score(result,json.loads((folder/'truth.json').read_text(encoding="utf-8")));row['case']=folder.name
        row['image_sha256']=hashlib.sha256((folder/'chart.png').read_bytes()).hexdigest();rows.append(row)
        print(folder.name,result['status'],row['passed'],flush=True)
    for index,control in enumerate(('mrr','mixed_currency','missing_comparison','missing_total','wrong_count','incomplete','third_curve','equal_totals','smooth','irregular_spacing','log_axis','independent_axes')):
        folder=out/f'control-{control}';generate(folder,seed+100+index,'pillow','light',31,'dense',control)
        result=recover_comparison(folder/'chart.png',{'source':'https://example.com/synthetic_fixture/status/123'},folder/'recovery')
        row=score(result,json.loads((folder/'truth.json').read_text(encoding="utf-8")));row['case']=folder.name
        stress=control in ('log_axis','independent_axes')
        row.update(control_kind='assumption_stress' if stress else 'expected_abstention',
                   abstained=result['status']!='conditional_calibration',unexpected_return=not stress and result['status']=='conditional_calibration')
        row['passed']=row['abstained'] if not stress else False
        controls.append(row)
    summary=dict(charts=len(rows),passed=sum(r['passed'] for r in rows),abstained=sum(r['status']!='conditional_calibration' for r in rows),
                 returned_failures=sum(r['status']=='conditional_calibration' and not r['passed'] for r in rows),
                 cases=rows,controls=controls,control_failures=sum(c['unexpected_return'] for c in controls),
                 assumption_stress_returns=sum(c['control_kind']=='assumption_stress' and not c['abstained'] for c in controls),completed_at=datetime.now(timezone.utc).isoformat())
    (out/'summary.json').write_text(json.dumps(summary,indent=2), encoding="utf-8");return summary


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--seed',type=int,default=540000)
    a=p.parse_args();r=run(a.out,a.seed);print({k:v for k,v in r.items() if k not in ('cases','controls')})
