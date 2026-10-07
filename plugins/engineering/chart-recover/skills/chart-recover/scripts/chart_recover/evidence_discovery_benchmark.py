"""Frozen full-agent study of source retrieval followed by numerical recovery."""
from pathlib import Path
import hashlib
import json
import shutil
from unittest.mock import patch
from .external_benchmark import generate,score
from .agent import investigate_image

NAMES=['Lumen','Cedar Metrics','Orbit Ledger','Northstar Tools','Copper Finch','Delta Workspace',
       'Pixel Harbor','Juniper Stack','Amber Note','Mint Circuit','Echo Desk','Quartz Studio']


def run(output,seed=150000):
    out=Path(output)
    if (out/'protocol.json').exists():raise ValueError('Use a fresh output directory')
    out.mkdir(parents=True,exist_ok=True);src=Path(__file__).parent;(out/'source').mkdir()
    for p in src.glob('*.py'):(out/'source'/p.name).write_bytes(p.read_bytes())
    protocol=dict(seed=seed,entities=NAMES,renderers=['pillow','matplotlib'],cases=24,
        source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (out/'source').glob('*.py')},
        input='Image, generic source-post URL and post text. No profile URL, entity metadata, scale, geometry, date coordinates or numeric anchors. Offline catalog and redacted profiles form a bounded candidate corpus.',
        discovery='Twelve target names and twelve longer-name decoys. Opaque canonical slugs are supplied only in the catalog. Even-index businesses appear in post text; odd-index names appear only in the image.',
        scoring='After full agent inference, read private truth. Require exactly the expected source candidate, plus the existing correct-scale, no-leakage, <=4px X error, no-extrapolation and <2% hidden-value NMAE criteria.',
        limitations='24 different rendered images of 12 numerical datasets; two renderers, five styles, one English font/source grammar. A constructed candidate corpus, not independent public discovery accuracy. No network is permitted during inference.')
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2), encoding="utf-8");cache=out/'cache';(cache/'profiles').mkdir(parents=True)
    entries=[dict(name=name,slug=f'fixture-{seed+71*i}') for i,name in enumerate(NAMES)]
    payload=dict(recentlyAddedStartups=entries+[dict(name=e['name']+' Research',slug=e['slug']+'-decoy') for e in entries],fastestGrowingStartups=[])
    (cache/'discovery.json').write_text(json.dumps(payload,indent=2), encoding="utf-8");rows=[]
    with patch('requests.sessions.Session.request',side_effect=AssertionError('Offline evaluation attempted network access')):
        for i,entry in enumerate(entries):
            for renderer in ('pillow','matplotlib'):
                folder=out/f'{renderer}-{seed+i}';style=['light','dark','filled','jpeg','small'][i%5]
                generate(folder,seed+i,renderer,style,entity=entry['name'],slug=entry['slug'])
                (cache/'profiles'/f"{entry['slug']}.md").write_bytes((folder/'profile.md').read_bytes())
                text=f"Daily revenue for {entry['name']}." if i%2==0 else 'Here is this month’s daily revenue chart.'
                config=dict(source=f'https://x.com/fixture/status/{seed+i}',post_text=text,evidence_cache=str(cache))
                (folder/'input.json').write_text(json.dumps(config,indent=2), encoding="utf-8")
                agent=investigate_image(folder/'chart.png',config,folder/'analysis')
                discovery=json.loads((folder/'analysis/evidence-discovery/discovery.json').read_text(encoding="utf-8"))
                candidate_path=folder/'analysis/conditional-external/result.json'
                result=json.loads(candidate_path.read_text(encoding="utf-8")) if candidate_path.exists() else dict(status='needs_evidence_or_review',reasons=['No external reconstruction; inspect discovery and agent trace.'])
                truth=json.loads((folder/'truth.json').read_text(encoding="utf-8"));row=score(result,truth)
                expected=f"https://trustmrr.com/startup/{entry['slug']}.md"
                selected=[c['url'] for c in discovery['candidates']]
                row.update(entity=entry['name'],evidence_mode='post_and_image' if i%2==0 else 'image_only',
                    expected_profile=expected,source_candidates=selected,correct_source=selected==[expected],
                    numerical_success=row['success'],profile_url_supplied=False)
                row['success']=row['numerical_success'] and row['correct_source'];rows.append(row)
                (out/'cases.json').write_text(json.dumps(rows,indent=2), encoding="utf-8");print(renderer,entry['name'],row['correct_source'],row['status'],row['success'],flush=True)
        controls=[]
        for j,control in enumerate(['no_matching_name','too_many_links','missing_profile','wrong_profile_identity','wrong_metric','wrong_year','wrong_entity_link','unrelated_values']):
            folder=out/f'control-{control}';local_cache=folder/'cache';shutil.copytree(cache,local_cache)
            entry=entries[0];render_control=control if control in ('wrong_metric','wrong_year','unrelated_values') else None
            generate(folder,seed+500+j,control=render_control,entity=entry['name'],slug=entry['slug'])
            (local_cache/'profiles'/f"{entry['slug']}.md").write_bytes((folder/'profile.md').read_bytes())
            config=dict(source=f'https://x.com/fixture/status/{seed+500+j}',post_text='Daily revenue update.',evidence_cache=str(local_cache))
            if control=='no_matching_name':(local_cache/'discovery.json').write_text(json.dumps(dict(recentlyAddedStartups=[],fastestGrowingStartups=[])), encoding="utf-8")
            elif control=='too_many_links':config['post_text']=' '.join('https://trustmrr.com/startup/'+e['slug'] for e in entries[:4])
            elif control=='missing_profile':(local_cache/'profiles'/f"{entry['slug']}.md").unlink()
            elif control=='wrong_profile_identity':
                p=local_cache/'profiles'/f"{entry['slug']}.md";p.write_text(p.read_text(encoding="utf-8").replace(f"`{entry['slug']}`",'`different-slug`'), encoding="utf-8")
            elif control=='wrong_entity_link':config['post_text']='https://trustmrr.com/startup/'+entries[1]['slug']
            (folder/'input.json').write_text(json.dumps(config,indent=2), encoding="utf-8")
            agent=investigate_image(folder/'chart.png',config,folder/'analysis')
            controls.append(dict(case=control,abstained=agent['conditional_candidates']==0 and agent['strict_candidates']==0,status=agent['status'],steps=agent['steps']))
    summary=dict(protocol=protocol,cases=len(rows),passed=sum(r['success'] for r in rows),correct_source=sum(r['correct_source'] for r in rows),
        abstentions=sum(r['status']!='conditional_calibration' for r in rows),
        incorrect_returned_candidates_under_criteria=sum(r['status']=='conditional_calibration' and not r['success'] for r in rows),rows=rows,controls=controls)
    (out/'summary.json').write_text(json.dumps(summary,indent=2), encoding="utf-8");return summary


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--seed',type=int,default=150000)
    a=p.parse_args();r=run(a.out,a.seed);print(json.dumps({k:v for k,v in r.items() if k not in ('rows','protocol','controls')},indent=2))
