"""Sparse-revenue evaluation with informative and flat checking sets."""
from datetime import date
from pathlib import Path
import hashlib
import json
import numpy as np
from .external_benchmark import generate,score,URL
from .external_evidence import recover_external
from .public_profile import parse_profile


def run(output,seed=160000,per_renderer=4,styles=('light','dark')):
    if not 1<=per_renderer<100:raise ValueError('per_renderer must be between 1 and 99 to keep case seeds distinct')
    if not styles or any(s not in ('light','dark','filled','jpeg','small') for s in styles):raise ValueError('Unsupported sparse style')
    out=Path(output)
    if (out/'protocol.json').exists():raise ValueError('Use a fresh output directory')
    out.mkdir(parents=True,exist_ok=True);(out/'source').mkdir();src=Path(__file__).parent
    files=sorted(p.name for p in Path(__file__).parent.glob('*.py'))
    for f in files:(out/'source'/f).write_bytes((src/f).read_bytes())
    protocol=dict(seed=seed,per_renderer=per_renderer,styles=list(styles),cases=2*per_renderer,controls=2*per_renderer,source_hashes={f:hashlib.sha256((src/f).read_bytes()).hexdigest() for f in files},
        design='Sparse linear daily revenue, mostly zero. Positive cases have distinct fitting/checking levels and one hidden positive peak. Controls have only zero checking values. Two renderers with the explicitly listed styles.',
        input='Image and redacted external-profile-format source, no supplied axis scale or geometry. Six source amounts hidden.',
        acceptance='Prefer a daily grid supported by visible straight-segment joins and withheld central pixels; otherwise use the fixed fitting-date search. Strategy is fixed before checking values. Unique-scale and <2% checking error / >=90% coverage rules, plus at least two checking levels distinguishable in rounded-value and pixel intervals. The split is never changed.',
        scoring='Correct scale, no hidden-value leakage, <=4px proposed X error, no extrapolation and six-amount NMAE <2% of the full value range. Truth is read only after inference.',
        limitations='Procedural sparse curves and a supplied profile source; tests informative-checking policy, not independent public identity or general accuracy.')
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2), encoding="utf-8");rows=[];controls=[];hidden=[3,8,13,19,23,27]
    fit=[i for i in range(30) if i not in hidden and date(2026,9,i+1).toordinal()%3!=1]
    check=[i for i in range(30) if i not in hidden and date(2026,9,i+1).toordinal()%3==1]
    for ri,renderer in enumerate(('pillow','matplotlib')):
        for flat in (False,True):
            for j in range(per_renderer):
                case_seed=seed+ri*1000+(100 if flat else 0)+j;rng=np.random.default_rng(case_seed);values=np.zeros(30)
                for i in rng.choice(fit,3,replace=False):values[i]=round(float(rng.uniform(80,1200)),2)
                values[hidden[j%len(hidden)]]=round(float(rng.uniform(300,1100)),2)
                if not flat:
                    for i in rng.choice(check,2,replace=False):values[i]=round(float(rng.uniform(150,1000)),2)
                name=f'{renderer}-{case_seed}' if not flat else f'control-flat-{renderer}-{case_seed}'
                p=out/name;generate(p,case_seed,renderer,styles[j%len(styles)],values=values,axis_scale='linear')
                r=recover_external(p/'chart.png',parse_profile((p/'profile.md').read_text(encoding="utf-8"),URL),p/'analysis')
                if flat:
                    controls.append(dict(case=name.removeprefix('control-'),status=r['status'],abstained=r['status']!='conditional_calibration',
                        checking_information=r.get('checking_information'),reasons=r['reasons']))
                else:
                    row=score(r,json.loads((p/'truth.json').read_text(encoding="utf-8")));rows.append(row);(out/'cases.json').write_text(json.dumps(rows,indent=2), encoding="utf-8")
                print(name,r['status'],flush=True)
    summary=dict(protocol=protocol,cases=len(rows),passed=sum(r['success'] for r in rows),abstentions=sum(r['status']!='conditional_calibration' for r in rows),
        incorrect_returned_candidates_under_criteria=sum(r['status']=='conditional_calibration' and not r['success'] for r in rows),rows=rows,controls=controls)
    (out/'summary.json').write_text(json.dumps(summary,indent=2), encoding="utf-8");return summary


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--seed',type=int,default=160000)
    p.add_argument('--per-renderer',type=int,default=4);p.add_argument('--styles',default='light,dark')
    a=p.parse_args();r=run(a.out,a.seed,a.per_renderer,tuple(a.styles.split(',')));print(json.dumps({k:v for k,v in r.items() if k not in ('protocol','rows')},indent=2))
