import pytest
from chart_recover.public_profile import parse_profile,profile_url,fetch_profile


PROFILE='''# Lumen
- Name: Lumen
- Slug: `lumen`
- Revenue last synced: 2026-10-04T02:26:55.502Z
- Verified payment provider API source: Stripe (API key)
### Daily revenue — last 30 days
| Date | Verified revenue |
| --- | ---: |
| 2026-10-01 | $1,200 |
| 2026-10-02 | REDACTED |
| 2026-10-03 | $998.25 |
| 2026-10-04 | $90 |
### Monthly revenue timeline
| Month | Verified revenue |
| --- | ---: |
| 2026-09 | $20,000 |
| 2026-10 | $2,288.25 |
## Metric Snapshots
- Current MRR: $50,000
## Recommendations
| 2026-10-01 | $999,999 |
'''
URL='https://trustmrr.com/startup/lumen.md'


def test_dated_table_keeps_provenance_and_excludes_partial_periods():
    p=parse_profile(PROFILE,URL)
    assert p['entity']=='Lumen' and p['currency']=='$'
    daily,monthly=p['tables']
    assert len(daily['rows'])==4 and len(monthly['rows'])==2
    assert daily['rows'][0]['low']==1199.5
    assert daily['rows'][2]['low']==998.245
    assert daily['rows'][1]['status']=='unreadable_amount'
    assert daily['rows'][3]['status']==monthly['rows'][1]['status']=='partial_period_excluded'
    assert daily['rows'][0]['quote']=='| 2026-10-01 | $1,200 |'
    assert all(r['source_sha256']==p['source_sha256'] for t in p['tables'] for r in t['rows'])
    assert all(r['value'] not in (50000,999999) for t in p['tables'] for r in t['rows'])


@pytest.mark.parametrize('url',['http://trustmrr.com/startup/lumen','https://trustmrr.com.evil.test/startup/lumen',
    'https://trustmrr.com:443/startup/lumen','https://u:p@trustmrr.com/startup/lumen','https://trustmrr.com/api/v1/startups/lumen',
    'https://trustmrr.com/startup/lumen?x=1','https://trustmrr.com/startup/lumen#x'])
def test_public_profile_url_has_no_auth_or_api_fallback(url):
    with pytest.raises(ValueError):profile_url(url)


@pytest.mark.parametrize('old,new',[
    ('`lumen`','`other`'),('2026-10-03 |','2026-10-01 |'),('2026-10-03 |','2026-10-30 |'),
    ('2026-10-03 |','2026-13-03 |'),('02:26:55.502Z','02:26:55.502'),
    ('| Date | Verified revenue |','| Date | MRR |'),
])
def test_malformed_or_conflicting_table_fails_closed(old,new):
    with pytest.raises(ValueError):parse_profile(PROFILE.replace(old,new),URL)


def test_fetch_stops_at_access_response_without_following_redirects(tmp_path):
    class Response:
        status_code=302
        closed=False
        def close(self):self.closed=True
    class Session:
        calls=[]
        response=Response()
        def get(self,url,**kwargs):self.calls.append((url,kwargs));return self.response
    session=Session()
    with pytest.raises(RuntimeError):fetch_profile(URL,tmp_path,session)
    assert len(session.calls)==1 and session.calls[0][1]['allow_redirects'] is False
    assert session.response.closed and not (tmp_path/'profile.md').exists()


def test_nonfinite_public_amount_is_rejected():
    with pytest.raises(ValueError):parse_profile(PROFILE.replace('$1,200','$'+'9'*400),URL)
