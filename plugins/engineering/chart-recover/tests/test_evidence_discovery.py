import json
from pathlib import Path
import pytest
from PIL import Image
from chart_recover.evidence_discovery import EvidenceDiscovery,parse_catalog,post_profile_links,exact_name


def catalog(names=('Lumen',)):
    return dict(recentlyAddedStartups=[dict(name=n,slug='opaque-'+str(i)) for i,n in enumerate(names)],fastestGrowingStartups=[])


def offline(tmp_path,payload):
    cache=tmp_path/'cache';cache.mkdir();(cache/'discovery.json').write_text(json.dumps(payload))
    image=tmp_path/'chart.png';Image.new('RGB',(800,450),'white').save(image)
    return EvidenceDiscovery(tmp_path/'catalog',cache),image


def test_discovery_preserves_explicit_link_basis_and_rejects_lookalike_hosts():
    found,rejected=post_profile_links(dict(source='https://x.com/a/status/123',
        post_text='Source https://trustmrr.com/startup/opaque-1. And https://trustmrr.com.evil.test/startup/lumen',
        post_links=[dict(url='https://t.co/test',expanded_url='https://trustmrr.com/startup/opaque-1.md')]))
    assert len(found)==1 and found[0]['url']=='https://trustmrr.com/startup/opaque-1.md'
    assert {b['kind'] for b in found[0]['basis']}=={'post_text_url','post_api_expanded_url'}
    assert len(rejected)==2


def test_direct_link_discovery_does_not_need_catalog_or_follow_shorteners(tmp_path):
    class Session:
        def get(self,*a,**k):pytest.fail('unexpected network request')
    resolver=EvidenceDiscovery(tmp_path/'catalog',session=Session())
    r=resolver.discover('not-opened',dict(post_text='https://trustmrr.com/startup/lumen https://t.co/abc'),tmp_path/'result')
    assert r['status']=='candidates_found' and not r['catalog_used'] and len(r['candidates'])==1


@pytest.mark.parametrize('name,text,match',[
    ('Lumen','Lumen Labs chart',True),('Lumen','Lumens chart',False),('Lumen','Lumenn chart',False),
    ('Cedar Metrics','CEDAR   METRICS update',True),('Anonymous Startup','Anonymous Startup',False),
    ('ARR','ARR',False),('Revenue','Revenue',False)])
def test_catalog_retrieval_is_exact_not_fuzzy_or_generic(name,text,match):
    assert bool(exact_name(name,text))==match


def test_catalog_deduplicates_but_rejects_conflicting_names():
    p=catalog();p['fastestGrowingStartups']=p['recentlyAddedStartups'].copy()
    assert len(parse_catalog(p))==1 and len(parse_catalog(p)[0]['locations'])==2
    p['fastestGrowingStartups']=[dict(name='Different',slug='opaque-0')]
    with pytest.raises(ValueError,match='Conflicting'):parse_catalog(p)


@pytest.mark.parametrize('payload',[{},dict(recentlyAddedStartups=[dict(name='Lumen',slug='../private')],fastestGrowingStartups=[]),
    dict(recentlyAddedStartups=[dict(name='Lumen',slug='lumen')]*26,fastestGrowingStartups=[])])
def test_malformed_or_unbounded_catalog_fails(payload):
    with pytest.raises(ValueError):parse_catalog(payload)


def test_catalog_candidates_use_header_and_post_text_without_amounts(tmp_path,monkeypatch):
    import chart_recover.evidence_discovery as discovery
    resolver,image=offline(tmp_path,catalog(('Lumen','Cedar Metrics','Pixel Harbor')))
    tokens=[dict(text='Lumen',box=[40,20,100,20],confidence=99),dict(text='Pixel Harbor',box=[40,300,100,20],confidence=99)]
    monkeypatch.setattr(discovery,'read_text',lambda *a,**k:dict(tokens=tokens))
    r=resolver.discover(image,dict(post_text='Cedar Metrics revenue is $1000000'),tmp_path/'result')
    assert {x['url'] for x in r['candidates']}=={'https://trustmrr.com/startup/opaque-0.md','https://trustmrr.com/startup/opaque-1.md'}
    assert r['catalog_used'] and r['profile_url_supplied'] is False


def test_ambiguous_source_set_is_retained_without_truncation(tmp_path,monkeypatch):
    import chart_recover.evidence_discovery as discovery
    resolver,image=offline(tmp_path,catalog(('Lumen','Cedar Metrics','Pixel Harbor','Amber Note')))
    monkeypatch.setattr(discovery,'read_text',lambda *a,**k:dict(tokens=[]))
    r=resolver.discover(image,dict(post_text='Lumen Cedar Metrics Pixel Harbor Amber Note'),tmp_path/'result')
    assert r['status']=='too_many_candidates' and len(r['candidates'])==4


def test_offline_missing_profile_never_fetches(tmp_path):
    class Session:
        def get(self,*a,**k):pytest.fail('offline mode requested the network')
    resolver=EvidenceDiscovery(tmp_path/'out',tmp_path/'missing-cache',session=Session())
    with pytest.raises(OSError):resolver.profile('https://trustmrr.com/startup/lumen',tmp_path/'profile')


def test_catalog_access_barrier_is_not_retried_across_images(tmp_path):
    class Response:
        status_code=403
        def close(self):pass
    class Session:
        calls=0
        def get(self,*a,**k):self.calls+=1;assert k['allow_redirects'] is False;return Response()
    session=Session();resolver=EvidenceDiscovery(tmp_path,session=session)
    for _ in range(2):
        with pytest.raises(ValueError,match='HTTP 403'):resolver.catalog()
    assert session.calls==1


def test_strict_agent_disables_discovery_before_network_or_ocr(tmp_path,monkeypatch):
    import chart_recover.agent as agent
    import chart_recover.evidence_discovery as discovery
    monkeypatch.setattr(agent,'recover',lambda *a,**k:dict(image_sha256='x',status='needs_evidence_or_review',calibrated_candidates=0))
    monkeypatch.setattr(discovery,'EvidenceDiscovery',lambda *a,**k:pytest.fail('strict mode created a resolver'))
    r=agent.investigate_image('ignored',dict(discover_evidence=True),tmp_path,strict_only=True)
    assert r['conditional_candidates']==0
    assert any(s['action']=='discover_external_evidence' and s['status']=='disabled_by_strict_policy' for s in r['steps'])


def test_agent_does_not_fetch_any_profile_after_ambiguous_discovery(tmp_path,monkeypatch):
    import chart_recover.agent as agent
    monkeypatch.setattr(agent,'recover',lambda *a,**k:dict(image_sha256='x',status='needs_evidence_or_review',calibrated_candidates=0))
    class Resolver:
        def discover(self,*a):return dict(status='too_many_candidates',candidates=[dict(url='unused')]*4)
        def profile(self,*a):pytest.fail('ambiguous candidates fetched')
    from PIL import Image
    image=tmp_path/'blank.png';Image.new('RGB',(80,60),'white').save(image)
    r=agent.investigate_image(image,dict(discover_evidence=True),tmp_path,evidence_resolver=Resolver())
    assert r['conditional_candidates']==0
    assert any(s['action']=='discover_external_evidence' and s['status']=='too_many_candidates' for s in r['steps'])
