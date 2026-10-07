"""Frozen external-table reconstruction with six unavailable source amounts."""
from datetime import date,timedelta
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
from .public_profile import parse_profile
from .external_evidence import recover_external


URL='https://trustmrr.com/startup/synthetic-lumen-example.md'


def generate(folder,seed,renderer='pillow',style='light',control=None,*,color='#7165e8',jpeg_quality=55,image_scale=1.,entity='Lumen',slug='synthetic-lumen-example',values=None,axis_scale=None,curve='linear',step_where='post'):
    if curve not in ('linear','pchip','cubic','step'):raise ValueError('Unsupported curve interpolation')
    if step_where not in ('pre','post','mid'):raise ValueError('Unsupported step convention')
    out=Path(folder);out.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(seed)
    width,height=1000,600;left,right,top,bottom=90.,920.,155.,455.
    scale=axis_scale or ('log' if seed%3==1 else 'linear')
    if scale not in ('linear','log'):raise ValueError('Expected linear or log axis scale')
    values=np.round(np.exp(rng.uniform(4.7,7.5,30)) if scale=='log' else rng.uniform(250,1800,30),2) if values is None else np.asarray(values,float)
    if values.shape!=(30,) or not np.isfinite(values).all() or np.ptp(values)<=0 or (scale=='log' and values.min()<=0):
        raise ValueError('Expected thirty finite, varying values, positive for log scale')
    transformed=np.log10(values) if scale=='log' else values
    plot_days=np.arange(30);plot_values=transformed
    if curve in ('pchip','cubic'):
        from scipy.interpolate import PchipInterpolator,CubicSpline
        plot_days=np.linspace(0,29,1741)
        interpolator=PchipInterpolator(np.arange(30),transformed) if curve=='pchip' else CubicSpline(np.arange(30),transformed,bc_type='natural')
        plot_values=interpolator(plot_days)
    elif curve=='step':
        if step_where=='post':
            plot_days=np.repeat(np.arange(30),2)[1:]
            plot_values=np.repeat(transformed,2)[:-1]
        elif step_where=='pre':
            plot_days=np.repeat(np.arange(30),2)[:-1]
            plot_values=np.repeat(transformed,2)[1:]
        else:
            plot_days=np.r_[0.,np.repeat(np.arange(29)+.5,2),29.]
            plot_values=np.repeat(transformed,2)
    lo,hi=float(plot_values.min()),float(plot_values.max());gap=(hi-lo)*.04;lo-=gap;hi+=gap
    xs=np.linspace(left,right,30);ys=bottom-(transformed-lo)/(hi-lo)*(bottom-top)
    plot_xs=xs if curve=='linear' else left+(right-left)*plot_days/29
    plot_ys=ys if curve=='linear' else bottom-(plot_values-lo)/(hi-lo)*(bottom-top)
    hidden=[3,8,13,19,23,27]
    bg='#171b29' if style=='dark' else '#ffffff';fg='#e1e5ef' if style=='dark' else '#303744'
    if renderer=='matplotlib':
        fig=plt.figure(figsize=(width/100,height/100),dpi=100,facecolor=bg)
        ax=fig.add_axes([left/width,1-bottom/height,(right-left)/width,(bottom-top)/height],facecolor=bg)
        ax.set_xlim(0,29);ax.set_ylim(lo,hi);ax.axis('off')
        if style=='filled':ax.fill_between(plot_days,plot_values,lo,color=color,alpha=.35)
        ax.plot(plot_days,plot_values,color=color,lw=1.6)
        fig.savefig(out/'render.png',dpi=100,facecolor=bg);plt.close(fig)
        im=Image.open(out/'render.png').convert('RGB')
    else:
        im=Image.new('RGB',(width,height),bg);draw=ImageDraw.Draw(im)
        if style=='filled':draw.polygon([(left,bottom),*zip(plot_xs,plot_ys),(right,bottom)],fill='#b5adef')
        draw.line(list(zip(plot_xs,plot_ys)),fill=color,width=3)
    draw=ImageDraw.Draw(im);font=lambda n:ImageFont.truetype(font_manager.findfont('DejaVu Sans'),n)
    draw.text((60,25),'OtherCo' if control=='wrong_entity' else entity,font=font(28),fill=fg)
    draw.text((left,85),'MRR' if control=='wrong_metric' else 'Revenue',font=font(20),fill=fg)
    for i in [0,5,10,15,20,25,29]:
        day=30-i if control=='reversed_dates' else i+1
        draw.text((xs[i],490),f'Sep {day}',font=font(12 if style=='small' else 16),fill=fg,anchor='mt')
    if control=='wrong_year':draw.text((470,520),'2025',font=font(16),fill=fg)
    if control=='ambiguous_year':draw.text((470,490),'2025',font=font(16),fill=fg)
    if control=='two_curves':draw.line(list(zip(xs,ys[::-1])),fill='#18aa78',width=3)
    if control=='same_hue_two_curves':draw.line(list(zip(xs,ys[::-1])),fill=color,width=3)
    if control=='missing_middle':draw.rectangle([455,140,545,470],fill=bg)
    if control=='chart_absent':draw.rectangle([left-15,top-15,right+15,bottom+15],fill=bg)
    im.save(out/'chart.png')
    if style=='jpeg':
        im.save(out/'compressed.jpg',quality=jpeg_quality);Image.open(out/'compressed.jpg').save(out/'chart.png')
    if image_scale!=1.:
        if image_scale<=0:raise ValueError('image_scale must be positive')
        resized=Image.open(out/'chart.png').resize((round(width*image_scale),round(height*image_scale)),Image.Resampling.LANCZOS)
        resized.save(out/'chart.png');xs=xs*resized.width/width;ys=ys*resized.height/height
    docs=['# '+entity,'- Name: '+entity,f'- Slug: `{slug}`','- Revenue last synced: 2026-10-01T12:00:00Z',
          '- Verified payment provider API source: Synthetic evaluation fixture',
          '### Daily revenue — last 30 days','| Date | Verified revenue |','| --- | ---: |']
    source_values=np.round(rng.uniform(300,2000,30),2) if control=='unrelated_values' else values
    for i,v in enumerate(source_values):
        amount='REDACTED' if i in hidden or control=='no_amounts' else f'${v:,.2f}'
        docs.append(f'| 2026-09-{i+1:02d} | {amount} |')
    docs+=['## Metric Snapshots','- Current MRR: $9,000,000']
    (out/'profile.md').write_text('\n'.join(docs)+'\n', encoding="utf-8")
    truth=dict(seed=seed,renderer=renderer,style=style,scale=scale,curve=curve,values=values.tolist(),hidden_indices=hidden,
               points=[dict(x=float(x),y=float(y)) for x,y in zip(xs,ys)],control=control)
    if curve=='step':truth['step_where']=step_where
    (out/'truth.json').write_text(json.dumps(truth,indent=2), encoding="utf-8");return truth


