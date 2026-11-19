"""Affine calibration from point facts, period totals and explicit value domains.

A period total is a sum constraint, never an endpoint. Underconstrained but
bounded solutions expose intervals only; no arbitrary representative curve.
"""
from __future__ import annotations
import math
import numpy as np
from scipy.optimize import linprog
from .calibrate import _least_squares_axis


def calibrate_totals(points, anchors=(), totals=(), *, baseline=None, value_domain=None, pixel_error=2.5):
    points=np.asarray(points,dtype=float)
    if not len(points) or not np.isfinite(points).all():raise ValueError('Need finite observation coordinates')
    if not math.isfinite(pixel_error) or pixel_error<0:raise ValueError('Invalid pixel_error')
    q=-points;rows=[];rhs=[];equalities=[];targets=[];used=[];ignored=[];assumptions=['The axis is linear.']

    def add(coeff, low, high, error):
        if not all(math.isfinite(v) for v in (*coeff,low,high,error)) or low>high or error<0:
            raise ValueError('Constraint bounds and coordinates must be finite and ordered')
        rows.extend([[coeff[0]-error,coeff[1]],[-coeff[0]-error,-coeff[1]]]);rhs.extend([high,-low])
        equalities.append(coeff);targets.append((low+high)/2)

    def accepted(item):
        if not item.get('source') or not item.get('matched'):
            ignored.append(dict(constraint=item,reason='Source and correspondence are required'));return False
        return True

    observations=list(anchors)
    if baseline is not None:
        if not baseline.get('source') or baseline.get('value',0)!=0:raise ValueError('Baseline requires zero value and provenance')
        observations.append(dict(pixel=baseline['pixel'],value=0,matched=True,source=baseline['source'],pixel_error=baseline.get('pixel_error',pixel_error)))
        if not baseline.get('verified'):assumptions.append('The supplied baseline represents zero.')
    for item in observations:
        if not accepted(item):continue
        low=item.get('low',item.get('value'));high=item.get('high',item.get('value'))
        if low is None or high is None:raise ValueError('Point constraint needs value or low/high')
        add([-float(item['pixel']),1.],float(low),float(high),float(item.get('pixel_error',pixel_error)))
        used.append(dict(item,kind='point',low=low,high=high))
        assumptions.extend(item.get('assumptions',[]))
    for item in totals:
        if not accepted(item):continue
        # Summing a 101-sample interpolated curve instead of the actual 28 daily
        # observations is a semantic error: require a declared count and indices.
        if item.get('kind','sum')!='sum':raise ValueError('Only sum aggregates are supported')
        indices=item.get('point_indices')
        if not isinstance(indices,list) or not indices or len(set(indices))!=len(indices):raise ValueError('Sum needs unique point_indices')
        if any(type(i) is not int or not 0<=i<len(points) for i in indices):raise ValueError('Sum point index outside observations')
        if item.get('observation_count')!=len(indices):raise ValueError('Sum needs the actual observation_count')
        low=item.get('low',item.get('value'));high=item.get('high',item.get('value'))
        if low is None or high is None:raise ValueError('Sum needs value or low/high')
        add([float(q[indices].sum()),float(len(indices))],float(low),float(high),len(indices)*float(item.get('pixel_error',pixel_error)))
        used.append(dict(item,kind='sum',low=low,high=high))
        assumptions.extend(item.get('assumptions',[]))
    if value_domain is not None:
        if not value_domain.get('source'):raise ValueError('Value domain needs provenance or an explicit assumption')
        low=value_domain.get('low');high=value_domain.get('high')
        if low is None and high is None:raise ValueError('Value domain needs a lower or upper bound')
        if any(v is not None and not math.isfinite(v) for v in (low,high)) or (low is not None and high is not None and low>high):raise ValueError('Invalid value domain')
        for value in q:
            if low is not None:rows.append([-value-pixel_error,-1]);rhs.append(-low)
            if high is not None:rows.append([value-pixel_error,1]);rhs.append(high)
        assumptions.append(f"Values are in the supplied domain: {low} to {high}; source: {value_domain['source']}")
    result=dict(anchors_used=used,anchors_ignored=ignored,assumptions=assumptions,pixel_error=pixel_error,scale='linear',values=None,
                bound_meaning='Feasible bounds conditional on source truth, observation count, linear scale, stated pixel error and supplied value domain; not confidence intervals.')
    if not rows:return dict(result,status='unidentifiable',reason='No accepted absolute constraints.')
    options=dict(A_ub=np.asarray(rows),b_ub=np.asarray(rhs),bounds=[(1e-12,None),(None,None)],method='highs')
    feasible=linprog([0,0],**options)
    if not feasible.success:return dict(result,status='inconsistent',reason='Point, total or domain constraints conflict.')
    lower=[];upper=[]
    for value in q:
        lo=linprog([value-pixel_error,1],**options);hi=linprog([-value-pixel_error,-1],**options)
        domain_low=(value_domain or {}).get('low');domain_high=(value_domain or {}).get('high')
        if not lo.success and not (lo.status==3 and domain_low is not None):
            return dict(result,status='unidentifiable',reason='The supplied totals do not bound the entire axis.')
        if not hi.success and not (hi.status==3 and domain_high is not None):
            return dict(result,status='unidentifiable',reason='The supplied totals do not bound the entire axis.')
        low=float(lo.fun) if lo.success else domain_low
        high=float(-hi.fun) if hi.success else domain_high
        if value_domain:
            if value_domain.get('low') is not None:low=max(low,value_domain['low'])
            if value_domain.get('high') is not None:high=min(high,value_domain['high'])
        lower.append(low);upper.append(high)
    result.update(lower=lower,upper=upper)
    rank=np.linalg.matrix_rank(np.asarray(equalities)) if equalities else 0
    if rank<2:return dict(result,status='bounded_only',reason='Absolute intervals are bounded, but multiple affine scales remain. No single value estimate is justified.')
    # Keep the uncertainty polygon for bounds. A representative at nominal
    # pixel centers must itself obey the domain, without clipping individual
    # values away from the reported affine coefficients.
    fit_rows=list(rows);fit_rhs=list(rhs);fit_feasible=feasible
    if value_domain:
        for value in q:
            if value_domain.get('low') is not None:fit_rows.append([-value,-1]);fit_rhs.append(-value_domain['low'])
            if value_domain.get('high') is not None:fit_rows.append([value,1]);fit_rhs.append(value_domain['high'])
        fit_feasible=linprog([0,0],A_ub=fit_rows,b_ub=fit_rhs,bounds=options['bounds'],method='highs')
        if not fit_feasible.success:
            return dict(result,status='bounded_only',reason='Pixel-uncertainty bounds are feasible, but no nominal affine representative satisfies the value domain.')
    design=np.asarray(equalities);counts=design[:,1]
    # Dividing a sum equation by its count gives a mean coordinate; weighting
    # its residual by that count retains the objective in original sum units.
    coef,estimator=_least_squares_axis(design[:,0]/counts,np.asarray(targets)/counts,
        fit_rows,fit_rhs,fit_feasible.x,weights=counts)
    values=(coef[0]*q+coef[1]).tolist()
    estimator['constraint_squared_loss']=estimator.pop('transformed_anchor_squared_loss')
    return dict(result,status='calibrated',values=values,coefficients=dict(a=float(coef[0]),b=float(coef[1])),
        point_estimator=dict(estimator,objective_space='point_and_total_values',
            note='Constrained least-squares representative of the supplied point and sum observations; not independent evidence.'))
