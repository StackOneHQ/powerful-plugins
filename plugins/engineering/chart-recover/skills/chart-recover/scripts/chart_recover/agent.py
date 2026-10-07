"""Inspect -> run readers -> test correspondence hypotheses -> export evidence."""
from pathlib import Path
import csv
import json
from .automatic import recover
from .hypotheses import propose_calendar,candidate_result
from .vision import overlay


def investigate_image(image,config=None,output='artifacts/agent',strict_only=False,evidence_resolver=None):
    config=dict(config or {})
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    workflow=recover(image,config,out/'readers')
    summary=dict(image=str(image),image_sha256=workflow['image_sha256'],status=workflow['status'],
                 strict_candidates=workflow['calibrated_candidates'],conditional_candidates=0,
                 steps=[dict(action='run_automatic_readers',workflow='readers/workflow.json',status=workflow['status'])],
                 conditional_results=[],policy='Conditional estimates are explicitly separated from strict calibration. Dates and identity are not inferred from numerical agreement.')
    calendar_path=out/'readers/calendar/result.json'
    current_calendar=next((a for a in workflow.get('attempts',[]) if a['reader']=='calendar' and a.get('result')=='calendar/result.json' and a['status']!='failed'),None)
    calendar=json.loads(calendar_path.read_text(encoding="utf-8")) if current_calendar and calendar_path.exists() else None
    if not strict_only and calendar and calendar.get('image_sha256')==workflow['image_sha256']:
        proposal=propose_calendar(calendar)
        (out/'hypotheses.json').write_text(json.dumps(proposal,indent=2,allow_nan=False), encoding="utf-8")
        summary['steps'].append(dict(action='test_calendar_association',status=proposal['status'],evidence='hypotheses.json'))
        candidate=candidate_result(calendar,proposal)
        if candidate and calendar['status']!='calibrated':
            folder=out/'conditional-calendar';folder.mkdir(exist_ok=True)
            (folder/'result.json').write_text(json.dumps(candidate,indent=2,allow_nan=False), encoding="utf-8")
            overlay(image,candidate['geometry'],folder/'overlay.png')
            with (folder/'data.csv').open('w',newline='') as f:
                writer=csv.writer(f);writer.writerow(['point','relative_position','plot_date','pixel_x','pixel_y','conditional_value','lower','upper','status'])
                series=candidate['geometry']['series'][0];cal=candidate['recovery'][0];points=series['points']
                for i,p in enumerate(points):writer.writerow([i,i/(len(points)-1),'',p['x'],p['y'],cal['values'][i],cal['lower'][i],cal['upper'][i],'conditional_calibration'])
            summary['conditional_candidates']=1
            summary['conditional_results'].append(dict(reader='calendar',result='conditional-calendar/result.json',csv='conditional-calendar/data.csv',
                                                       overlay='conditional-calendar/overlay.png',status='conditional_calibration',date_assignment='unassigned',
                                                       assumptions=candidate['correspondence']['assumptions']))
            if not workflow['calibrated_candidates']:summary['status']='has_conditional_candidates'
    if not strict_only and config.get('post_text'):
        from .first_customer import caption_claim,recover_first_customer
        claim=caption_claim(config['post_text'],config.get('source') or config.get('post_url'))
        (out/'caption-claim.json').write_text(json.dumps(claim,indent=2,allow_nan=False), encoding="utf-8")
        summary['steps'].append(dict(action='inspect_first_customer_caption',status=claim['status'],evidence='caption-claim.json'))
        if claim['status']=='proposed':
            folder='conditional-first-customer'
            first=recover_first_customer(image,config,out/folder)
            summary['steps'].append(dict(action='test_first_customer_zero_history',status=first['status'],
                result=f'{folder}/result.json',evidence_strength=first['evidence_strength']))
            if first['status']=='conditional_calibration':
                summary['conditional_candidates']+=1
                summary['conditional_results'].append(dict(reader='first_customer',result=f'{folder}/result.json',
                    csv=f'{folder}/data.csv',overlay=f'{folder}/overlay.png',status=first['status'],
                    date_assignment='unassigned',evidence_strength=first['evidence_strength'],assumptions=first['assumptions']))
                if not workflow['calibrated_candidates']:summary['status']='has_conditional_candidates'
    if not strict_only:
        from .comparison_totals import recover_comparison
        folder='conditional-comparison-totals'
        comparison=recover_comparison(image,config,out/folder)
        summary['steps'].append(dict(action='test_comparison_totals',status=comparison['status'],
            result=f'{folder}/result.json',evidence_strength=comparison['evidence_strength']))
        if comparison['status']=='conditional_calibration':
            summary['conditional_candidates']+=1
            summary['conditional_results'].append(dict(reader='comparison_totals',result=f'{folder}/result.json',
                csv=f'{folder}/data.csv',overlay=f'{folder}/overlay.png',status=comparison['status'],
                evidence_strength=comparison['evidence_strength'],date_assignment=comparison['date_assignment'],assumptions=comparison['assumptions']))
            if not workflow['calibrated_candidates']:summary['status']='has_conditional_candidates'
    sources=[]
    discovery_enabled=config.get('discover_evidence') or config.get('evidence_cache')
    if discovery_enabled:
        if strict_only:
            summary['steps'].append(dict(action='discover_external_evidence',status='disabled_by_strict_policy'))
        elif not config.get('evidence_profile_url'):
            from .evidence_discovery import EvidenceDiscovery
            evidence_resolver=evidence_resolver or EvidenceDiscovery(out/'evidence-catalog',config.get('evidence_cache'))
            discovery=evidence_resolver.discover(image,config,out/'evidence-discovery')
            summary['steps'].append(dict(action='discover_external_evidence',status=discovery['status'],
                                         evidence='evidence-discovery/discovery.json',candidate_count=len(discovery['candidates'])))
            if discovery['status']=='candidates_found':sources=discovery['candidates']
    if config.get('evidence_profile_url'):
        sources=[dict(url=config['evidence_profile_url'],basis=[dict(kind='user_supplied_profile_url')])]
    for index,candidate_source in enumerate(sources):
        if strict_only:
            summary['steps'].append(dict(action='external_public_profile',status='disabled_by_strict_policy'))
        else:
            from .public_profile import fetch_profile,parse_profile
            from .external_evidence import recover_external
            import requests
            try:
                suffix='' if len(sources)==1 else f'-{index+1}'
                evidence_name='external-profile'+suffix;result_name='conditional-external'+suffix
                evidence=out/evidence_name;evidence.mkdir(exist_ok=True)
                if config.get('evidence_profile_snapshot'):
                    text=Path(config['evidence_profile_snapshot']).read_text(encoding="utf-8")
                    profile=parse_profile(text,candidate_source['url'])
                    (evidence/'profile.md').write_text(text, encoding="utf-8")
                    (evidence/'profile.json').write_text(json.dumps(profile,indent=2), encoding="utf-8")
                elif evidence_resolver:profile=evidence_resolver.profile(candidate_source['url'],evidence)
                else:profile=fetch_profile(candidate_source['url'],evidence)
                external=recover_external(image,profile,out/result_name)
                summary['steps'].append(dict(action='external_public_profile',status=external['status'],
                                             evidence=f'{evidence_name}/profile.json',result=f'{result_name}/result.json',source_candidate=candidate_source,
                                             reasons=external['reasons']))
                if external['status']=='conditional_calibration':
                    summary['conditional_candidates']+=1
                    summary['conditional_results'].append(dict(reader='external_daily_revenue',result=f'{result_name}/result.json',
                        csv=f'{result_name}/data.csv',overlay=f'{result_name}/overlay.png',status=external['status'],source_candidate=candidate_source,
                        date_assignment=external['date_assignment'],assumptions=external['assumptions']))
                    if external.get('daily_recovery'):summary['conditional_results'][-1]['daily_csv']=f'{result_name}/daily.csv'
                    if not workflow['calibrated_candidates']:summary['status']='has_conditional_candidates'
            except (ValueError,OSError,RuntimeError,requests.RequestException) as e:
                summary['steps'].append(dict(action='external_public_profile',status='unavailable',source_candidate=candidate_source,reason=str(e)))
    summary['steps'].append(dict(action='stop',reason='All available automatic readers and enabled correspondence hypotheses evaluated; no absolute value is invented from shape alone.'))
    (out/'agent.json').write_text(json.dumps(summary,indent=2,allow_nan=False), encoding="utf-8");return summary


