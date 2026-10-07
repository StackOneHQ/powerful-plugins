"""No GT tables, coordinates or plot boxes enter extract().

Known chart family and scale are explicit inputs. Endpoint facts supply two
absolute values, with their point correspondence given. Reported accuracy is
conditional on those inputs, not autonomous real-world recovery accuracy.
"""
from pathlib import Path
import json
import time
import sys
import numpy as np
from scipy.optimize import linear_sum_assignment
from .synthetic import generate_one, collision_demo, KINDS
from .vision import extract, overlay
from .calibrate import calibrate


def _rgb(c):return np.array([int(c[i:i+2],16) for i in (1,3,5)])


def evaluate_case(folder, truth, pred=None):
    pred=pred if pred is not None else extract(folder/'chart.png',kind=truth['kind'])
    expected=truth['series'];found=pred['series'];records=[]
    if not found:return dict(status='failed',reason='No series',series_count_ok=False,series=[])
    cost=np.array([[np.linalg.norm(_rgb(a['color'])-_rgb(b['color'])) for b in found] for a in expected])
    ti,pi=linear_sum_assignment(cost)
    horizontal=truth['kind']=='barh';continuous=truth['kind'] in ('line','area','stacked_area')
    for i,j in zip(ti,pi):
        ts,ps=expected[i],found[j]
        tp,pp=ts['points'],ps['points'];key='y' if horizontal else 'x'
        tp=sorted(tp,key=lambda p:p[key])
        true_x=np.array([p[key] for p in tp]);true_v=np.array([p['value'] for p in tp])
        px=np.array([p[key] for p in pp]);coord=np.array(ps['coordinates'])
        if continuous:
            true_c=np.array([p['y'] for p in tp])
            target_c=np.interp(px,true_x,true_c)
            if truth['scale']=='log':target_v=10**np.interp(px,true_x,np.log10(true_v))
            else:target_v=np.interp(px,true_x,true_v)
            count_ok=px.min() <= true_x.min()+3 and px.max() >= true_x.max()-3 and len(pp)>=96
        else:
            count_ok=len(pp)==len(tp)
            if not count_ok:
                records.append(dict(status='failed',reason='Wrong mark count',expected=len(tp),found=len(pp)));continue
            target_c=np.array([-p['x'] if horizontal else p['y'] for p in tp]);target_v=true_v
            count_ok=bool(np.max(abs(px-true_x)) < 5)
        # Values only at first/last marks are exposed as external evidence.
        anchors=[dict(pixel=float(coord[k]),value=float(true_v[vk]),source='synthetic endpoint disclosure',matched=True)
                 for k,vk in [(0,0),(-1,-1)]]
        cal=calibrate(coord,anchors,scale=truth['scale'],pixel_error=2.5)
        no=calibrate(coord,scale='unknown')
        record=dict(status=cal['status'],count_ok=bool(count_ok),pixel_mae=float(np.abs(coord-target_c).mean()),
                    abstained_without_evidence=no['status']=='unidentifiable',points=len(pp))
        if cal['status']=='calibrated':
            est=np.array(cal['values']);lo=np.array(cal['lower']);hi=np.array(cal['upper'])
            record.update(nmae=float(np.abs(est[1:-1]-target_v[1:-1]).mean()/np.ptp(true_v)),
                          interval_coverage=float(((target_v[1:-1] >= lo[1:-1])&(target_v[1:-1] <= hi[1:-1])).mean()))
            record['passed']=bool(count_ok and record['nmae'] < .02)
        else:record['passed']=False
        records.append(record)
    ok=len(found)==len(expected) and len(records)==len(expected) and all(r.get('passed',False) for r in records)
    return dict(status='passed' if ok else 'failed',series_count_ok=len(found)==len(expected),series=records)


def run_benchmark(output, per_kind=12, seed=9000, render_holdout=True):
    out=Path(output)
    if out.exists() and any(out.iterdir()):raise ValueError('Use a fresh empty output directory for an evaluation')
    out.mkdir(parents=True,exist_ok=True);start=time.time();rows=[]
    variants=('clean','dark','jpeg','small','truncated')
    cases=[]
    for k in KINDS:
        for i in range(per_kind):
            variant=variants[i%len(variants)]
            if k.startswith('stacked') and variant=='truncated':variant='clean'
            cases.append((k,'linear',variant,'matplotlib'))
    for k in ('line','scatter'):
        for i in range(per_kind//2):cases.append((k,'log',variants[i%4],'matplotlib'))
    if render_holdout:
        for k in ('bar','line','area','scatter'):
            for i in range(max(3,per_kind//2)):cases.append((k,'linear',variants[i%4],'pillow'))
    for i,(kind,scale,variant,renderer) in enumerate(cases):
        case_id=f'{i:04d}_{kind}_{scale}_{variant}_{renderer}';folder=out/'cases'/case_id
        truth=generate_one(folder,seed+i,kind,scale,variant,renderer)
        pred=extract(folder/'chart.png',kind=kind)
        result=evaluate_case(folder,truth,pred)
        row=dict(id=case_id,seed=seed+i,kind=kind,scale=scale,variant=variant,renderer=renderer,**result);rows.append(row)
        if i<8 or result['status']=='failed':overlay(folder/'chart.png',pred,folder/'overlay.png')
        (out/'cases.json').write_text(json.dumps(rows,indent=2), encoding="utf-8")
        if (i+1)%20==0:print(f'Benchmarked {i+1}/{len(cases)} charts',file=sys.stderr,flush=True)
    groups={}
    for k in sorted(set(r['kind'] for r in rows)):
        group=[r for r in rows if r['kind']==k];s=[s for r in group for s in r['series'] if 'nmae' in s]
        groups[k]=dict(charts=len(group),passed=sum(r['status']=='passed' for r in group),
                       median_nmae=float(np.median([r['nmae'] for r in s])) if s else None,
                       p95_nmae=float(np.quantile([r['nmae'] for r in s],.95)) if s else None)
    s=[s for r in rows for s in r['series'] if 'nmae' in s]
    summary=dict(charts=len(rows),passed=sum(r['status']=='passed' for r in rows),groups=groups,
                 seed=seed,seconds=round(time.time()-start,2),
                 mean_interval_coverage=float(np.mean([r['interval_coverage'] for r in s])) if s else None,
                 all_evaluated_unanchored_series_abstained=bool(s) and all(r['abstained_without_evidence'] for r in s),
                 renderer_holdout=dict(charts=sum(r['renderer']=='pillow' for r in rows),passed=sum(r['renderer']=='pillow' and r['status']=='passed' for r in rows)),
                 collision_proof=collision_demo(out/'collision'),
                 protocol='Known family and scale; image-only geometry; first and last point values/correspondence disclosed. Pass = all series counted/aligned, continuous traces cover at least 96/101 samples, and each series interior-point mean absolute value error <2% of its true range. Failures retained. No claim of open-world accuracy.')
    (out/'summary.json').write_text(json.dumps(summary,indent=2), encoding="utf-8");return summary
