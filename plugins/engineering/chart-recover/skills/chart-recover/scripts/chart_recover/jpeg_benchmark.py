"""Frozen palette/compression/size challenge for external-table curve recovery."""
from pathlib import Path
import hashlib
import itertools
import json
from .external_benchmark import generate,score,URL
from .external_evidence import recover_external
from .public_profile import parse_profile


def run(output,seed=120000):
    out=Path(output)
    if (out/'protocol.json').exists():raise ValueError('Use a fresh output directory')
    out.mkdir(parents=True,exist_ok=True);source=Path(__file__).parent;(out/'source').mkdir(exist_ok=True)
    files=['jpeg_benchmark.py','external_benchmark.py','external_evidence.py','public_profile.py','vision.py','ocr.py','autopilot.py','calibrate.py','calendar_vision.py']
    for f in files:(out/'source'/f).write_bytes((source/f).read_bytes())
    settings=list(itertools.product(['pillow','matplotlib'],['#e22a36','#18aa78','#d68416'],[35,55,75],[1.,.8]))
    protocol={'seed':seed,'cases':len(settings),'source_hashes':{f:hashlib.sha256((source/f).read_bytes()).hexdigest() for f in files},
              'input':'Image and linked fictional profile; six source amounts redacted; no numeric anchor, scale, crop, color or date coordinates supplied.',
              'design':'Two renderers × three new hues (red, green, orange) × JPEG qualities 35/55/75 × original/80% size. No clean cases in this challenge. One source grammar and one font family.',
              'acceptance':'Unchanged external-table fit/check and unique-scale criteria. Strong hue seeds expand to observed faint pixels; no hidden truth enters extraction or alignment.',
              'scoring':'Correct scale, no hidden-value leakage, <=4px proposed X error, no extrapolation and six-amount NMAE <2% of the full value range. Truth is read only after inference.',
              'controls':'Eleven JPEG controls at quality 45, including crossed same-hue curves, a missing middle, and no chart. Control acceptance is retained as a failure, not excluded.',
              'limitations':'Procedural graphics; no public source identity or independent accounting truth is established.'}
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2), encoding="utf-8");rows=[]
    for j,(renderer,color,quality,size) in enumerate(settings):
        name=f'{renderer}-{seed+j}';p=out/name
        generate(p,seed+j,renderer,'jpeg',color=color,jpeg_quality=quality,image_scale=size)
        result=recover_external(p/'chart.png',parse_profile((p/'profile.md').read_text(encoding="utf-8"),URL),p/'analysis')
        row=score(result,json.loads((p/'truth.json').read_text(encoding="utf-8")));row['render_settings']={'color':color,'jpeg_quality':quality,'image_scale':size}
        rows.append(row);(out/'cases.json').write_text(json.dumps(rows,indent=2), encoding="utf-8");print(name,row['status'],row['success'],flush=True)
    controls=[]
    for j,control in enumerate(['wrong_entity','wrong_metric','wrong_year','ambiguous_year','reversed_dates','unrelated_values','no_amounts','two_curves','same_hue_two_curves','missing_middle','chart_absent']):
        p=out/f'control-{control}';generate(p,seed+5000+j,style='jpeg',control=control,jpeg_quality=45)
        r=recover_external(p/'chart.png',parse_profile((p/'profile.md').read_text(encoding="utf-8"),URL),p/'analysis')
        controls.append({'case':control,'status':r['status'],'abstained':r['status']!='conditional_calibration','reasons':r['reasons']})
    summary={'protocol':protocol,'cases':len(rows),'passed':sum(r['success'] for r in rows),'abstentions':sum(r['status']!='conditional_calibration' for r in rows),
             'incorrect_returned_candidates_under_criteria':sum(r['status']=='conditional_calibration' and not r['success'] for r in rows),'rows':rows,'controls':controls}
    (out/'summary.json').write_text(json.dumps(summary,indent=2), encoding="utf-8");return summary


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--seed',type=int,default=120000)
    args=p.parse_args();r=run(args.out,args.seed);print(json.dumps({k:v for k,v in r.items() if k not in ['protocol','rows']},indent=2))