def score(result,truth):
    row=dict(seed=truth['seed'],renderer=truth['renderer'],style=truth['style'],status=result['status'],
             success=False,reasons=result['reasons'],checking=result.get('checking'))
    if result['status']!='conditional_calibration':return row
    cal=result['recovery'][0];points=result['geometry']['series'][0]['points']
    xs=np.array([p['x'] for p in points]);pred=np.array(cal['values']);ys=np.array([p['y'] for p in points])
    keep=truth['hidden_indices'];tx=np.array([truth['points'][i]['x'] for i in keep]);target=np.array(truth['values'])[keep]
    expected_dates={f'2026-09-{i+1:02d}' for i in keep}
    leaked=[r for r in result['observations'] if r['eligible'] and r['period'] in expected_dates]
    # Score at the reader's proposed date locations, not private true x values.
    axis=result['date_axis'];base=date.fromisoformat(axis['origin']).toordinal()
    proposed_x=np.array([axis['origin_x']+axis['pixels_per_day']*(date(2026,9,i+1).toordinal()-base) for i in keep])
    if axis.get('sampling'):
        # Score the explicit daily estimates exported by a step-aware reader.
        # The raw trace contains vertical-stroke middles, not daily values.
        daily={r['proposed_date']:r for r in result.get('daily_recovery',[])}
        missing=sorted(expected_dates-set(daily))
        if missing:
            row.update(hidden_predictions_missing=missing,hidden_values_leaked=len(leaked));return row
        selected=[daily[f'2026-09-{i+1:02d}'] for i in keep]
        recovered=np.array([r['conditional_value'] for r in selected])
        lower=np.array([r['lower'] for r in selected]);upper=np.array([r['upper'] for r in selected])
        consistent=all(abs(r['pixel_x']-x)<1e-6 and xs.min()<=r['sample_window'][0]<=r['sample_window'][1]<=xs.max()
                       for r,x in zip(selected,proposed_x))
        row['prediction_basis']='returned_daily_plateau_estimates'
    else:
        recovered=np.interp(proposed_x,xs,pred)
        lower=np.interp(proposed_x,xs,cal['lower']);upper=np.interp(proposed_x,xs,cal['upper'])
        consistent=True;row['prediction_basis']='raw_curve_at_proposed_date'
    error=np.abs(recovered-target)
    dx=float(np.max(np.abs(proposed_x-tx)));nmae=float(error.mean()/np.ptp(truth['values']))
    coverage=float(np.mean((target>=lower)&(target<=upper)))
    row.update(hidden_values=len(keep),mae=float(error.mean()),nmae=nmae,max_x_error=dx,hidden_values_leaked=len(leaked),
               inferred_scale=cal['scale'],true_scale=truth['scale'],conditional_interval_coverage=coverage,
               success=bool(consistent and not leaked and dx<=4 and cal['scale']==truth['scale'] and nmae<.02
                       and proposed_x.min()>=xs.min() and proposed_x.max()<=xs.max()))
    return row


