"""Image-only axis reading, with two of five numerical tick labels absent.

Private truth is scored only after recovery. This is partial-axis reading,
not recovery of an entirely absent axis without external numerical evidence.
"""
from pathlib import Path
import hashlib
import json
import os
import platform
import subprocess
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from .render_cache import configure_cache
configure_cache()
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt,font_manager
from .tick_recovery import analyze_ticks

STYLES=['light','dark','left','jpeg','small','truncated','log','negative','abbreviated','wide']


def generate(folder,seed,renderer='pillow',style='light',control=None):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(seed)
    width=int(rng.integers(680,1060));height=int(rng.integers(410,650))
    if style=='wide':width=1200;height=430
    side='left' if style=='left' else 'right';scale='log' if style=='log' else 'linear'
    ticks=np.geomspace(10,100000,5) if scale=='log' else np.linspace(-1000 if style=='negative' else 1000 if style=='truncated' else 0,3000 if style=='negative' else 5000 if style in ('truncated','abbreviated') else 400,5)
    values=rng.uniform(ticks[0]+.08*np.ptp(ticks),ticks[-1]-.08*np.ptp(ticks),9)
    if scale=='log':values=10**rng.uniform(1.3,4.7,9)
    transform=np.log10 if scale=='log' else lambda x:np.asarray(x)
    l=width*.14 if side=='left' else width*.07;r=width*.91 if side=='left' else width*.84;t=80;b=height-65
    xs=np.linspace(l,r,9);q=transform(values);lo,hi=transform(ticks[[0,-1]])
    ys=b-(q-lo)/(hi-lo)*(b-t);tick_y=b-(transform(ticks)-lo)/(hi-lo)*(b-t)
    bg='#192131' if style=='dark' else '#ffffff';fg='#e8ecf1' if style=='dark' else '#566475'
    grid='#465469' if style=='dark' else '#d3d8df';color='#8b75ea'
    hidden=[1,3];visible=[i for i in range(5) if i not in hidden and control!='no_labels']
    labels=[]
    for i,v in enumerate(ticks):
        value=v*1.6 if control=='conflict' and i==2 else v
        unit='€' if control=='mixed_currency' and i==2 else '$'
        label=f'{unit}{value/1000:g}K' if style=='abbreviated' and value else f'{unit}{value:g}'
        labels.append(label if i in visible else '')
    fontpath=font_manager.findfont('DejaVu Sans');font_size=11 if style=='small' else 17
    if renderer=='pillow':
        im=Image.new('RGB',(width,height),bg);draw=ImageDraw.Draw(im)
        font=ImageFont.truetype(fontpath,font_size)
        draw.text((l,25),'Daily revenue',font=ImageFont.truetype(fontpath,23),fill=fg)
        for i,y in enumerate(tick_y):
            draw.line((l,round(y),r,round(y)),fill=grid,width=1)
            if labels[i]:draw.text((l-14 if side=='left' else r+14,round(y)),labels[i],font=font,fill=fg,anchor='rm' if side=='left' else 'lm')
        draw.line(list(zip(xs,ys)),fill=color,width=3)
        if control=='two_curves':draw.line(list(zip(xs,ys*.7+t*.3)),fill='#12a678',width=3)
        if control=='dual_axis':
            for i,y in enumerate(tick_y):draw.text((l-14,y),f'€{i*10}',font=font,fill=fg,anchor='rm')
        im.save(folder/'chart.png')
    else:
        fig=plt.figure(figsize=(width/100,height/100),dpi=100,facecolor=bg)
        ax=fig.add_axes([l/width,1-b/height,(r-l)/width,(b-t)/height],facecolor=bg)
        ax.set_xlim(0,8);ax.set_yscale(scale);ax.set_ylim(float(ticks[0]),float(ticks[-1]))
        ax.set_xticks([]);ax.set_yticks(ticks,labels);ax.minorticks_off()
        ax.tick_params(axis='y',length=0,labelsize=font_size*.75,pad=10,colors=fg)
        if side=='right':ax.yaxis.tick_right()
        for sp in ax.spines.values():sp.set_visible(False)
        ax.grid(axis='y',color=grid,linewidth=.8);ax.set_axisbelow(True)
        ax.plot(np.arange(9),values,color=color,lw=2)
        ax.set_title('Daily revenue',loc='left',fontsize=16,color=fg,pad=25)
        fig.canvas.draw();xy=ax.transData.transform(np.c_[np.arange(9),values]);xs=xy[:,0];ys=height-xy[:,1]
        fig.savefig(folder/'chart.png',facecolor=bg,dpi=100);plt.close(fig)
    if style=='jpeg':
        Image.open(folder/'chart.png').convert('RGB').save(folder/'compressed.jpg',quality=48)
        Image.open(folder/'compressed.jpg').save(folder/'chart.png')
    truth=dict(seed=seed,renderer=renderer,style=style,control=control,scale=scale,side=side,font=fontpath,
               points=[dict(x=float(x),y=float(y),value=float(v)) for x,y,v in zip(xs,ys,values)],
               ticks=[dict(value=float(v),y=float(y),visible=i in visible) for i,(v,y) in enumerate(zip(ticks,tick_y))],
               plot=[float(l),float(t),float(r),float(b)])
    (folder/'truth.json').write_text(json.dumps(truth,indent=2), encoding="utf-8")


