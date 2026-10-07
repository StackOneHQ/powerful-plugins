"""Bounded evidence-round orchestration; source content is data, never commands."""
from pathlib import Path
import hashlib
import json
from .pipeline import analyze


def investigate(image,config,output,max_rounds=5,retriever=None):
    """Try supplied evidence packets in order; stop when solved or exhausted.

    A corpus or X retriever can discover documents. With chart_context, the
    semantic binder matches dated facts to extracted marks without manual y
    anchors. Reviewed evidence packets remain supported. Source truth and
    chart context are conditional; retrieval rank never authorizes a match.
    """
    if not 1<=max_rounds<=20:raise ValueError('max_rounds must be 1..20')
    config=dict(config);packets=list(config.pop('evidence_rounds',[]));history=[]
    seen=set();out=Path(output);out.mkdir(parents=True,exist_ok=True)
    retrieval_config=config.pop('retrieval',None)
    if retriever is None and retrieval_config:
        from .retrieval import CorpusRetriever,XRetriever
        provider=retrieval_config.get('provider','corpus')
        if provider=='corpus':retriever=CorpusRetriever.from_jsonl(retrieval_config['path'])
        elif provider=='x':retriever=XRetriever()
        else:raise ValueError('retrieval provider must be corpus or x')
    if retriever is not None:
        from .retrieval import plan_queries
        context=config.get('chart_context',{})
        documents=retriever.retrieve(context,limit=(retrieval_config or {}).get('limit',30))
        discovery=dict(queries=plan_queries(context),documents=documents,
                       note='Retrieved documents require semantic/date binding; rankings are not verified evidence.')
        (out/'retrieval.json').write_text(json.dumps(discovery,indent=2), encoding="utf-8")
        # Inspect all retrieved evidence together so later conflicting facts are
        # not hidden by an early success on the first two disclosures.
        if documents:packets.insert(0,dict(evidence_documents=documents))
    result=None
    for round_no in range(min(max_rounds,len(packets)+1)):
        if round_no:
            packet=packets[round_no-1]
            for key in ('anchors','evidence_documents'):
                if packet.get(key):config[key]=config.get(key,[])+packet[key]
            # A reviewed scale/baseline observation may resolve a hypothesis.
            for key in ('scale','baseline'):
                if key in packet:config[key]=packet[key]
        fingerprint=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
        if fingerprint in seen:
            history.append({'round':round_no,'action':'stop','reason':'No new evidence'});break
        seen.add(fingerprint)
        result=analyze(image,config,out/f'round-{round_no}')
        history.append(dict(round=round_no,status=result['status'],outcomes=[r['status'] for r in result['recovery']],
                            requested_evidence=result['trace'][-1]['next_actions']))
        if result['status']=='calibrated' and (retriever is None or not documents or round_no>=1):break
        if any(r['status']=='inconsistent' for r in result['recovery']):break
    retrieval_evaluated=retriever is None or not documents or any(h.get('round',0)>=1 and h.get('status') for h in history)
    final=dict(status=result['status'] if retrieval_evaluated else 'needs_evidence_or_review',rounds=history,
               retrieval_evaluated=retrieval_evaluated,
               final_result=f"round-{history[-1]['round'] if history[-1].get('status') else history[-2]['round']}/result.json")
    (out/'investigation.json').write_text(json.dumps(final,indent=2), encoding="utf-8");return final


def batch(manifest,output,configs=None,defaults=None):
    manifest=Path(manifest);out=Path(output);out.mkdir(parents=True,exist_ok=True);results=[];configs=configs or {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():continue
        post=json.loads(line);post_id=post['id']
        if not str(post_id).isdigit():raise ValueError('Expected numeric post id')
        images=post.get('images',[])
        if post.get('image'):images=images+[{'path':post['image']}]
        for i,media in enumerate(images):
            path=(manifest.parent/media['path']).resolve()
            if not path.is_relative_to(manifest.parent.resolve()):raise ValueError('Image path outside manifest directory')
            cfg=dict(defaults or {});cfg.update(configs.get(str(post_id),{}))
            cfg.setdefault('post_text',post.get('text',post.get('text_excerpt','')));cfg.setdefault('post_url',post['url'])
            cfg.setdefault('post_date',post.get('created_at'))
            try:
                r=investigate(path,cfg,out/f'{post_id}-{i}')
                results.append(dict(post_id=post_id,image=media['path'],**r))
            except (ValueError,OSError) as e:results.append(dict(post_id=post_id,image=media['path'],status='failed',reason=str(e)))
    summary=dict(images=len(results),calibrated=sum(r['status']=='calibrated' for r in results),results=results)
    (out/'batch.json').write_text(json.dumps(summary,indent=2), encoding="utf-8");return summary
