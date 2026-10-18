import pytest
from chart_recover.constraints import calibrate_totals


def total(value=160,**kw):
    return dict(value=value,kind='sum',point_indices=[0,1,2],observation_count=3,source='Public period total',matched=True,**kw)


def test_total_with_zero_baseline_recovers_points_not_total_as_endpoint():
    r=calibrate_totals([80,50,10],totals=[total()],baseline={'pixel':100,'source':'Visible zero tick','verified':True},pixel_error=0)
    assert r['status']=='calibrated'
    assert r['values']==pytest.approx([20,50,90])
    assert sum(r['values'])==pytest.approx(160)


def test_total_alone_is_unbounded():
    r=calibrate_totals([80,50,10],totals=[total()],pixel_error=0)
    assert r['status']=='unidentifiable' and r['values'] is None


def test_total_and_nonnegative_domain_yield_only_bounds():
    r=calibrate_totals([80,50,10],totals=[total()],value_domain={'low':0,'source':'Explicit nonnegative assumption'},pixel_error=0)
    assert r['status']=='bounded_only' and r['values'] is None
    assert r['lower'][0]==pytest.approx(0)
    assert r['upper'][-1]==pytest.approx(112)
    assert all(lo<=v<=hi for lo,v,hi in zip(r['lower'],[20,50,90],r['upper']))


def test_two_disjoint_totals_identify_axis_without_baseline():
    totals=[dict(total(70),point_indices=[0,1],observation_count=2),dict(total(140),point_indices=[1,2],observation_count=2)]
    r=calibrate_totals([80,50,10],totals=totals,pixel_error=0)
    assert r['status']=='calibrated' and r['values']==pytest.approx([20,50,90])


def test_total_and_dated_point_can_identify_nonzero_baseline():
    r=calibrate_totals([80,50,10],anchors=[dict(pixel=10,value=90,source='Endpoint',matched=True)],totals=[total()],pixel_error=0)
    assert r['status']=='calibrated' and r['values']==pytest.approx([20,50,90])


def test_conflicting_sum_is_not_repaired():
    r=calibrate_totals([80,50,10],anchors=[dict(pixel=80,value=20,source='First',matched=True),dict(pixel=10,value=90,source='Last',matched=True)],totals=[total(1000)],pixel_error=0)
    assert r['status']=='inconsistent'


def test_missing_observation_count_does_not_sum_interpolated_samples():
    t=total();del t['observation_count']
    with pytest.raises(ValueError,match='observation_count'):calibrate_totals([80,50,10],totals=[t])


def test_unconfirmed_total_never_calibrates():
    t=total();t['matched']=False
    assert calibrate_totals([80,50,10],totals=[t])['status']=='unidentifiable'


def test_pixel_intervals_cover_reconstruction_with_rounded_total():
    t=total();del t['value'];t.update(low=159,high=161)
    r=calibrate_totals([80.3,49.7,10.2],totals=[t],baseline={'pixel':100,'source':'Supplied zero'},pixel_error=1)
    assert all(lo<=v<=hi for lo,v,hi in zip(r['lower'],[20,50,90],r['upper']))
