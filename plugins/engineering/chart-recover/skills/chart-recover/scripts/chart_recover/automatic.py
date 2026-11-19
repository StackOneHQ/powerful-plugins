"""Bounded multi-reader workflow; retain every candidate and failed attempt.

Different panels can expose different metrics and axes. A successful reader
does not erase another reader's conflicts or imply that every panel recovered.
"""
from pathlib import Path
import hashlib
import json
from .pipeline import analyze
from .calendar_recovery import analyze_calendar
from .tick_recovery import analyze_ticks


def recover(image,config=None,output='artifacts/recovery'):
    config=dict(config or {});out=Path(output);out.mkdir(parents=True,exist_ok=True)
    source=config.get('source') or config.get('post_url');attempts=[]
    summary=dict(image=str(image),image_sha256=hashlib.sha256(Path(image).read_bytes()).hexdigest(),config=config,
                 status='needs_evidence_or_review',calibrated_candidates=0,attempts=attempts,
                 note='Readers may describe different panels. Results and conflicts are retained separately; no whole-image completion claim.')
    for name,reader,cfg in [('bars',analyze,dict(config,auto_layout=True,post_url=source)),
                            ('calendar',analyze_calendar,dict(config,source=source)),
                            ('ticks',analyze_ticks,dict(config,source=source))]:
        try:
            result=reader(image,cfg,out/name)
            reasons=list(result.get('correspondence',{}).get('reasons',[])) if name in ('calendar','ticks') else list(result['trace'][-1]['next_actions'])
            reasons=list(dict.fromkeys(reasons+[r['reason'] for r in result['recovery'] if r.get('reason')]))
            record=dict(reader=name,status=result['status'],outcomes=[r['status'] for r in result['recovery']],
                        series=len(result['geometry']['series']),result=f'{name}/result.json',csv=f'{name}/data.csv',overlay=f'{name}/overlay.png',
                        next_actions=reasons,assumptions=list(dict.fromkeys(a for r in result['recovery'] for a in r.get('assumptions',[]))))
            summary['calibrated_candidates']+=int(result['status']=='calibrated')
        except Exception as error:
            record=dict(reader=name,status='failed',error_type=type(error).__name__,reason=str(error),next_actions=['Inspect this reader failure; other attempts remain independent.'])
        attempts.append(record)
        summary['status']='has_calibrated_candidates' if summary['calibrated_candidates'] else 'needs_evidence_or_review'
        (out/'workflow.json').write_text(json.dumps(summary,indent=2), encoding="utf-8")
    return summary


def recover_batch(manifest,output,configs=None,defaults=None):
    manifest=Path(manifest);out=Path(output);out.mkdir(parents=True,exist_ok=True);records=[];configs=configs or {}
    summary=dict(images=0,images_with_calibrated_candidates=0,results=records)
    (out/'batch.json').write_text(json.dumps(summary,indent=2), encoding="utf-8")
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():continue
        post=json.loads(line);post_id=str(post['id'])
        if not post_id.isdigit():raise ValueError('Expected numeric post id')
        media=list(post.get('images',[]))
        if post.get('image'):media.append(dict(path=post['image']))
        for i,item in enumerate(media):
            image=(manifest.parent/item['path']).resolve()
            if not image.is_relative_to(manifest.parent.resolve()):raise ValueError('Image path outside manifest directory')
            config=dict(defaults or {});config.update(configs.get(post_id,{}))
            config.setdefault('source',post['url']);config.setdefault('post_date',post.get('created_at'))
            config.setdefault('post_text',post.get('text',post.get('text_excerpt','')))
            try:
                result=recover(image,config,out/f'{post_id}-{i}')
                record=dict(post_id=post_id,image=item['path'],status=result['status'],calibrated_candidates=result['calibrated_candidates'],
                            workflow=f'{post_id}-{i}/workflow.json')
            except (ValueError,OSError) as error:record=dict(post_id=post_id,image=item['path'],status='failed',reason=str(error),calibrated_candidates=0)
            records.append(record);summary['images']=len(records)
            summary['images_with_calibrated_candidates']=sum(r['calibrated_candidates']>0 for r in records)
            (out/'batch.json').write_text(json.dumps(summary,indent=2), encoding="utf-8")
    return summary
