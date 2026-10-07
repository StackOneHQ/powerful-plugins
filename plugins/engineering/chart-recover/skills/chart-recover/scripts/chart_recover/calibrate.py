"""Identify an axis only when the supplied observations constrain it.

A screen coordinate p maps to v = a*(-p)+b (linear) or
log10(v) = a*(-p)+b (log), a>0. Interval linear programs propagate
pixel and anchor rounding bounds. These are conditional bounds, not CIs.
"""
from __future__ import annotations
import math
import numpy as np
from scipy.optimize import linprog


def _least_squares_axis(q, target, rows, rhs, feasible):
    """Choose an anchor-midpoint least-squares axis inside the feasible polygon.

    There are only two parameters. If ordinary least squares is infeasible,
    minimize the quadratic on each boundary line, restricted to the interval
    allowed by every other inequality. A convex quadratic's constrained minimum
    is either its unconstrained minimum or on one of these boundary segments.
    Normalization limits cancellation when units or pixel origins are large.
    This selects a representative axis; it does not tighten the feasible bounds.
    """
    q=np.asarray(q,float);target=np.asarray(target,float)
    raw_a=np.asarray(rows,float);raw_b=np.asarray(rhs,float)
    ordinary=np.polyfit(q,target,1)
    if ordinary[0]>=1e-12 and np.all(raw_a@ordinary<=raw_b+1e-7):
        return ordinary,dict(method='ordinary_least_squares',
                             transformed_anchor_squared_loss=float(np.sum((ordinary[0]*q+ordinary[1]-target)**2)))
    qc=float(q.mean());qs=float(q.std());yc=float(target.mean());ys=max(float(np.ptp(target)),1.)
    transform=np.array([[ys/qs,0.],[-ys*qc/qs,ys]])
    offset=np.array([0.,yc])
    a=np.vstack((raw_a@transform/ys,[-1.,0.]))
    b=np.append((raw_b-raw_a@offset)/ys,-1e-12*qs/ys)
    x=np.column_stack(((q-qc)/qs,np.ones(len(q))));y=(target-yc)/ys
    initial=np.array([feasible[0]*qs/ys,(feasible[0]*qc+feasible[1]-yc)/ys])
    best=initial;loss=float(np.sum((x@best-y)**2));boundary_candidates=0
    for normal,limit in zip(a,b):
        norm=float(np.linalg.norm(normal))
        origin=normal*(limit/(norm*norm));direction=np.array([-normal[1],normal[0]])/norm
        slopes=a@direction;slack=b-a@origin;parallel=np.abs(slopes)<1e-12
        if np.any(slack[parallel]<-1e-10):continue
        positive=slopes>1e-12;negative=slopes<-1e-12
        lower=float(np.max(slack[negative]/slopes[negative])) if negative.any() else -np.inf
        upper=float(np.min(slack[positive]/slopes[positive])) if positive.any() else np.inf
        if lower>upper+1e-10:continue
        if lower>upper:lower=upper=(lower+upper)/2
        xd=x@direction
        optimum=float(xd@(y-x@origin)/(xd@xd))
        candidate=origin+np.clip(optimum,lower,upper)*direction
        if np.any(a@candidate>b+1e-9):continue
        boundary_candidates+=1;candidate_loss=float(np.sum((x@candidate-y)**2))
        if candidate_loss<loss:best=candidate;loss=candidate_loss
    coef=transform@best+offset
    return coef,dict(method='constrained_least_squares' if boundary_candidates else 'feasible_point_numerical_fallback',
                     boundary_candidates=boundary_candidates,
                     transformed_anchor_squared_loss=float(np.sum((coef[0]*q+coef[1]-target)**2)))