def run(output='artifacts/tick-heldout-v1',seed=70000,per_renderer=20):
    out=Path(output)
    if (out/'protocol.json').exists():raise ValueError('Refusing to overwrite an existing frozen evaluation; choose a fresh output directory.')
    out.mkdir(parents=True,exist_ok=True);source=Path(__file__).parent
    files=['tick_recovery.py','tick_benchmark.py','autopilot.py','layout.py','ocr.py','vision.py','calibrate.py']
    (out/'source').mkdir(exist_ok=True)
    for name in files:(out/'source'/name).write_bytes((source/name).read_bytes())
    protocol=dict(seed=seed,per_renderer=per_renderer,source_hashes={f:hashlib.sha256((source/f).read_bytes()).hexdigest() for f in files},
                  input='Image only. Three of five numeric Y tick labels are visible. No scale, kind, ROI, color, anchors or date coordinates supplied.',
                  scoring='Private truth opened after recovery. At least 96 samples, 97% X coverage, correct axis scale, no wrongly read tick, rendered-curve NMAE below 2%, and two absent tick values each within 2% of full axis range.',
                  limitations='Two procedural renderers and one font family. Linear/log single continuous colored curves with neutral gridlines. Dates and original observation counts not inferred. This is partial-axis reading, not full absent-axis recovery.',
                  runtime=dict(python=platform.python_version(),numpy=np.__version__,matplotlib=matplotlib.__version__,tesseract=subprocess.run(['tesseract','--version'],capture_output=True,text=True).stdout.splitlines()[0]))
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2), encoding="utf-8");rows=[]
    for ri,renderer in enumerate(['pillow','matplotlib']):
        for j in range(per_renderer):
            s=seed+ri*1000+j;folder=out/f'{renderer}-{s}';generate(folder,s,renderer,STYLES[j%len(STYLES)])
            result=analyze_ticks(folder/'chart.png',{},folder/'analysis')
            truth=json.loads((folder/'truth.json').read_text(encoding="utf-8"))
            row=dict(seed=s,renderer=renderer,style=truth['style'],status=result['status'],success=False,reasons=result['correspondence']['reasons'])
            if result['status']=='calibrated':
                cal=result['recovery'][0];series=result['geometry']['series'][0];xs=np.array([p['x'] for p in series['points']]);nodes=truth['points']
                node_x=[p['x'] for p in nodes];node_v=np.array([p['value'] for p in nodes]);log=truth['scale']=='log'
                values=np.interp(xs,node_x,np.log10(node_v) if log else node_v)
                if log:values=10**values
                span=truth['ticks'][-1]['value']-truth['ticks'][0]['value'];error=np.abs(np.array(cal['values'])-values)
                bad_ticks=[]
                for a in cal['anchors_used']:
                    nearest=min(truth['ticks'],key=lambda k:abs(k['y']-a['pixel']))
                    if abs(nearest['y']-a['pixel'])>4 or nearest['value']!=a['value'] or not nearest['visible']:bad_ticks.append(a)
                hidden=[]
                for tick in truth['ticks']:
                    if tick['visible']:continue
                    value=cal['coefficients']['a']*(-tick['y'])+cal['coefficients']['b']
                    if cal['scale']=='log':value=10**value
                    hidden.append(dict(reference=tick['value'],estimate=float(value),absolute_error=float(abs(value-tick['value']))))
                coverage=(xs[-1]-xs[0])/(node_x[-1]-node_x[0]);nmae=float(error.mean()/span)
                row.update(samples=len(xs),wrong_ticks=len(bad_ticks),inferred_scale=cal['scale'],x_coverage=float(coverage),nmae=nmae,
                           mae=float(error.mean()),hidden_ticks=hidden,conditional_interval_coverage=float(np.mean((np.array(cal['lower'])<=values)&(values<=np.array(cal['upper'])))),
                           success=len(xs)>=96 and coverage>=.97 and cal['scale']==truth['scale'] and not bad_ticks and nmae<.02 and all(t['absolute_error']/span<.02 for t in hidden))
            rows.append(row);(out/'cases.json').write_text(json.dumps(rows,indent=2), encoding="utf-8")
            print(f'{renderer} {s}: {result["status"]}, passed={row["success"]}',flush=True)
    controls=[]
    for j,control in enumerate(['no_labels','mixed_currency','conflict','two_curves','dual_axis']):
        folder=out/f'control-{control}';generate(folder,seed+3000+j,control=control)
        result=analyze_ticks(folder/'chart.png',{},folder/'analysis')
        controls.append(dict(case=control,status=result['status'],abstained=all(r.get('values') is None for r in result['recovery']),reasons=result['correspondence']['reasons']))
    summary=dict(protocol=protocol,cases=len(rows),passed=sum(r['success'] for r in rows),abstentions=sum(r['status']!='calibrated' for r in rows),
                 incorrect_returned_calibrations_under_criteria=sum(r['status']=='calibrated' and not r['success'] for r in rows),
                 by_renderer={r:dict(passed=sum(x['success'] for x in rows if x['renderer']==r),cases=sum(x['renderer']==r for x in rows)) for r in ('pillow','matplotlib')},
                 controls=controls,rows=rows,failures=[r for r in rows if not r['success']])
    (out/'summary.json').write_text(json.dumps(summary,indent=2), encoding="utf-8");return summary


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--out',default='artifacts/tick-heldout-v1');parser.add_argument('--seed',type=int,default=70000);parser.add_argument('--per-renderer',type=int,default=20)
    args=parser.parse_args();summary=run(args.out,args.seed,args.per_renderer)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('rows','failures','protocol')},indent=2))
