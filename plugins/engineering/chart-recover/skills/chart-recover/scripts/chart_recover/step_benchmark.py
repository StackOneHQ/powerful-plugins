"""Frozen paired step-convention study; source amounts are withheld from both readers."""
from pathlib import Path
import hashlib
import importlib.util
import json
import numpy as np
from .external_benchmark import generate, score, URL
from .public_profile import parse_profile


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def totals(rows):
    return dict(cases=len(rows),passed=sum(r['success'] for r in rows),
        abstentions=sum(r['status']!='conditional_calibration' for r in rows),
        returned_failures=sum(r['status']=='conditional_calibration' and not r['success'] for r in rows))


def run(output, baseline, seed=420000):
    out=Path(output);src=Path(__file__).parent
    if out.exists():raise ValueError('Use a new output directory; frozen studies are never overwritten')
    (out/'source').mkdir(parents=True)
    files=['step_benchmark.py','external_benchmark.py','external_evidence.py','public_profile.py',
           'vision.py','ocr.py','autopilot.py','calibrate.py','calendar_vision.py']
    for f in files:(out/'source'/f).write_bytes((src/f).read_bytes())
    (out/'source'/'baseline_external_evidence.py').write_bytes(Path(baseline).read_bytes())
    readers={}
    for name,filename in [('baseline','baseline_external_evidence.py'),('revised','external_evidence.py')]:
        spec=importlib.util.spec_from_file_location('chart_recover._step_study_'+name,out/'source'/filename)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);readers[name]=module
    plans=[]
    for ri,renderer in enumerate(('pillow','matplotlib')):
        for ci,where in enumerate(('pre','post','mid')):
            for pi,pattern in enumerate(('random','holds')):
                for si,style in enumerate(('light','dark','filled','jpeg','small')):
                    plans.append(dict(seed=seed+ri*10000+ci*1000+pi*100+si,renderer=renderer,
                        style=style,curve='step',step_where=where,pattern=pattern,control=None))
        for ci,curve in enumerate(('linear','pchip','cubic')):
            for si,style in enumerate(('light','dark','filled','jpeg','small')):
                plans.append(dict(seed=seed+ri*10000+5000+ci*100+si,renderer=renderer,
                    style=style,curve=curve,step_where='post',pattern='random',control=None))
    for ci,where in enumerate(('pre','post','mid')):
        for si,control in enumerate(('wrong_year','wrong_metric','unrelated_values','wrong_entity')):
            plans.append(dict(seed=seed+30000+ci*100+si,renderer='matplotlib',style='light',
                curve='step',step_where=where,pattern='random',control=control))
    for ci,where in enumerate(('pre','post')):
        plans.append(dict(seed=seed+31000+ci,renderer='pillow',style='light',curve='step',
            step_where=where,pattern='affine',control='ambiguous_convention'))
    protocol=dict(seed=seed,plans=plans,
        source_hashes={p.name:digest(p) for p in (out/'source').glob('*.py')},
        input='Image and linked profile with six redacted amounts. No curve convention, axis scale, ROI, numerical anchors or private date positions.',
        design='90 fresh cases: 60 pre/post/mid step charts (random levels or unequal runs of held levels), 30 linear/PCHIP/cubic regressions; two curve renderers, five styles. 14 controls include two intrinsically ambiguous pre/post affine trends. Both readers run on identical bytes.',
        inference='Reader and scorer snapshots and complete case plan are frozen before generating any image. Both inferences finish and write results before truth is parsed. Checking values never select a date grid or step convention.',
        acceptance='At least 8 fitting and 5 checking dates, fixed ordinal split; unique scale and, for step reader, unique plateau convention from fitting dates. Informative checking levels, NMAE <2% and coverage >=90%.',
        scoring='Same numerical criteria: correct scale, no hidden-source leakage, daily X error <=4px, no extrapolation, six hidden values at NMAE <2% of full value range. Revised step reader is scored on its exported daily plateau estimates; older reader and non-step results use raw-curve interpolation at proposed dates. Missing daily predictions fail. Both use the same updated scorer.',
        scoring_change='Explicit daily sampling avoids treating vertical-stroke midpoints as a day value. This changes the prediction representation, not date or monetary error thresholds. The raw-curve export is retained. Historical results are not overwritten.',
        limitations='Procedural source/image grammar, one English text renderer and font, assumed linked entity/year/daily metric; no independent public accuracy or learned model.')
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2), encoding="utf-8");rows={k:[] for k in readers};controls={k:[] for k in readers};manifest={}
    for plan in plans:
        folder=out/((('control-'+plan['control']+'-') if plan['control'] else '')+f"{plan['renderer']}-{plan['seed']}")
        values=None;axis_scale=None
        if plan['pattern']=='holds':
            rng=np.random.default_rng(plan['seed']);axis_scale='log' if plan['seed']%3==1 else 'linear'
            values=np.round(np.repeat(np.exp(rng.uniform(4.7,7.5,10)) if axis_scale=='log' else rng.uniform(250,1800,10),[2,4,1,3,2,5,1,4,3,5]),2)
        elif plan['pattern']=='affine':values=np.arange(30)*30.+300;axis_scale='linear'
        generate(folder,plan['seed'],plan['renderer'],plan['style'],
            control=None if plan['control']=='ambiguous_convention' else plan['control'],curve=plan['curve'],
            step_where=plan['step_where'],values=values,axis_scale=axis_scale)
        manifest[folder.name]={f:digest(folder/f) for f in ('chart.png','profile.md','truth.json')}
        profile=parse_profile((folder/'profile.md').read_text(encoding="utf-8"),URL)
        results={name:module.recover_external(folder/'chart.png',profile,folder/name) for name,module in readers.items()}
        truth=json.loads((folder/'truth.json').read_text(encoding="utf-8"))
        for name,result in results.items():
            if plan['control']:
                controls[name].append(dict(case=folder.name,kind=plan['control'],status=result['status'],abstained=result['status']!='conditional_calibration',reasons=result['reasons']))
            else:
                row=score(result,truth)
                row.update(case=folder.name,curve=plan['curve'],step_where=plan['step_where'] if plan['curve']=='step' else None,
                    pattern=plan['pattern'],alignment_strategy=result.get('alignment_search',{}).get('strategy'),
                    selected_convention=result.get('date_axis',{}).get('sampling',{}).get('convention'))
                rows[name].append(row)
        print(folder.name,*(f"{name}:{result['status']}" for name,result in results.items()),flush=True)
        (out/'progress.json').write_text(json.dumps(dict(rows=rows,controls=controls),indent=2), encoding="utf-8")
    assert all(digest(src/f)==protocol['source_hashes'][f] for f in files)
    assert all(digest(out/name/f)==h for name,fs in manifest.items() for f,h in fs.items())
    assert digest(baseline)==protocol['source_hashes']['baseline_external_evidence.py']
    (out/'inputs.json').write_text(json.dumps(manifest,indent=2), encoding="utf-8")
    summaries={name:dict(**totals(items),groups={group:totals([r for r in items if (r['curve']=='step')==(group=='step')]) for group in ('step','other')},
        rows=items,controls=controls[name]) for name,items in rows.items()}
    transitions=[dict(case=a['case'],baseline=a['success'],revised=b['success']) for a,b in zip(rows['baseline'],rows['revised']) if a['success']!=b['success']]
    summary=dict(protocol=protocol,readers=summaries,transitions=transitions,
        previously_passing_regressions=sum(t['baseline'] and not t['revised'] for t in transitions),
        new_passes=sum(not t['baseline'] and t['revised'] for t in transitions))
    (out/'summary.json').write_text(json.dumps(summary,indent=2), encoding="utf-8");return summary


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--baseline',required=True);p.add_argument('--seed',type=int,default=420000)
    a=p.parse_args();r=run(a.out,a.baseline,a.seed)
    print(json.dumps({k:{n:s[n] for n in ('cases','passed','abstentions','returned_failures','groups')} for k,s in r['readers'].items()},indent=2))
