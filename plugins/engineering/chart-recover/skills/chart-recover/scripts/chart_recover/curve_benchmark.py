"""Fresh smooth and step-chart evaluation for conditional external recovery."""
from pathlib import Path
import hashlib
import json
from .external_benchmark import generate,score,URL
from .external_evidence import recover_external
from .public_profile import parse_profile


def run(output,seed=230000):
    out=Path(output)
    if (out/'protocol.json').exists():raise ValueError('Use a fresh output directory')
    out.mkdir(parents=True,exist_ok=True);(out/'source').mkdir();src=Path(__file__).parent
    files=['curve_benchmark.py','external_benchmark.py','external_evidence.py','public_profile.py','vision.py','ocr.py','autopilot.py','calibrate.py','calendar_vision.py']
    for f in files:(out/'source'/f).write_bytes((src/f).read_bytes())
    protocol=dict(seed=seed,cases=30,controls=9,curves=['pchip','cubic','step'],
        source_hashes={f:hashlib.sha256((src/f).read_bytes()).hexdigest() for f in files},
        input='Image and redacted daily source table; no curve mode, scale, geometry or date coordinates. Six source amounts are hidden.',
        design='PCHIP, natural cubic spline and right-continuous step rendering. Two independent curve renderers; light, dark, filled, JPEG and small-text styles. Linear/log axes. Spline axis bounds include overshoot; daily values are exact interpolation nodes.',
        acceptance='Current production geometry/fitting-date strategy is selected before checking values. The same unique-scale and informative-checking rules apply.',
        scoring='After inference, open private truth. Six missing table values; require correct scale, no hidden-value leakage, proposed X alignment <=4px, no extrapolation, hidden-value NMAE <2% of value range.',
        method_diagnostic='Separately count corner-grid selection on smooth and step inputs; numerical success alone does not prove the geometric assumption.',
        limitations='Procedural curves with a known source URL and English daily labels; not independent public identity or accounting accuracy.')
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2), encoding="utf-8");rows=[];controls=[]
    for ri,renderer in enumerate(('pillow','matplotlib')):
        for ci,curve in enumerate(protocol['curves']):
            for j,style in enumerate(('light','dark','filled','jpeg','small')):
                case_seed=seed+ri*1000+ci*100+j;p=out/f'{renderer}-{case_seed}'
                generate(p,case_seed,renderer,style,curve=curve)
                result=recover_external(p/'chart.png',parse_profile((p/'profile.md').read_text(encoding="utf-8"),URL),p/'analysis')
                row=score(result,json.loads((p/'truth.json').read_text(encoding="utf-8")))
                row.update(curve=curve,alignment_strategy=result.get('alignment_search',{}).get('strategy'))
                rows.append(row);(out/'cases.json').write_text(json.dumps(rows,indent=2), encoding="utf-8")
                print(renderer,curve,style,row['status'],row['success'],row['alignment_strategy'],flush=True)
    for ci,curve in enumerate(protocol['curves']):
        for j,control in enumerate(('wrong_year','wrong_metric','unrelated_values')):
            name=f'{curve}-{control}';p=out/f'control-{name}'
            generate(p,seed+3000+ci*10+j,control=control,curve=curve)
            result=recover_external(p/'chart.png',parse_profile((p/'profile.md').read_text(encoding="utf-8"),URL),p/'analysis')
            controls.append(dict(case=name,status=result['status'],abstained=result['status']!='conditional_calibration',reasons=result['reasons']))
    summary=dict(protocol=protocol,cases=len(rows),passed=sum(r['success'] for r in rows),
        abstentions=sum(r['status']!='conditional_calibration' for r in rows),
        incorrect_returned_candidates_under_criteria=sum(r['status']=='conditional_calibration' and not r['success'] for r in rows),
        corner_grids_on_non_linear_curves=sum(r['alignment_strategy']=='image_corners' for r in rows),rows=rows,controls=controls)
    (out/'summary.json').write_text(json.dumps(summary,indent=2), encoding="utf-8");return summary


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--seed',type=int,default=230000)
    a=p.parse_args();r=run(a.out,a.seed)
    print(json.dumps({k:v for k,v in r.items() if k not in ('protocol','rows','controls')},indent=2))
