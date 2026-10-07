from datetime import date,timedelta
import numpy as np
import pytest
from chart_recover.external_evidence import select_alignment


def fixture(ys):
    xs=np.arange(50,921,dtype=float)
    geometry=dict(size=[1000,600],roi=[49,80,922,420],series=[dict(points=[
        dict(x=float(x),y=float(y),pixel_error=2.5) for x,y in zip(xs,ys)])])
    axis=dict(origin='2026-09-01',origin_x=51.25,pixels_per_day=29.95,pixel_error=3.,fit_labels=[])
    for dt in (0,5,10,15,20,25,29):
        x=axis['origin_x']+axis['pixels_per_day']*dt
        axis['fit_labels'].append(dict(date=(date(2026,9,1)+timedelta(days=dt)).isoformat(),
            x=x,month_box=[x-25,490,24,16],day_box=[x+1,490,24,16]))
    return geometry,axis


def test_visible_corners_locate_daily_grid_without_monetary_values():
    # Top-edge/numerical-fit alignment cannot establish this grid with no
    # monetary rows. The visible straight segments independently locate it.
    xs=np.arange(50,921,dtype=float)
    ys=np.interp(xs,np.arange(50,921,30),np.random.default_rng(21).uniform(100,400,30))
    g,a=fixture(ys)
    result,ledger=select_alignment(g,[],a)
    assert result is not None
    assert result['origin_x']==pytest.approx(50,abs=.1)
    assert result['pixels_per_day']==pytest.approx(30,abs=.01)
    assert ledger['strategy']=='image_corners'


@pytest.mark.parametrize('phase',[-2,2,4])
def test_rounded_sine_extrema_do_not_establish_corner_grid(phase):
    xs=np.arange(50,921,dtype=float)
    g,a=fixture(250+100*np.cos(2*np.pi*(xs-50-phase)/60))
    result,_=select_alignment(g,[],a)
    assert result is None


def test_curve_without_slope_discontinuities_does_not_establish_corner_grid():
    xs=np.arange(50,921,dtype=float)
    g,a=fixture(100+.001*(xs-470)**2)
    assert select_alignment(g,[],a)[0] is None


def test_corners_confined_to_small_region_do_not_establish_whole_grid():
    xs=np.arange(50,921,dtype=float)
    ys=np.interp(xs,[50,350,380,410,440,470,500,530,920],[300,300,100,350,100,350,100,300,300])
    g,a=fixture(ys)
    assert select_alignment(g,[],a)[0] is None


def test_irregular_corners_do_not_establish_regular_daily_grid():
    xs=np.arange(50,921,dtype=float)
    knots=np.arange(50,921,30,dtype=float);knots[1:-1]+=np.tile([-4.5,4.5],14)
    ys=np.interp(xs,knots,np.random.default_rng(21).uniform(100,400,30))
    g,a=fixture(ys)
    assert select_alignment(g,[],a)[0] is None


def test_fitting_pixels_cannot_dilute_error_on_rounded_join():
    # Shifted corners move part of the central window into the right fitting
    # window. Reusing those perfectly fitted pixels hides the rounded center.
    xs=np.arange(50,921,dtype=float);knots=np.arange(54.8,925,30)
    levels=np.tile([100.,400.],15);ys=np.interp(xs,knots,levels)
    for x,y in zip(knots,levels):
        near=np.abs(xs-x)<1.5
        ys[near]+=15 if y==100 else -15
    g,a=fixture(ys);a['pixels_per_day']=30.
    assert select_alignment(g,[],a)[0] is None
