import importlib.util
import numpy as np


def curves():
    rng=np.random.default_rng(19);n=28;knots=np.linspace(40,1000,n)
    values=[rng.uniform(130,570,n),rng.uniform(220,610,n)]
    x=np.arange(39,1002)
    observed=[dict(x=x.tolist(),y=(np.interp(x,knots,y)+rng.uniform(-.35,.35,len(x))).tolist()) for y in values]
    return observed,knots,values


def fit(candidates,n=28):
    assert importlib.util.find_spec('chart_recover.curve_grid') is not None,'Pixel-only grid fitter is missing'
    from chart_recover.curve_grid import fit_shared_grid
    return fit_shared_grid(candidates,39,1001,n)


def test_stroke_extent_does_not_set_the_daily_grid():
    candidates,knots,truth=curves();result=fit(candidates)
    assert result['status']=='supported',result
    assert np.max(abs(np.array(result['xs'])-knots))<.2
    assert np.max(abs(np.array(result['ys'])-truth))<.5
    assert max(abs(x) for x in result['endpoint_offsets'])<=2.5
    assert result['selection_uses']=='observed_pixels_only'


def test_nearby_wrong_day_count_is_rejected_after_equal_fitting_freedom():
    candidates,_,_=curves()
    result=fit(candidates,n=27)
    assert result['status']=='needs_review'


def test_smooth_trace_does_not_identify_a_unique_daily_count():
    candidates,_,_=curves()
    for i,c in enumerate(candidates):c['y']=(380+140*np.sin(np.asarray(c['x'])/130+i)).tolist()
    assert fit(candidates)['status']=='needs_review'


def test_unobserved_interior_spans_are_refused_before_knot_fitting():
    candidates,_,_=curves()
    c=candidates[0];x=np.array(c['x']);keep=(x<250)|(x>500)
    c['x']=x[keep].tolist();c['y']=np.array(c['y'])[keep].tolist()
    result=fit(candidates)
    assert result['status']=='needs_review'
    assert result['reason']=='Observed trace has unsupported gaps or unordered positions.'
