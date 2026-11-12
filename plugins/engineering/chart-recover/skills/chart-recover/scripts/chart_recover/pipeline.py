"""Bounded investigate → extract → gather → calibrate → verify loop."""
from __future__ import annotations
import csv
import hashlib
import json
import math
from pathlib import Path
from .vision import extract,overlay
from .calibrate import calibrate
from .evidence import claims_from_text,match_reference
from .ocr import read_text
from .semantic import bind_documents
from .constraints import calibrate_totals


def analyze(image,config=None,output='artifacts/analysis'):
    config=config or {};out=Path(output);out.mkdir(parents=True,exist_ok=True);trace=[]
    trace.append(dict(step='inspect',image_sha256=hashlib.sha256(Path(image).read_bytes()).hexdigest()))
    visual=None
    if config.get('auto_layout'):
        from .autopilot import inspect_bar_card
        visual=inspect_bar_card(image,config.get('post_url'))
        geometry=visual['geometry']
    else:
        geometry=extract(image,kind=config.get('kind','auto'),roi=config.get('roi'),color=config.get('color'),samples=config.get('samples',101))
    trace.append(dict(step='extract',series=len(geometry['series']),method=geometry['method']))
    ocr=visual['ocr'] if visual else read_text(image) if config.get('ocr',True) else {'available':False,'text':'','tokens':[]}
    post_source=config.get('post_url') or config.get('source') or ''
    leads=claims_from_text(config.get('post_text',''),post_source or 'provided post text',config.get('entity'))
    leads+=claims_from_text(ocr['text'],'OCR of input image',config.get('entity'))
    for doc in config.get('evidence_documents',[]):
        leads+=claims_from_text(doc.get('text',doc.get('text_excerpt','')),doc.get('url',doc.get('source','')),doc.get('entity'))
    documents=list(config.get('evidence_documents',[]))
    if config.get('post_text'):
        documents.append(dict(text=config['post_text'],url=post_source,created_at=config.get('post_date')))
    binding=bind_documents(documents,geometry,config['chart_context'],pixel_error=config.get('pixel_error',2.5)) if config.get('chart_context') else dict(claims=[],decisions=[],anchors=[])
    visual_anchors=visual['binding']['anchors'] if visual else []
    all_anchors=list(config.get('anchors',[]))+binding['anchors']+visual_anchors
    trace.append(dict(step='gather_evidence',candidate_claims=len(leads),accepted_anchors=len(all_anchors),
                      automatically_bound=len(binding['anchors'])+len(visual_anchors),rejected_claims=sum(d['status']=='rejected' for d in binding['decisions']),
                      supplied_period_totals=len(config.get('totals',[]))))
    extracted_ids={s['id'] for s in geometry['series']}
    for total in config.get('totals',[]):
        if 'series' not in total:raise ValueError('Every total must name its series')
        if total['series'] not in extracted_ids:raise ValueError('Total references an unknown series')
    results=[]
    for s in geometry['series']:
        anchors=[]
        for raw in all_anchors:
            if raw.get('series',s['id'])!=s['id']:continue
            a=dict(raw)
            if 'point_index' in a:
                if len(geometry['series']) > 1 and 'series' not in a:
                    raise ValueError('A point_index anchor must name its series when multiple series are detected')
                raw_index=a.pop('point_index')
                if isinstance(raw_index,bool) or not (isinstance(raw_index,int) or
                        isinstance(raw_index,float) and math.isfinite(raw_index) and raw_index.is_integer()):
                    raise ValueError('point_index must be an integer')
                idx=int(raw_index)
                if not -len(s['points'])<=idx<len(s['points']):raise ValueError('Anchor point_index outside extracted series')
                a['pixel']=s['coordinates'][idx]
            anchors.append(a)
        totals=[t for t in config.get('totals',[]) if t.get('series')==s['id']]
        if totals:
            if config.get('scale')!='linear':raise ValueError('Period-total calibration needs an explicitly linear scale')
            if s['kind'].startswith('stacked'):raise ValueError('Period totals for stacked boundaries need additional semantic review')
            cal=calibrate_totals(s['coordinates'],anchors,totals,baseline=config.get('baseline'),
                                 value_domain=config.get('value_domain'),pixel_error=config.get('pixel_error',2.5))
        else:
            cal=calibrate(s['coordinates'],anchors,scale=config.get('scale','unknown'),
                          baseline=config.get('baseline'),pixel_error=config.get('pixel_error',2.5))
        result=dict(series=s['id'],**cal)
        if s['kind'].startswith('stacked') and cal['status']=='calibrated':
            # Boundary values are cumulative. Segment values need both boundaries.
            result['value_semantics']='Cumulative upper boundary; not individual segment values.'
            if cal['scale']=='linear':
                a=cal['coefficients']['a']
                result['segment_values']=[a*p['extent'] for p in s['points']]
                result['segment_note']='Segment estimates use visible thickness; raster occlusion and boundary stroke width affect thin bands.'
        candidates=config.get('reference_series',[])
        result['reference_matches']=match_reference(s['shape_normalized'],candidates) if candidates else []
        results.append(result)
    trace.append(dict(step='calibrate',outcomes=[r['status'] for r in results]))
    needs=[]
    if geometry.get('quality_issues'):needs.append('Review the incomplete trace against the supplied plot ROI before accepting calibration.')
    if not geometry['series']:needs.append('Provide plot ROI, chart kind and foreground color, or manually digitized coordinates.')
    if any(r['status'] in ('unidentifiable','ambiguous_scale','bounded_only') for r in results):
        needs.append('Find absolute values for the same metric, currency and period, and map them to specific marks/ticks.')
    if any(r['status']=='inconsistent' for r in results):needs.append('Review conflicting anchors, axis scale, units and time alignment.')
    trace.append(dict(step='verify',next_actions=needs,stop='Evidence exhausted; no fabricated absolute values.'))
    result=dict(image=str(image),config=config,geometry=geometry,ocr=ocr,evidence_leads=leads,evidence_binding=binding,recovery=results,trace=trace,
                status='calibrated' if results and all(r['status']=='calibrated' for r in results) and not geometry.get('quality_issues') else 'needs_evidence_or_review')
    if visual:result['visual_evidence']=dict(layout=visual['layout'],binding=visual['binding'])
    (out/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False), encoding="utf-8");overlay(image,geometry,out/'overlay.png')
    with (out/'data.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['series','point','pixel_x','pixel_y','shape_normalized','value','lower','upper','status'])
        for s,r in zip(geometry['series'],results):
            for i,p in enumerate(s['points']):
                val=lambda key:r[key][i] if r.get(key) is not None else ''
                w.writerow([s['id'],i,p['x'],p['y'],s['shape_normalized'][i],val('values'),val('lower'),val('upper'),r['status']])
    return result