def _model(points, anchors, scale, pixel_error):
    if scale == 'log' and any(a['low'] <= 0 for a in anchors):
        return {'scale': scale, 'status': 'inconsistent', 'reason': 'Log anchors must be positive.'}
    transform = math.log10 if scale == 'log' else float
    rows, rhs = [], []
    for anchor in anchors:
        q, e = -anchor['pixel'], anchor.get('pixel_error', pixel_error)
        lo, hi = transform(anchor['low']), transform(anchor['high'])
        rows.extend([[q-e, 1], [-q-e, -1]])
        rhs.extend([hi, -lo])
    opts = dict(A_ub=rows, b_ub=rhs, bounds=[(1e-12, None), (None, None)], method='highs')
    feasible = linprog([0, 0], **opts)
    if not feasible.success:
        return {'scale': scale, 'status': 'inconsistent', 'reason': 'Anchors conflict with one increasing axis within their stated bounds.'}
    values, lows, highs = [], [], []
    coef,estimator = _least_squares_axis([-a['pixel'] for a in anchors],
                      [(transform(a['low'])+transform(a['high']))/2 for a in anchors], rows, rhs, feasible.x)
    for p in points:
        q = -float(p)
        lower = linprog([q-pixel_error, 1], **opts)
        upper = linprog([-q-pixel_error, -1], **opts)
        if not lower.success or not upper.success:
            return {'scale': scale, 'status': 'unidentifiable', 'reason': 'Calibration remains unbounded.'}
        lo, hi, val = float(lower.fun), float(-upper.fun), float(coef @ [q, 1])
        if scale == 'log':
            if max(lo, hi, val) > 300:
                return {'scale': scale, 'status': 'unidentifiable', 'reason': 'Log extrapolation exceeds numerical limits.'}
            lo, hi, val = 10**lo, 10**hi, 10**val
        lows.append(lo); highs.append(hi); values.append(min(max(val, lo), hi))
    return {'scale': scale, 'status': 'calibrated', 'values': values, 'lower': lows, 'upper': highs,
            'coefficients': {'a': float(coef[0]), 'b': float(coef[1])},
            'point_estimator': dict(estimator,objective_space='log10_value' if scale=='log' else 'value',
                                    note='Representative fit to observed anchor midpoints; not a statistical expectation or an additional source of evidence.'),
            'bound_meaning': 'Feasible bounds conditional on scale, anchor truth, correspondence, and stated pixel error; not statistical confidence intervals.'}


def calibrate(points, anchors=(), *, scale='unknown', baseline=None, pixel_error=1.5):
    """baseline is {'pixel': ..., 'value': 0, 'source': ..., 'verified': bool}.

    Points are vertical screen positions. For horizontal bars use negative x.
    A visible bottom boundary is NOT evidence of a zero baseline.
    """
    if scale not in ('linear', 'log', 'unknown'):
        raise ValueError('scale must be linear, log, or unknown')
    if not math.isfinite(pixel_error) or pixel_error < 0:
        raise ValueError('pixel_error must be nonnegative and finite')
    points = list(map(float, points))
    if not all(math.isfinite(p) for p in points):
        raise ValueError('Nonfinite point coordinate')
    usable, ignored, assumptions = [], [], []
    for item in anchors:
        a = dict(item)
        if not a.get('source'):
            ignored.append({'anchor': a, 'reason': 'Missing source/provenance'}); continue
        if not a.get('matched', False):
            ignored.append({'anchor': a, 'reason': 'Correspondence to this chart/metric/time has not been confirmed'}); continue
        if 'value' in a:
            a.setdefault('low', a['value']); a.setdefault('high', a['value'])
        if not all(k in a and math.isfinite(a[k]) for k in ('pixel', 'low', 'high')):
            raise ValueError('Anchor needs finite pixel and value or low/high')
        if a['low'] > a['high'] or a.get('pixel_error', pixel_error) < 0:
            raise ValueError('Invalid anchor bounds')
        usable.append(a)
        assumptions.extend(a.get('assumptions',[]))
    if baseline is not None:
        if not baseline.get('source'):
            raise ValueError('Baseline needs provenance or an explicit assumption')
        if scale != 'linear':
            raise ValueError('A zero baseline is usable only with an explicitly linear scale')
        if baseline.get('value', 0) != 0:
            raise ValueError('Use an ordinary anchor for a nonzero baseline')
        usable.append(dict(pixel=float(baseline['pixel']), low=0., high=0.,
                           pixel_error=baseline.get('pixel_error', pixel_error), source=baseline['source'], matched=True))
        if not baseline.get('verified', False):
            assumptions.append('The specified baseline represents zero.')
    if scale != 'unknown':
        assumptions.append(f'The axis uses the supplied {scale} scale.')
    result = {'anchors_used': usable, 'anchors_ignored': ignored, 'assumptions': assumptions,
              'pixel_error': pixel_error, 'values': None}
    if len(usable) < 2 or np.ptp([a['pixel'] for a in usable]) <= 2*pixel_error:
        return dict(result, status='unidentifiable', reason='Need two separated absolute anchors, or one absolute anchor plus an explicit linear zero baseline.')
    candidates = [_model(points, usable, s, pixel_error) for s in (('linear', 'log') if scale == 'unknown' else (scale,))]
    valid = [c for c in candidates if c['status'] == 'calibrated']
    if not valid:
        status = 'unidentifiable' if any(c['status'] == 'unidentifiable' for c in candidates) else 'inconsistent'
        return dict(result, status=status, candidates=candidates, reason='No bounded calibration satisfies all evidence.')
    if len(valid) > 1:
        return dict(result, status='ambiguous_scale', candidates=candidates,
                    reason='Both linear and log axes fit. Supply scale evidence or additional anchors.')
    return dict(result, **valid[0])