def run(output,seed=90000,per_renderer=10):
    out=Path(output)
    if (out/'protocol.json').exists():raise ValueError('Use a fresh path; frozen evaluations are never overwritten')
    out.mkdir(parents=True,exist_ok=True);src=Path(__file__).parent
    files=['external_benchmark.py','external_evidence.py','public_profile.py','vision.py','ocr.py','autopilot.py','calibrate.py','calendar_vision.py']
    (out/'source').mkdir(exist_ok=True)
    for name in files:(out/'source'/name).write_bytes((src/name).read_bytes())
    protocol=dict(seed=seed,per_renderer=per_renderer,source_hashes={f:hashlib.sha256((src/f).read_bytes()).hexdigest() for f in files},
                  input='Image and a linked public-profile-format table with six redacted amounts. No ROI, color, numerical anchor, axis scale or date coordinates.',
                  acceptance='Prefer a geometry-only daily grid supported by straight-segment joins and withheld central pixels; otherwise choose among at most 65 text-constrained alignments using fitting dates only. Strategy is fixed before checking values. At least 8 fitting / 5 checking dates, fixed date-ordinal split, at least two checking levels distinguishable in value and pixel intervals, unique scale, checking NMAE <2%, checking coverage >=90%; association remains conditional.',
                  scoring='After inference, open private truth. Six missing table values; require correct scale, no hidden-value leakage, proposed X alignment <=4px, no extrapolation, hidden-value NMAE <2% of value range.',
                  limitations='Procedural images and source text; two curve renderers, one text renderer. This does not establish public source truth or independent identity.')
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2), encoding="utf-8");rows=[]
    for ri,renderer in enumerate(('pillow','matplotlib')):
        for j in range(per_renderer):
            folder=out/f'{renderer}-{seed+ri*1000+j}';generate(folder,seed+ri*1000+j,renderer,['light','dark','filled','jpeg','small'][j%5])
            profile=parse_profile((folder/'profile.md').read_text(encoding="utf-8"),URL)
            result=recover_external(folder/'chart.png',profile,folder/'analysis')
            truth=json.loads((folder/'truth.json').read_text(encoding="utf-8"));row=score(result,truth);rows.append(row)
            (out/'cases.json').write_text(json.dumps(rows,indent=2), encoding="utf-8");print(renderer,row['seed'],row['status'],row['success'],flush=True)
    controls=[]
    for j,control in enumerate(('wrong_entity','wrong_metric','wrong_year','ambiguous_year','reversed_dates','unrelated_values','no_amounts','two_curves')):
        folder=out/f'control-{control}';generate(folder,seed+3000+j,control=control)
        result=recover_external(folder/'chart.png',parse_profile((folder/'profile.md').read_text(encoding="utf-8"),URL),folder/'analysis')
        controls.append(dict(case=control,status=result['status'],abstained=result['status']!='conditional_calibration',reasons=result['reasons']))
    summary=dict(protocol=protocol,cases=len(rows),passed=sum(r['success'] for r in rows),
                 abstentions=sum(r['status']!='conditional_calibration' for r in rows),
                 incorrect_returned_candidates_under_criteria=sum(r['status']=='conditional_calibration' and not r['success'] for r in rows),
                 rows=rows,controls=controls)
    (out/'summary.json').write_text(json.dumps(summary,indent=2), encoding="utf-8");return summary


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',default='artifacts/external-heldout-v1');p.add_argument('--seed',type=int,default=90000);p.add_argument('--per-renderer',type=int,default=10)
    args=p.parse_args();r=run(args.out,args.seed,args.per_renderer);print(json.dumps({k:v for k,v in r.items() if k not in ('rows','protocol')},indent=2))
