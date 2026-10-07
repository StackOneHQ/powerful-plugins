"""Frozen image-only conditional inference, with hidden calendar amounts.

This tests recovery under a generated relationship, not proof of identity from
shape or validation that public source data are truthful.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from .render_cache import configure_cache
configure_cache()
from matplotlib import font_manager
from .calendar_benchmark import generate_dashboard
from .calendar_recovery import analyze_calendar
from .hypotheses import propose_calendar,candidate_result


def generate(folder,seed,renderer='pillow',style='light',control=None):
    folder=Path(folder)
    base_control=control if control in ('wrong_metric','wrong_month','no_amounts') else 'missing_metric'
    truth=generate_dashboard(folder,seed,renderer,style,base_control)
    path=folder/'chart.png';im=Image.open(path).convert('RGB');draw=ImageDraw.Draw(im);width,height=im.size
    bg='#181a26' if style=='dark' else '#ffffff';fg='#e1e5ef' if style=='dark' else '#394150'
    draw.rectangle([0,398,width,452],fill=bg)
    # Inset labels are deliberate contradictory positional clues. They do not
    # change the private sequence relationship, and must not become plot dates.
    inset=bool(seed%2)
    if inset:
        import calendar
        font=ImageFont.truetype(font_manager.findfont('DejaVu Sans'),16)
        xs=[p['x'] for p in truth['points']];month=calendar.month_abbr[truth['month']]
        for day in (5,10,15,20,25):
            x=xs[day-1]+(xs[-1]-xs[0])*.075
            draw.text((x,420),f'{month} {day}',font=font,fill=fg,anchor='mm')
    if control in ('unrelated_curve','reversed_curve','two_curves'):
        xs=np.array([p['x'] for p in truth['points']]);ys=np.array([p['y'] for p in truth['points']])
        if control!='two_curves':draw.rectangle([int(xs[0])-5,90,int(xs[-1])+5,394],fill=bg)
        rng=np.random.default_rng(seed+90111)
        replacement=ys[::-1] if control=='reversed_curve' else rng.uniform(120,370,len(xs))
        draw.line(list(zip(xs,replacement)),fill='#13a987' if control=='two_curves' else '#7267ec',width=3)
    im.save(path);truth.update(conditional_context='Generic Revenue headings; shared daily metric and complete-month correspondence are not asserted by headings/endpoints.',
                              inset_date_labels=inset,control=control)
    (folder/'truth.json').write_text(json.dumps(truth,indent=2), encoding="utf-8");return truth


def run(output='artifacts/hypothesis-heldout-v1',seed=80000,per_renderer=20):
    out=Path(output)
    if (out/'protocol.json').exists():raise ValueError('Use a fresh output path; existing frozen evaluations are not overwritten.')
    out.mkdir(parents=True,exist_ok=True);source=Path(__file__).parent
    files=['hypotheses.py','hypothesis_benchmark.py','calendar_benchmark.py','calendar_recovery.py','calendar_vision.py','autopilot.py','layout.py','ocr.py','vision.py','calibrate.py']
    (out/'source').mkdir(exist_ok=True)
    for name in files:(out/'source'/name).write_bytes((source/name).read_bytes())
    protocol=dict(seed=seed,per_renderer=per_renderer,source_hashes={f:hashlib.sha256((source/f).read_bytes()).hexdigest() for f in files},
                  input='Image only. No manual kind, scale, ROI, color, monetary anchors, plot dates or correspondence assumptions. Generic Revenue headings; exact endpoint labels absent. Six calendar amounts absent.',
                  inference='At least 14 readable observations, an irregular sequence, fixed modulo-three fit/check split, <2% checking NMAE, >=90% checking bound coverage, unique all-evidence calibration. Conditional identity only; no plot dates assigned.',
                  scoring='Private truth opened after inference. Complete month count; X alignment <=4px; no false accepted OCR amount; correct axis scale; hidden-amount NMAE <2% of true value range. Strict and conditional statuses remain separate.',
                  limitations='Two curve renderers, one calendar renderer and two fonts. Generated identity is true by construction. Numerical agreement cannot establish identity or source truth on public data; same-image checking cells are not independent sources.')
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2), encoding="utf-8");rows=[]
    for ri,renderer in enumerate(('pillow','matplotlib')):
        for j in range(per_renderer):
            seed_i=seed+ri*1000+j;folder=out/f'{renderer}-{seed_i}'
            generate(folder,seed_i,renderer,['light','dark','highlight','jpeg','small'][j%5])
            strict=analyze_calendar(folder/'chart.png',{},folder/'strict')
            proposal=propose_calendar(strict);candidate=candidate_result(strict,proposal)
            (folder/'hypotheses.json').write_text(json.dumps(proposal,indent=2), encoding="utf-8")
            if candidate:(folder/'conditional-result.json').write_text(json.dumps(candidate,indent=2), encoding="utf-8")
            truth=json.loads((folder/'truth.json').read_text(encoding="utf-8"));values=np.array(truth['values']);keep=truth['hidden_indices']
            row=dict(seed=seed_i,renderer=renderer,style=truth['style'],strict_status=strict['status'],proposal_status=proposal['status'],
                     status='conditional_calibration' if candidate else 'abstained',success=False,observations=len(strict['calendar']['observations']),
                     reasons=proposal['rejections'],date_label_audit=proposal.get('date_label_audit',{}).get('status'))
            if candidate:
                cal=candidate['recovery'][0];pred=np.array(cal['values']);obs=strict['calendar']['observations']
                wrong=[o for o in obs if o['date'][:7]!=f"{truth['year']:04d}-{truth['month']:02d}" or o['value']!=values[int(o['date'][-2:])-1]]
                leak=[o for o in obs if int(o['date'][-2:])-1 in keep]
                dx=max(abs(p['x']-q['x']) for p,q in zip(candidate['geometry']['series'][0]['points'],truth['points']))
                errors=np.abs(pred-values);nmae=float(errors[keep].mean()/np.ptp(values))
                row.update(mae=float(errors[keep].mean()),nmae=nmae,hidden_values=len(keep),wrong_ocr_values=len(wrong),hidden_values_leaked=len(leak),max_x_error=float(dx),
                           conditional_interval_coverage=float(np.mean((np.array(cal['lower'])[keep]<=values[keep])&(values[keep]<=np.array(cal['upper'])[keep]))),
                           inferred_scale=cal['scale'],date_assignment=candidate['correspondence']['date_assignment'],
                           success=len(pred)==truth['days'] and not wrong and not leak and dx<=4 and cal['scale']=='linear' and nmae<.02 and candidate['correspondence']['date_assignment']=='unassigned')
            rows.append(row);(out/'cases.json').write_text(json.dumps(rows,indent=2), encoding="utf-8");print(renderer,seed_i,row['status'],row['success'],flush=True)
    controls=[]
    for j,control in enumerate(('wrong_metric','wrong_month','no_amounts','unrelated_curve','reversed_curve','two_curves')):
        folder=out/f'control-{control}';generate(folder,seed+3000+j,control=control)
        strict=analyze_calendar(folder/'chart.png',{},folder/'strict');proposal=propose_calendar(strict)
        (folder/'hypotheses.json').write_text(json.dumps(proposal,indent=2), encoding="utf-8")
        controls.append(dict(case=control,status=proposal['status'],abstained=not proposal.get('selected'),reasons=proposal['rejections']))
    summary=dict(protocol=protocol,cases=len(rows),passed=sum(r['success'] for r in rows),abstentions=sum(r['status']=='abstained' for r in rows),
                 incorrect_returned_candidates_under_criteria=sum(r['status']=='conditional_calibration' and not r['success'] for r in rows),
                 strict_calibrated=sum(r['strict_status']=='calibrated' for r in rows),controls=controls,rows=rows,failures=[r for r in rows if not r['success']])
    (out/'summary.json').write_text(json.dumps(summary,indent=2), encoding="utf-8");return summary


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--out',default='artifacts/hypothesis-heldout-v1');parser.add_argument('--seed',type=int,default=80000);parser.add_argument('--per-renderer',type=int,default=20)
    args=parser.parse_args();result=run(args.out,args.seed,args.per_renderer);print(json.dumps({k:v for k,v in result.items() if k not in ('protocol','rows','failures')},indent=2))
