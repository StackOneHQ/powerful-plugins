import numpy as np
import pytest
from chart_recover.calibrate import calibrate


def anchor(p,v,**kw):return dict(pixel=p,value=v,source='test:public-fact',matched=True,**kw)


def test_hidden_scale_abstains_even_with_one_anchor():
    assert calibrate([90,50,10])['values'] is None
    assert calibrate([90,50,10],[anchor(10,100)])['status']=='unidentifiable'


def test_single_anchor_and_known_zero_recover():
    r=calibrate([90,50,10],[anchor(10,900)],scale='linear',pixel_error=0,
                baseline={'pixel':100,'source':'test:zero tick','verified':True})
    assert r['status']=='calibrated'
    np.testing.assert_allclose(r['values'],[100,500,900])


def test_unknown_baseline_requires_two_absolute_facts():
    r=calibrate([90,50,10],[anchor(90,1100),anchor(10,1900)],scale='linear',pixel_error=0)
    np.testing.assert_allclose(r['values'],[1100,1500,1900])


def test_two_facts_do_not_distinguish_linear_and_log():
    r=calibrate([100,50,0],[anchor(100,100),anchor(0,1000)],pixel_error=0)
    assert r['status']=='ambiguous_scale' and r['values'] is None
    assert len(r['candidates'])==2
    assert abs(r['candidates'][0]['values'][1]-r['candidates'][1]['values'][1])>200


def test_three_facts_can_select_log():
    r=calibrate([100,50,0],[anchor(100,1),anchor(50,10),anchor(0,100)],pixel_error=.5)
    assert r['status']=='calibrated' and r['scale']=='log'
    np.testing.assert_allclose(r['values'],[1,10,100],rtol=.025)


def test_conflicting_evidence_is_not_silently_dropped():
    r=calibrate([100,50,0],[anchor(100,1),anchor(50,100),anchor(0,10)],scale='linear')
    assert r['status']=='inconsistent'


def test_provenance_and_correspondence_required():
    r=calibrate([100,0],[{'pixel':100,'value':1,'matched':True},dict(anchor(0,100),matched=False)],scale='linear')
    assert r['status']=='unidentifiable' and len(r['anchors_ignored'])==2


def test_interval_bounds_contain_feasible_truth():
    r=calibrate([90,50,10],[dict(anchor(90,100),low=95,high=105),dict(anchor(10,900),low=880,high=920)],scale='linear')
    assert all(lo<=v<=hi for v,lo,hi in zip([100,500,900],r['lower'],r['upper']))
    assert r['upper'][1]>r['lower'][1]


def test_log_zero_and_invalid_bounds_rejected():
    assert calibrate([100,0],[anchor(100,0),anchor(0,100)],scale='log')['status']=='inconsistent'
    with pytest.raises(ValueError):calibrate([100,0],[anchor(100,float('nan'))])
    with pytest.raises(ValueError):calibrate([100,0],baseline={'pixel':100,'source':'assumption'},scale='unknown')


def test_horizontal_coordinates_and_negative_values():
    r=calibrate([-10,-50,-100],[anchor(-10,-900),anchor(-100,0)],scale='linear',pixel_error=0)
    np.testing.assert_allclose(r['values'],[-900,-500,0],atol=1e-7)


@pytest.mark.parametrize('scale',['linear','log'])
def test_infeasible_ols_uses_constrained_minimum_not_arbitrary_vertex(scale):
    # In transformed coordinates b=0 and 1 <= a <= 4/3. The constrained
    # least-squares optimum is a=6/5; the zero-objective LP picks a=1.
    values=[0,2,2] if scale=='linear' else [1,100,100]
    anchors=[anchor(p,v,pixel_error=e) for p,v,e in zip([0,-1,-2],values,[0,1,.5])]
    r=calibrate([0,-1,-2],anchors,scale=scale,pixel_error=0)
    assert r['status']=='calibrated'
    assert r['point_estimator']['method']=='constrained_least_squares'
    np.testing.assert_allclose(list(r['coefficients'].values()),[1.2,0],atol=1e-9)
    expected=np.array([0,1.2,2.4]);expected=10**expected if scale=='log' else expected
    np.testing.assert_allclose(r['values'],expected,atol=1e-8)
    low=np.array([0,1,2]);high=np.array([0,4/3,8/3])
    if scale=='log':low,high=10.**low,10.**high
    np.testing.assert_allclose(r['lower'],low,atol=1e-8)
    np.testing.assert_allclose(r['upper'],high,atol=1e-8)
    assert all(lo-1e-8<=v<=hi+1e-8 for lo,v,hi in zip(r['lower'],r['values'],r['upper']))


def test_constrained_fit_is_invariant_to_pixel_origin_and_units():
    def run(shift,factor,money):
        anchors=[anchor(shift+factor*p,money*v,pixel_error=factor*e)
                 for p,v,e in zip([0,-1,-2],[0,2,2],[0,1,.5])]
        return calibrate([shift+factor*p for p in [0,-1,-2]],anchors,scale='linear',pixel_error=0)
    base=run(0,1,1)
    for shift,factor,money in [(1000,30,100000),(200,5,.01),(-20000,100,1)]:
        r=run(shift,factor,money)
        np.testing.assert_allclose(np.array(r['values'])/money,base['values'],atol=1e-8)


def test_constrained_fit_matches_independent_convex_optimizer():
    from scipy.optimize import minimize,LinearConstraint
    rng=np.random.default_rng(70291);constrained=0
    for _ in range(16):
        q=np.arange(6,dtype=float);a,b=rng.uniform(.5,2),rng.uniform(2,10)
        errors=rng.uniform(.15,.9,len(q));errors[0]=0
        values=a*q+b+rng.uniform(-.95,.95,len(q))*a*errors
        anchors=[anchor(-x,v,pixel_error=e) for x,v,e in zip(q,values,errors)]
        r=calibrate(-q,anchors,scale='linear',pixel_error=0)
        assert r['status']=='calibrated'
        constrained+=r['point_estimator']['method']=='constrained_least_squares'
        matrix=np.array([[x-e,1] if sign==0 else [-x-e,-1] for x,e in zip(q,errors) for sign in range(2)])
        limits=np.array([v if sign==0 else -v for v in values for sign in range(2)])
        design=np.column_stack((q,np.ones(len(q))))
        reference=minimize(lambda z:float(np.sum((design@z-values)**2)),[a,b],
                           jac=lambda z:2*design.T@(design@z-values),bounds=[(1e-12,None),(None,None)],
                           constraints=[LinearConstraint(matrix,-np.inf,limits)],method='SLSQP',options={'ftol':1e-12})
        assert reference.success
        coef=np.array(list(r['coefficients'].values()))
        assert np.max(matrix@coef-limits)<1e-7
        np.testing.assert_allclose(coef,reference.x,atol=1e-6)
    assert constrained>=8
