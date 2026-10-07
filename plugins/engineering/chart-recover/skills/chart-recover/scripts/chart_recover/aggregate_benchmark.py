"""Frozen-seed reconstruction from two period totals, with no point values."""
from pathlib import Path
import json
import numpy as np
from .synthetic import generate_one
from .pipeline import analyze

ROOT=Path(__file__).resolve().parent.parent


def run(per_kind=20,seed=22000,output=None):
    out=Path(output) if output else ROOT/'artifacts/aggregate-heldout';out.mkdir(parents=True,exist_ok=True)
    rows=[]
    for k,kind in enumerate(('bar','line','area','scatter')):
        for i in range(per_kind):
            number=seed+k*100+i;folder=out/'cases'/f'{kind}-{number}'
            truth=generate_one(folder,number,kind,'linear',('clean','dark','jpeg','small','truncated')[i%5])
            values=[p['value'] for p in truth['series'][0]['points']];n=len(values);split=n//2
            # The analyzer receives the image, observation count, kind, scale,
            # group membership and two SUMS, never per-point truth or y pixels.
            totals=[]
            for indices in (list(range(split)),list(range(split,n))):
                totals.append(dict(kind='sum',series='series_0',point_indices=indices,observation_count=len(indices),
                                   value=sum(values[j] for j in indices),source='Disclosed synthetic period total',matched=True))
            cfg=dict(kind=kind,scale='linear',ocr=False,samples=n,totals=totals)
            (folder/'config.json').write_text(json.dumps(cfg,indent=2), encoding="utf-8")
            row=dict(seed=number,kind=kind,variant=truth['variant'],expected_marks=n,status='failed')
            try:
                result=analyze(folder/'chart.png',cfg,folder/'recovery')
                geo=result['geometry']['series'];cal=result['recovery']
                if len(geo)!=1 or len(geo[0]['points'])!=n or cal[0]['status']!='calibrated':
                    row['reason']='Incomplete or ambiguous extraction/calibration'
                else:
                    pred=np.asarray(cal[0]['values']);actual=np.asarray(values)
                    nmae=float(np.abs(pred-actual).mean()/np.ptp(actual))
                    true_x=np.array([p['x'] for p in truth['series'][0]['points']]);pred_x=np.array([p['x'] for p in geo[0]['points']])
                    max_x_error=float(np.max(np.abs(true_x-pred_x)))
                    aligned=bool(max_x_error<max(4,np.median(np.diff(true_x))*.15))
                    row.update(nmae=nmae,max_x_error=max_x_error,aligned=aligned,
                               coverage=float(np.mean((np.array(cal[0]['lower'])<=actual)&(actual<=np.array(cal[0]['upper'])))),
                               status='passed' if aligned and nmae<.02 else 'failed')
            except (ValueError,IndexError) as error:row['reason']=str(error)
            rows.append(row)
    groups={kind:dict(charts=len(group),passed=sum(r['status']=='passed' for r in group),
                     median_nmae=float(np.median([r['nmae'] for r in group if 'nmae' in r])) if any('nmae' in r for r in group) else None)
            for kind in ('bar','line','area','scatter') if (group:=[r for r in rows if r['kind']==kind])}
    summary=dict(charts=len(rows),passed=sum(r['status']=='passed' for r in rows),seed=seed,groups=groups,
                 protocol='Known kind, linear scale, observation count and memberships of two disclosed period totals. No point values, baseline, ROI or true pixel coordinates enter analyze. All individual points scored; NMAE < 2% and x alignment required.',
                 limits='Synthetic conditional evaluation; source discovery and natural-language interpretation are not scored.')
    (out/'cases.json').write_text(json.dumps(rows,indent=2), encoding="utf-8");(out/'summary.json').write_text(json.dumps(summary,indent=2), encoding="utf-8")
    print(json.dumps(summary,indent=2));return summary

if __name__=='__main__':run()
