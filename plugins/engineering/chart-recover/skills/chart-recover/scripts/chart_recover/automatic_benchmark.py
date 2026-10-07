"""Locked image-to-values evaluation, with private values scored afterward.

Two endpoint labels are visible; no ROI, kind, color, date positions, numeric
anchors, baseline or private truth enters analysis. Linear scale is disclosed.
Pillow and Matplotlib renderers vary dimensions, styling and bar sequences.
"""
from pathlib import Path
import hashlib
import json
import os
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from .render_cache import configure_cache
configure_cache()
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt,font_manager
from .pipeline import analyze

MONTHS=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug']
STYLES=['light','dark','gray','highlight','rounded','jpeg','small','truncated']


def generate_card(folder,seed,renderer='pillow',style='light',control=None):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(seed);n=int(rng.integers(4,9))
    width=int(rng.integers(650,1200));height=int(rng.integers(380,700))
    values=np.round(rng.uniform(1200,8000,n),2)
    # A declared generator distribution with separated endpoint facts, not a
    # post-extraction filter. Every generated sample is kept in the denominator.
    values[0]=round(rng.uniform(400,1200),2);values[-1]=round(rng.uniform(8000,11000),2)
    low=min(values)*.8 if style=='truncated' else 0.
    high=max(values)*1.13
    bg='#141b2c' if style=='dark' else '#ffffff';fg='#e0e5ed' if style=='dark' else '#344054'
    color='#8389ee';colors=[color]*n
    if style=='gray':colors=['#929aaa']*n
    if style=='highlight':colors=['#929aaa']*(n-1)+[color]
    show=[0,n-1] if control!='no_amounts' else []
    if control=='conflict':show=[0,n//2,n-1]
    amounts={i:values[i] for i in show}
    if control=='conflict':amounts[n//2]=values.max()*2
    labels=MONTHS[:n] if control!='no_periods' else ['Item']*n
    if renderer=='pillow':
        im=Image.new('RGB',(width,height),bg);draw=ImageDraw.Draw(im)
        fontpath=font_manager.findfont('DejaVu Sans')
        font=ImageFont.truetype(fontpath,14 if style=='small' else 17)
        titlefont=ImageFont.truetype(fontpath,22)
        draw.text((width*.07,25),'Revenue',font=titlefont,fill=fg)
        left=width*.08;right=width*.93;base=height*.76;top=height*.20
        spacing=(right-left)/n;bw=spacing*.65
        points=[]
        for i,v in enumerate(values):
            x=left+(i+.5)*spacing;y=base-(v-low)/(high-low)*(base-top)
            box=(round(x-bw/2),round(y),round(x+bw/2),round(base))
            if style=='rounded':draw.rounded_rectangle(box,radius=7,fill=colors[i])
            else:draw.rectangle(box,fill=colors[i])
            draw.text((x,base+14),labels[i],font=font,fill=fg,anchor='mt')
            if i in show:
                currency='€' if control=='mixed_currency' and i==n-1 else '$'
                draw.text((x,base+39),f'{currency}{amounts[i]:,.2f}',font=font,fill=fg,anchor='mt')
            points.append(dict(x=float(x),y=float(round(y))))
        if control=='footer':
            draw.text((width*.48,height-20),'Example: $99,999.00',font=font,fill=fg,anchor='mm')
        im.save(folder/'chart.png')
    else:
        fig,ax=plt.subplots(figsize=(width/100,height/100),dpi=100,facecolor=bg)
        fig.subplots_adjust(left=.07,right=.96,bottom=.24,top=.80);ax.set_facecolor(bg)
        ax.bar(np.arange(n),values-low,bottom=low,color=colors,width=.65)
        ax.set_ylim(low,high);ax.set_yticks([]);ax.set_xticks(np.arange(n),labels,color=fg,fontsize=10 if style=='small' else 12)
        ax.tick_params(length=0,pad=10)
        for sp in ax.spines.values():sp.set_visible(False)
        ax.set_title('Revenue',loc='left',pad=30,color=fg,fontsize=18)
        for i in show:
            currency='€' if control=='mixed_currency' and i==n-1 else '$'
            ax.text(i,-.16,f'{currency}{amounts[i]:,.2f}',transform=ax.get_xaxis_transform(),ha='center',va='top',color=fg,fontsize=10 if style=='small' else 12)
        fig.canvas.draw();coords=ax.transData.transform(np.c_[np.arange(n),values])
        points=[dict(x=float(x),y=float(height-y)) for x,y in coords]
        fig.savefig(folder/'chart.png',facecolor=bg,dpi=100);plt.close(fig)
    if style=='jpeg':
        Image.open(folder/'chart.png').convert('RGB').save(folder/'compressed.jpg',quality=50)
        Image.open(folder/'compressed.jpg').save(folder/'chart.png')
    truth=dict(seed=seed,renderer=renderer,style=style,control=control,values=values.tolist(),points=points,
               visible_amount_indices=show,axis_limits=[float(low),float(high)])
    (folder/'truth.json').write_text(json.dumps(truth,indent=2), encoding="utf-8");return truth


def run(output='artifacts/automatic-heldout',seed=48000,per_renderer=40):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    files=['automatic_benchmark.py','autopilot.py','layout.py','ocr.py','pipeline.py','calibrate.py','vision.py']
    locked={f:hashlib.sha256((Path(__file__).parent/f).read_bytes()).hexdigest() for f in files}
    (out/'source').mkdir(exist_ok=True)
    for f in files:(out/'source'/f).write_bytes((Path(__file__).parent/f).read_bytes())
    protocol=dict(seed=seed,per_renderer=per_renderer,locked_source_sha256=locked,
                  input='Image and explicit linear-scale assumption only. Two displayed endpoint amounts are read by OCR. No private truth or manual geometry is supplied.',
                  success='One calibrated series; correct bar count; all x coordinates within 3 pixels; NMAE below 2% on bars whose amounts are absent from image.',
                  caveat='Controlled single-card distribution; not open-world chart recognition. OCR agreement is correlated. Every generated failure retained.')
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2), encoding="utf-8")
    rows=[]
    for ri,renderer in enumerate(['pillow','matplotlib']):
        for j in range(per_renderer):
            s=seed+ri*1000+j;folder=out/f'{renderer}-{s}'
            generate_card(folder,s,renderer,STYLES[j%len(STYLES)])
            r=analyze(folder/'chart.png',{'auto_layout':True,'scale':'linear'},folder/'analysis')
            # Scoring truth is opened only after the complete recovery finishes.
            truth=json.loads((folder/'truth.json').read_text(encoding="utf-8"));v=np.array(truth['values']);n=len(v)
            row=dict(seed=s,renderer=renderer,style=truth['style'],status=r['status'],success=False,
                     expected_bars=n,detected_bars=sum(len(s['points']) for s in r['geometry']['series']),
                     anchors=len(r['visual_evidence']['binding']['anchors']))
            if r['status']=='calibrated' and len(r['recovery'])==1 and len(r['recovery'][0]['values'])==n:
                pred=np.array(r['recovery'][0]['values']);keep=[i for i in range(n) if i not in truth['visible_amount_indices']]
                errors=np.abs(pred-v);nmae=float(errors[keep].mean()/np.ptp(v))
                dx=float(max(abs(a['x']-b['x']) for a,b in zip(r['geometry']['series'][0]['points'],truth['points'])))
                cal=r['recovery'][0]
                coverage=float(np.mean((np.array(cal['lower'])[keep]<=v[keep])&(v[keep]<=np.array(cal['upper'])[keep])))
                row.update(nmae=nmae,mae=float(errors[keep].mean()),max_x_error=dx,withheld_points=len(keep),conditional_interval_coverage=coverage,
                           success=nmae<.02 and dx<=3)
            rows.append(row)
    controls=[]
    for j,control in enumerate(['no_amounts','mixed_currency','conflict','no_periods']):
        folder=out/f'control-{control}';generate_card(folder,seed+3000+j,control=control)
        r=analyze(folder/'chart.png',{'auto_layout':True,'scale':'linear'},folder/'analysis')
        controls.append(dict(case=control,status=r['status'],recovery_statuses=[x['status'] for x in r['recovery']],
                             abstained=all(x.get('values') is None for x in r['recovery'])))
    summary=dict(protocol=protocol,cases=len(rows),passed=sum(r['success'] for r in rows),
                 by_renderer={name:dict(passed=sum(r['success'] for r in rows if r['renderer']==name),total=sum(r['renderer']==name for r in rows)) for name in ['pillow','matplotlib']},
                 failures=[r for r in rows if not r['success']],controls=controls,rows=rows)
    (out/'summary.json').write_text(json.dumps(summary,indent=2), encoding="utf-8");return summary


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',default='artifacts/automatic-heldout');p.add_argument('--seed',type=int,default=48000);p.add_argument('--per-renderer',type=int,default=40)
    a=p.parse_args();r=run(a.out,a.seed,a.per_renderer);print(json.dumps({k:v for k,v in r.items() if k not in ('rows','failures')},indent=2))
