"""Test conditional calendar-to-curve associations without asserting identity.

Numerical agreement can support a correspondence hypothesis. It cannot prove
that two panels share a metric, entity, dates or truthful underlying data.
"""
import copy
import numpy as np
from .calibrate import calibrate


def date_label_audit(geometry,ticks,days):
    """Compare label centers with equal daily spacing; centers are hypotheses."""
    note='Date-label centers are tested as tick positions. Without tick marks, inset or decorative labels can violate this interpretation.'
    if len(geometry.get('series',[]))!=1:return dict(status='unavailable',note=note)
    points=geometry['series'][0]['points'];first,last=points[0]['x'],points[-1]['x']
    unique={t['day']:t for t in ticks};ordered=sorted(unique.values(),key=lambda t:t['day'])
    if len(ordered)<3 or len({t['x'] for t in ordered})<3:return dict(status='insufficient_labels',note=note,labels=ordered)
    xs=np.array([t['x'] for t in ordered]);ds=np.array([t['day'] for t in ordered],float)
    slope,offset=np.polyfit(ds-1,xs,1)
    if slope<=0:return dict(status='nonmonotonic_labels',note=note,labels=ordered)
    errors=[]
    for t in ordered:
        proposed=first+(t['day']-1)/(days-1)*(last-first)
        tolerance=max(4.,t['box'][2]/2+3.,(last-first)*.015)
        errors.append(dict(day=t['day'],label_x=t['x'],full_month_x=float(proposed),
                           difference=float(t['x']-proposed),tolerance=float(tolerance)))
    return dict(status='compatible' if all(abs(r['difference'])<=r['tolerance'] for r in errors) else 'label_centers_disagree',
                labels=ordered,full_month_comparison=errors,pixels_per_day=float(slope),first_day_x=float(offset),
                inferred_day_at_curve_start=float(1+(first-offset)/slope),inferred_day_at_curve_end=float(1+(last-offset)/slope),
                linear_label_residual=float(np.max(np.abs(xs-(slope*(ds-1)+offset)))),note=note)


def _turns(values):
    values=np.asarray(values,float);diff=np.diff(values);sign=np.sign(diff[np.abs(diff)>np.ptp(values)*.025])
    return int(np.sum(sign[:-1]!=sign[1:]))


def _anchors(observations,mapping):
    anchors=[]
    for obs in observations:
        day=int(obs['date'][-2:]);coordinate=mapping(day)
        if coordinate is None:continue
        pixel,extra=coordinate
        anchors.append(dict(pixel=pixel,low=obs['low'],high=obs['high'],pixel_error=2.5+extra,
                            source=obs['source'],matched=True,correspondence_basis='conditional_hypothesis',source_observation_date=obs['date'],label_box=obs['box']))
    return anchors


