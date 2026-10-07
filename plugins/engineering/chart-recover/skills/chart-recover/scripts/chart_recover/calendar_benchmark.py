"""Full-image curve/calendar evaluation with undisclosed daily amounts.

The chart and calendar explicitly name daily revenue and the same month.
Endpoint dates establish the plotted period. Recovery gets no scale, numeric
anchors, correspondence assumptions, kind, color, ROI or private truth.
"""
from pathlib import Path
import calendar
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
from .calendar_recovery import analyze_calendar


def generate_dashboard(folder,seed,renderer='pillow',style='light',control=None):
    out=Path(folder);out.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(seed)
    year=int(rng.choice([2024,2026,2027]));month=int(rng.integers(1,13));days=calendar.monthrange(year,month)[1]
    first_weekday=0 if seed%2 else 6;offset=(calendar.monthrange(year,month)[0]-first_weekday)%7
    weeks=(offset+days+6)//7;width=int(rng.integers(840,1120));height=1120
    values=np.round(rng.uniform(150,1450,days),0)
    # Keep endpoint calendar cells visible to make every occupied week readable;
    # six randomly selected interior values are absent from the image.
    hidden=sorted(int(x) for x in rng.choice(np.arange(1,days-1),size=6,replace=False))
    for week in range(weeks):
        indices=[i for i in range(days) if (i+offset)//7==week]
        if indices and all(i in hidden for i in indices):hidden.remove(indices[0])
    bg='#181a26' if style=='dark' else '#ffffff';fg='#e1e5ef' if style=='dark' else '#394150'
    panel='#282c3b' if style=='dark' else '#eff1f5';color='#7267ec'
    left=width*.08;right=width*.92;top=100.;bottom=390.
    lo=float(min(values)-(max(values)-min(values))*.12);hi=float(max(values)+(max(values)-min(values))*.12)
    xs=np.linspace(left,right,days);ys=bottom-(values-lo)/(hi-lo)*(bottom-top)
    kind='line' if seed%2 else 'area'
    if renderer=='matplotlib':
        fig=plt.figure(figsize=(width/100,height/100),dpi=100,facecolor=bg)
        ax=fig.add_axes([left/width,1-bottom/height,(right-left)/width,(bottom-top)/height],facecolor=bg)
        ax.set_xlim(0,days-1);ax.set_ylim(lo,hi);ax.axis('off')
        if kind=='line':ax.plot(np.arange(days),values,color=color,lw=2.2)
        else:ax.fill_between(np.arange(days),values,lo,color=color)
        fig.savefig(out/'curve.png',facecolor=bg,dpi=100);plt.close(fig)
        im=Image.open(out/'curve.png').convert('RGB')
    else:
        im=Image.new('RGB',(width,height),bg);draw=ImageDraw.Draw(im)
        pts=list(zip(xs,ys))
        if kind=='line':draw.line(pts,fill=color,width=3)
        else:draw.polygon([(left,bottom)]+pts+[(right,bottom)],fill=color)
    draw=ImageDraw.Draw(im)
    alternate=Path(font_manager.findfont('DejaVu Sans Mono'))
    fontpath=font_manager.findfont('DejaVu Sans') if seed%2 or not alternate.exists() else str(alternate)
    font=lambda n:ImageFont.truetype(fontpath,n)
    heading=font(20);body=font(14 if style=='small' else 16);tiny=font(11)
    monthname=calendar.month_name[month];abbr=calendar.month_abbr[month]
    draw.text((left,45),'Daily revenue' if control!='missing_metric' else 'Revenue',font=heading,fill=fg)
    draw.text((left+240,45),f'{monthname} {year}',font=heading,fill=fg)
    draw.text((left,bottom+24),f'{abbr} {5 if control=="partial_period" else 1}',font=body,fill=fg,anchor='mt')
    draw.text((right,bottom+24),f'{abbr} {days}',font=body,fill=fg,anchor='mt')
    step=width*.095;rowstep=step*.8;calleft=(width-step*7)/2;title_y=520;weekday_y=568
    draw.text((calleft,title_y),'Daily MRR' if control=='wrong_metric' else 'Daily revenue' if control!='missing_metric' else 'Amounts',font=heading,fill=fg)
    calmonth=month%12+1 if control=='wrong_month' else month
    draw.text((calleft+240,title_y),f'{calendar.month_name[calmonth]} {year}',font=heading,fill=fg)
    letters=['M','T','W','T','F','S','S'] if first_weekday==0 else ['S','M','T','W','T','F','S']
    for j,letter in enumerate(letters):draw.text((calleft+(j+.5)*step,weekday_y),letter,font=body,fill=fg,anchor='mm')
    truth_cells=[]
    for i,value in enumerate(values):
        row,col=divmod(i+offset,7);cx=calleft+(col+.5)*step;cy=weekday_y+30+row*rowstep
        highlight=i==days-1 and style=='highlight';cellbg=color if highlight else panel;cellfg='#ffffff' if highlight else fg
        draw.rounded_rectangle([cx-step/2+3,cy,cx+step/2-3,cy+rowstep-5],radius=7,fill=cellbg)
        if i not in hidden and control!='no_amounts':
            amount=value*3 if control=='conflict' and i==0 else value
            draw.text((cx,cy+12),f'${amount:,.0f}',font=body,fill=cellfg,anchor='mt')
        draw.text((cx,cy+39),str(int(rng.integers(5,80))),font=tiny,fill=cellfg,anchor='mt')
        truth_cells.append(dict(date=f'{year:04d}-{month:02d}-{i+1:02d}',value=float(value),amount_visible=i not in hidden and control!='no_amounts'))
    path=out/'chart.png';im.save(path)
    if style=='jpeg':
        im.save(out/'compressed.jpg',quality=55);Image.open(out/'compressed.jpg').save(path)
    truth=dict(seed=seed,renderer=renderer,calendar_renderer='Pillow',font=fontpath,style=style,control=control,year=year,month=month,
               days=days,kind=kind,hidden_indices=hidden,values=values.tolist(),points=[dict(x=float(x),y=float(y)) for x,y in zip(xs,ys)],cells=truth_cells)
    (out/'truth.json').write_text(json.dumps(truth,indent=2), encoding="utf-8");return truth


def run(output='artifacts/calendar-heldout',seed=60000,per_renderer=20):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    source=Path(__file__).parent;files=['calendar_benchmark.py','calendar_vision.py','calendar_recovery.py','ocr.py','autopilot.py','vision.py','calibrate.py']
    hashes={f:hashlib.sha256((source/f).read_bytes()).hexdigest() for f in files};(out/'source').mkdir(exist_ok=True)
    for f in files:(out/'source'/f).write_bytes((source/f).read_bytes())
    protocol=dict(seed=seed,per_renderer=per_renderer,source_hashes=hashes,input='Image only; no axis scale, kind, ROI, color, numerical anchors or correspondence assumptions.',
                  visible_evidence='Matching daily-revenue headings and calendar month/year; first and last curve date labels; calendar money cells except withheld days.',
                  scoring='Private truth opened after recovery. Require correct month, all daily points, x alignment within 4px, no falsely read monetary value, and NMAE below 2% on undisclosed amounts.',
                  limitations='Procedural dashboards; two curve renderers but one calendar renderer, two fonts. No open-world public accuracy claim.')
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2), encoding="utf-8");rows=[]
    styles=['light','dark','highlight','jpeg','small']
    for ri,renderer in enumerate(['pillow','matplotlib']):
        for j in range(per_renderer):
            s=seed+1000*ri+j;folder=out/f'{renderer}-{s}';generate_dashboard(folder,s,renderer,styles[j%len(styles)])
            r=analyze_calendar(folder/'chart.png',{},folder/'analysis');t=json.loads((folder/'truth.json').read_text(encoding="utf-8"))
            row=dict(seed=s,renderer=renderer,style=t['style'],kind=t['kind'],status=r['status'],success=False,observations=len(r['calendar']['observations']))
            wrong=[o for o in r['calendar']['observations'] if o['date'][:7]!=f"{t['year']:04d}-{t['month']:02d}" or o['value']!=t['values'][int(o['date'][-2:])-1]]
            row['wrong_ocr_values']=len(wrong)
            if r['status']=='calibrated' and len(r['geometry']['series'])==1 and len(r['recovery'][0]['values'])==t['days']:
                cal=r['recovery'][0];pred=np.array(cal['values']);truth=np.array(t['values']);keep=t['hidden_indices'];err=np.abs(pred-truth)
                dx=max(abs(p['x']-q['x']) for p,q in zip(r['geometry']['series'][0]['points'],t['points']))
                nmae=float(err[keep].mean()/np.ptp(truth));coverage=float(np.mean((np.array(cal['lower'])[keep]<=truth[keep])&(truth[keep]<=np.array(cal['upper'])[keep])))
                row.update(nmae=nmae,mae=float(err[keep].mean()),max_x_error=float(dx),withheld_values=len(keep),conditional_interval_coverage=coverage,
                           inferred_scale=cal.get('scale'),success=not wrong and dx<=4 and nmae<.02)
            rows.append(row)
            (out/'cases.json').write_text(json.dumps(rows,indent=2), encoding="utf-8")
    controls=[]
    for j,control in enumerate(['wrong_metric','wrong_month','partial_period','missing_metric','conflict','no_amounts']):
        folder=out/f'control-{control}';generate_dashboard(folder,seed+3000+j,control=control)
        r=analyze_calendar(folder/'chart.png',{},folder/'analysis')
        controls.append(dict(case=control,status=r['status'],outcomes=[c['status'] for c in r['recovery']],abstained=all(c.get('values') is None for c in r['recovery']),reasons=r['correspondence']['reasons']))
    summary=dict(protocol=protocol,cases=len(rows),passed=sum(r['success'] for r in rows),
                 by_renderer={name:dict(passed=sum(r['success'] for r in rows if r['renderer']==name),total=sum(r['renderer']==name for r in rows)) for name in ['pillow','matplotlib']},
                 failures=[r for r in rows if not r['success']],controls=controls,rows=rows)
    (out/'summary.json').write_text(json.dumps(summary,indent=2), encoding="utf-8");return summary


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',default='artifacts/calendar-heldout');p.add_argument('--seed',type=int,default=60000);p.add_argument('--per-renderer',type=int,default=20)
    a=p.parse_args();r=run(a.out,a.seed,a.per_renderer);print(json.dumps({k:v for k,v in r.items() if k not in ('rows','failures')},indent=2))
