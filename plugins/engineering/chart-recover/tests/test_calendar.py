import calendar
from chart_recover.calendar_vision import locate_calendar
from chart_recover.calendar_recovery import correspondence


def token(text,x,y,w=15,h=12):return dict(text=text,box=[x,y,w,h],confidence=95)


def calendar_tokens(year=2024,month=2,first_weekday=0):
    out=[token(calendar.month_name[month],300,400,60),token(str(year),365,400,36)]
    letters=['M','T','W','T','F','S','S'] if first_weekday==0 else ['S','M','T','W','T','F','S']
    out += [token(letter,300+i*40,440,10) for i,letter in enumerate(letters)]
    offset=(calendar.monthrange(year,month)[0]-first_weekday)%7
    for day in range(1,calendar.monthrange(year,month)[1]+1):
        row,col=divmod(day+offset-1,7);out.append(token('$100',292+col*40,480+row*45,26))
    return out


def test_calendar_dates_include_leap_day_and_respect_week_start():
    for first in (0,6):
        candidates=locate_calendar(calendar_tokens(first_weekday=first),[1000,900])
        assert len(candidates)==1
        c=candidates[0];assert c['days']==29 and c['weekday']['first_weekday']==first
        assert c['offset']==(calendar.monthrange(2024,2)[0]-first)%7


def test_calendar_requires_year_and_regular_weekday_grid():
    tokens=calendar_tokens();tokens=[t for t in tokens if t['text']!='2024']
    assert not locate_calendar(tokens,[1000,900])


def test_missing_trailing_week_readings_do_not_shift_dates():
    tokens=calendar_tokens(year=2024,month=9,first_weekday=6)
    amounts=[t for t in tokens if t['text'].startswith('$')];last_y=max(t['box'][1] for t in amounts)
    tokens=[t for t in tokens if not (t['text'].startswith('$') and t['box'][1]==last_y)]
    c=locate_calendar(tokens,[1000,900])[0]
    assert c['extrapolated_trailing_rows']==1 and len(c['row_centers'])==5
    assert c['offset']==0 and c['row_centers'][-1]==last_y+6
    tokens=calendar_tokens();tokens[4]['box'][0]+=18
    assert not locate_calendar(tokens,[1000,900])


def context():
    tokens=calendar_tokens(year=2026,month=7)
    layout=locate_calendar(tokens,[1000,900])[0]
    geometry=dict(roi=[50,100,850,300],series=[dict(points=[dict(x=55+i*26.3,y=200) for i in range(31)])])
    return dict(consensus_tokens=tokens,size=[1000,900],layout=layout),geometry


def test_calendar_values_do_not_establish_curve_identity_or_dates():
    cal,geo=context();r=correspondence(cal,geo,{})
    assert r['status']=='needs_review' and len(r['reasons'])==2
    assumed=correspondence(cal,geo,dict(assume_shared_daily_revenue=True,assume_full_month=True))
    assert assumed['status']=='matched' and len(assumed['assumptions'])==2
    assert not assumed['metric_from_image'] and not assumed['full_period_from_image']


def test_visible_metric_contradiction_cannot_be_overridden_by_generic_assumption():
    cal,geo=context();cal['consensus_tokens'].append(token('MRR',70,60,40))
    r=correspondence(cal,geo,dict(assume_shared_daily_revenue=True,assume_full_month=True))
    assert r['status']=='needs_review' and any('heading contradicts' in s for s in r['reasons'])


def test_visible_different_month_blocks_calendar_correspondence():
    cal,geo=context();cal['consensus_tokens'] += [token('June',70,60,36),token('2026',110,60,36)]
    r=correspondence(cal,geo,dict(assume_shared_daily_revenue=True,assume_full_month=True))
    assert r['status']=='needs_review' and any('period or endpoint' in s for s in r['reasons'])


def test_matching_image_headings_and_overlapping_date_boxes_supply_correspondence():
    cal,geo=context()
    cal['observations']=[dict(currency='$')]
    cal['consensus_tokens'] += [token('Daily',60,40,35),token('revenue',100,40,60),
        token('$',175,40),
        token('July',210,40,35),token('2026',250,40,35),
        token('Daily',295,375,35),token('revenue',335,375,60),
        token('Jul',35,320,27),token('1',57,320,7),
        token('Jul',825,320,24),token('31',852,320,14)]
    r=correspondence(cal,geo,dict(assume_full_month=True))
    assert r['status']=='matched' and r['metric_from_image'] and r['full_period_from_image']
    assert len(r['assumptions'])==1 and not r['daily_sampling_from_image']