def investigate_batch(manifest,output='artifacts/agent-batch',strict_only=False,discover_evidence=False,evidence_cache=None):
    manifest=Path(manifest);out=Path(output);out.mkdir(parents=True,exist_ok=True);rows=[]
    resolver=None
    if (discover_evidence or evidence_cache) and not strict_only:
        from .evidence_discovery import EvidenceDiscovery
        resolver=EvidenceDiscovery(out/'evidence-catalog',evidence_cache)
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():continue
        post=json.loads(line);post_id=str(post['id'])
        if not post_id.isdigit():raise ValueError('Expected numeric post id')
        for i,media in enumerate(post.get('images',[])):
            path=(manifest.parent/media['path']).resolve()
            if not path.is_relative_to(manifest.parent.resolve()):raise ValueError('Image path outside manifest directory')
            result=investigate_image(path,dict(source=post['url'],post_text=post.get('text',''),post_links=post.get('links',[]),
                post_date=post.get('created_at'),discover_evidence=discover_evidence,evidence_cache=evidence_cache),out/f'{post_id}-{i}',strict_only,resolver)
            rows.append(dict(post_id=post_id,image=media['path'],status=result['status'],strict_candidates=result['strict_candidates'],
                             conditional_candidates=result['conditional_candidates'],result=f'{post_id}-{i}/agent.json'))
            summary=dict(images=len(rows),images_with_strict_candidates=sum(r['strict_candidates']>0 for r in rows),
                         images_with_conditional_candidates=sum(r['conditional_candidates']>0 for r in rows),results=rows)
            (out/'batch.json').write_text(json.dumps(summary,indent=2), encoding="utf-8");print(post_id,result['status'],flush=True)
    return dict(images=len(rows),images_with_strict_candidates=sum(r['strict_candidates']>0 for r in rows),
                images_with_conditional_candidates=sum(r['conditional_candidates']>0 for r in rows),results=rows)
