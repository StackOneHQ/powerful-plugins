"""Fit a shared daily knot grid to observed strokes without monetary values."""
import numpy as np
from scipy.optimize import minimize
from scipy.linalg import solveh_banded


def fit_shared_grid(candidates,left,right,count):
    """Separate stroke extent from knot location within a fixed raster allowance.

    Every tested count receives the same endpoint freedom and least-squares
    knot fit. A small fit residual alone cannot establish a daily sample count.
    """
    base=dict(status='needs_review',selection_uses='observed_pixels_only',
              max_endpoint_shift=2.5,excluded_endpoint_margin=5.5)
    if len(candidates)!=2 or count<8 or right-left<8*(count-1):
        return dict(base,reason='Need two resolved curves and at least eight daily positions.')
    observations=[]
    for curve in candidates:
        x=np.asarray(curve['x'],float);y=np.asarray(curve['y'],float)
        if len(x)!=len(y) or len(x)<count*4 or not np.isfinite(x).all() or not np.isfinite(y).all():
            return dict(base,reason='Insufficient finite observed pixels.')
        if np.any(np.diff(x)<=0) or np.max(np.diff(x))>15:
            return dict(base,reason='Observed trace has unsupported gaps or unordered positions.')
        # Fix the scored pixel set across all endpoint/count trials. Trimming
        # line caps must not let an optimizer discard a different set of errors.
        keep=(x>=left+5.5)&(x<=right-5.5)
        observations.append((x[keep],y[keep]))

    def fit_at(k,delta):
        lo=left+delta[0];hi=right+delta[1];nodes=[];checks=[]
        for x,y in observations:
            position=(x-lo)/(hi-lo)*(k-1)
            index=np.clip(np.floor(position).astype(int),0,k-2);fraction=position-index
            # Each observation touches two adjacent knots. The exact normal
            # equations are tridiagonal; avoid repeatedly factoring a dense
            # image-column matrix during the endpoint search.
            first=1-fraction
            diagonal=np.bincount(index,weights=first*first,minlength=k)+np.bincount(index+1,weights=fraction*fraction,minlength=k)
            off_diagonal=np.bincount(index,weights=first*fraction,minlength=k)
            target=np.bincount(index,weights=first*y,minlength=k)+np.bincount(index+1,weights=fraction*y,minlength=k)
            band=np.zeros((2,k));band[1]=diagonal;band[0,1:]=off_diagonal[:-1]
            try:values=solveh_banded(band,target)
            except np.linalg.LinAlgError:return None
            error=abs(first*values[index]+fraction*values[index+1]-y)
            nodes.append(values.tolist())
            checks.append(dict(mean_error=float(error.mean()),p95_error=float(np.quantile(error,.95)),
                               fitted_observed_columns=len(x)))
        return dict(xs=np.linspace(lo,hi,k).tolist(),ys=nodes,checks=checks,
                    endpoint_offsets=[float(v) for v in delta])

    trials=[]
    for k in (count,count-2,count-1,count+1,count+2):
        def objective(delta):
            fit=fit_at(k,delta)
            return sum(c['mean_error'] for c in fit['checks']) if fit else 1e12
        optimized=minimize(objective,[0.,0.],method='Powell',bounds=[(-2.5,2.5),(-2.5,2.5)],
                           options={'xtol':.03,'ftol':1e-6,'maxiter':30})
        result=fit_at(k,optimized.x)
        if result is None or not optimized.success:
            return dict(base,reason='Daily grid optimization is unsupported or did not converge.')
        trials.append(dict(result,count=k))
    main=trials[0];checks=main['checks']
    for i,check in enumerate(checks):
        check['neighbor_count_errors']=[t['checks'][i]['mean_error'] for t in trials[1:]]
    supported=all(c['mean_error']<=1.8 and c['p95_error']<=4.5 and
                  min(c['neighbor_count_errors'])>=max(2.,c['mean_error']*2) for c in checks)
    return dict(base,**main,status='supported' if supported else 'needs_review',
                reason=None if supported else 'The visible corners do not uniquely support the proposed daily spacing.',
                alternative_grids=[dict(count=t['count'],endpoint_offsets=t['endpoint_offsets'],checks=t['checks']) for t in trials[1:]])