def propose_calendar(calendar_result):
    """Use an explicit hypothesis, fit/check split and all-evidence final fit.

    No private truth or manual monetary anchors enter this function. The
    result is always a hypothesis, even when every numerical check succeeds.
    """
    result=calendar_result;calendar=result.get('calendar',{});geometry=result.get('geometry',{})
    correspondence=result.get('correspondence',{});rejected=[]
    audit=dict(status='unavailable');hypotheses=[]
    summary=dict(status='no_supported_hypothesis',hypotheses=hypotheses,rejections=rejected,
                 numerical_agreement_is_not_identity=True,date_assignment='unassigned')
    if calendar.get('status')!='read':rejected.append('Calendar observations or layout are unresolved.')
    if len(geometry.get('series',[]))!=1 or geometry.get('quality_issues'):rejected.append('Need one complete curve before testing a calendar association.')
    if rejected:return summary
    observations=sorted(calendar.get('observations',[]),key=lambda o:o['date']);layout=calendar['layout'];days=layout['days']
    series=geometry['series'][0];points=series['points'];ys=series['coordinates'];errors=series.get('x_location_y_error',[0.]*len(ys))
    audit=date_label_audit(geometry,correspondence.get('date_ticks',[]),days);summary['date_label_audit']=audit
    heading=correspondence.get('curve_heading');calendar_heading=correspondence.get('calendar_heading')
    if not heading or heading.get('metric')!='revenue' or heading.get('aggregation') not in (None,'daily'):
        rejected.append('The selected curve needs a local revenue heading compatible with daily values.')
    if calendar_heading and (calendar_heading.get('metric')!='revenue' or calendar_heading.get('aggregation') not in (None,'daily')):
        rejected.append('The calendar heading contradicts a daily-revenue association.')
    if any('contradict' in reason for reason in correspondence.get('reasons',[])):
        rejected.append('Visible metric or period evidence contradicts the proposed association.')
    if len(points)!=days:rejected.append('The proposed full-month association needs one extracted location per calendar day.')
    if len(observations)<14:rejected.append('Need at least fourteen readable calendar amounts for fit and unused-cell checks.')
    if len({o['currency'] for o in observations})!=1:rejected.append('Calendar observations have mixed units.')
    if _turns([o['value'] for o in observations])<4:
        rejected.append('A smooth or monotone sequence is too weak a pattern to propose identity from numerical agreement.')
    if rejected:return summary
    # Deterministic split fixed before calibration. Checking cells are not used
    # to select coefficients. They are observations, not independent sources.
    checking=[o for o in observations if (int(o['date'][-2:])-1)%3==1]
    fitting=[o for o in observations if (int(o['date'][-2:])-1)%3!=1]
    if len(checking)<5 or len(fitting)<8:
        rejected.append('Need at least eight fit cells and five unused checking cells.');return summary
    mappings=[('calendar_order_over_curve_span',lambda d:(ys[d-1],errors[d-1]))]
    if audit.get('pixels_per_day') and audit['linear_label_residual']<=4:
        xs=np.array([p['x'] for p in points]);py=np.array(ys)
        def date_mapping(day):
            x=audit['first_day_x']+(day-1)*audit['pixels_per_day']
            if not xs[0]<=x<=xs[-1]:return None
            y=float(np.interp(x,xs,py));err=max(abs(float(np.interp(x+dx,xs,py))-y) for dx in (-1.,1.))
            return y,err
        mappings.append(('date_label_centers_as_exact_ticks',date_mapping))
    for name,mapping in mappings:
        hypothesis=dict(id=name,status='rejected',fit_observations=len(fitting),check_observations=len(checking),reasons=[],
                        source='calendar observations and curve geometry in the same image',date_assignment='unassigned')
        hypotheses.append(hypothesis)
        train=_anchors(fitting,mapping);test=_anchors(checking,mapping)
        if len(train)!=len(fitting) or len(test)!=len(checking):
            hypothesis['reasons'].append('Some calendar dates lie outside the curve under this mapping.');continue
        fit=calibrate([a['pixel'] for a in test],train,scale='unknown',pixel_error=2.5+max(errors))
        hypothesis['fit_status']=fit['status']
        if fit['status']!='calibrated':
            hypothesis['reasons'].append(fit.get('reason','Numerical constraints do not select one scale.'));continue
        actual=np.array([(a['low']+a['high'])/2 for a in test]);pred=np.array(fit['values'])
        span=float(np.ptp([o['value'] for o in observations]));nmae=float(np.abs(actual-pred).mean()/span) if span else float('inf')
        coverage=float(np.mean((np.array(fit['lower'])<=actual)&(actual<=np.array(fit['upper']))))
        hypothesis['check']=dict(nmae=nmae,interval_coverage=coverage,scale=fit['scale'],
                                 rows=[dict(source_date=o['date'],observed=float(a),predicted=float(p)) for o,a,p in zip(checking,actual,pred)],
                                 meaning='Same-image cells excluded from coefficient fitting; not independent factual corroboration or held-out external ground truth.')
        if nmae>.02 or coverage<.9:
            hypothesis['reasons'].append('Unused checking cells do not support this mapping within the fixed error/coverage thresholds.');continue
        anchors=_anchors(observations,mapping)
        final=calibrate(ys,anchors,scale='unknown',pixel_error=2.5+max(errors))
        if final['status']!='calibrated':
            hypothesis['reasons'].append('Not all accepted observations admit one bounded calibration.');continue
        alignment_assumption=('Calendar dates in order correspond to equally spaced locations across the complete curve span.' if name=='calendar_order_over_curve_span'
                              else 'Printed date-label centers denote exact positions on a linear calendar-day X axis.')
        assumptions=['The calendar amounts and selected curve describe the same daily revenue metric, entity and currency.',alignment_assumption,
                     'Numerical agreement supports this association but does not prove panel identity or truthful source data.',
                     'Dates are not assigned to the output curve; calendar dates remain source-observation metadata.']+calendar.get('assumptions',[])
        if audit.get('status')=='label_centers_disagree':
            assumptions.append('Printed date-label centers disagree with full-month spacing; the positional hypothesis treats those labels as inset or decorative, not exact tick coordinates.')
        final['assumptions']+=assumptions
        hypothesis.update(status='supported_conditional_hypothesis',recovery=dict(series=series['id'],**final),assumptions=list(dict.fromkeys(assumptions)))
        # Calendars have observed dates; they are not promoted to chart dates.
        hypothesis['proposed_source_dates']=[f"{layout['year']:04d}-{layout['month']:02d}-{i+1:02d}" for i in range(days)] if name=='calendar_order_over_curve_span' else None
    supported=[h for h in hypotheses if h['status']=='supported_conditional_hypothesis']
    if len(supported)==1:
        summary.update(status='one_supported_conditional_hypothesis',selected=supported[0]['id'])
    elif len(supported)>1:
        # Equivalent parameterizations do not add evidence. Retain both and
        # require numerical agreement before exposing a common candidate.
        values=[np.array(h['recovery']['values']) for h in supported]
        if all(np.max(abs(v-values[0]))<=max(1e-6,np.ptp(values[0])*.005) for v in values[1:]):
            summary.update(status='equivalent_supported_hypotheses',selected=supported[0]['id'])
        else:summary['status']='competing_conditional_hypotheses'
    return summary


def candidate_result(calendar_result,proposal):
    """Keep conditional values distinct from strict correspondence results."""
    if not proposal.get('selected'):return None
    hypothesis=next(h for h in proposal['hypotheses'] if h['id']==proposal['selected'])
    result=copy.deepcopy(calendar_result);result['status']='conditional_calibration'
    result['recovery']=[dict(hypothesis['recovery'],status='conditional_calibration')]
    result['correspondence']=dict(status='inferred_not_verified',reasons=calendar_result['correspondence']['reasons'],
                                  assumptions=hypothesis['assumptions'],date_assignment='unassigned',date_label_audit=proposal.get('date_label_audit'))
    result['hypothesis_evaluation']=proposal
    result['trace'].append(dict(step='test_correspondence_hypotheses',status=proposal['status'],selected=proposal['selected'],
                               warning='Conditional inference; source identity and plot dates remain unverified.'))
    return result
