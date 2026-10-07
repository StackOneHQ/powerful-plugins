import json
import pytest
from chart_recover.collect import normalize_response,save_posts,XCollector

PAYLOAD={'data':[{'id':'123','text':'Public chart','author_id':'u','attachments':{'media_keys':['m']}}],
'includes':{'users':[{'id':'u','username':'founder'}],'media':[{'media_key':'m','type':'photo','url':'https://pbs.twimg.com/media/a.png'}]}}


def test_media_join_and_dedup(tmp_path):
    posts=normalize_response(PAYLOAD)
    assert posts[0]['url']=='https://x.com/founder/status/123'
    assert len(posts[0]['media'])==1
    assert save_posts(posts,tmp_path,download=False)['added']==1
    assert save_posts(posts,tmp_path,download=False)['added']==0
    assert len((tmp_path/'posts.jsonl').read_text().splitlines())==1


def test_pagination_and_fields():
    class Response:
        status_code=200
        def raise_for_status(self):pass
        def json(self):return PAYLOAD
    class Session:
        calls=[]
        def get(self,url,**kw):self.calls.append((url,kw));return Response()
    s=Session();assert len(list(XCollector('fake',s).search('MRR has:images')))==1
    assert s.calls[0][1]['params']['expansions']=='attachments.media_keys,author_id'
    assert s.calls[0][1]['params']['media.fields'].startswith('url,type')
    assert set(s.calls[0][1]['params']['tweet.fields'].split(','))=={'created_at','attachments','text','entities','author_id'}
    assert 'post.fields' not in s.calls[0][1]['params']


def test_missing_credentials(monkeypatch):
    monkeypatch.delenv('X_BEARER_TOKEN',raising=False)
    with pytest.raises(ValueError,match='X_BEARER_TOKEN'):XCollector()


def test_api_expanded_links_are_retained_as_provenance():
    payload={'data':{'id':'123','text':'https://t.co/test','entities':{'urls':[
        dict(url='https://t.co/test',expanded_url='https://trustmrr.com/startup/lumen',display_url='trustmrr.com/startup/lumen')]}}}
    post=normalize_response(payload)[0]
    assert post['links'][0]['expanded_url']=='https://trustmrr.com/startup/lumen'
    assert 'entities' in XCollector._fields()['tweet.fields'].split(',')


def test_unsafe_media_skipped(tmp_path):
    p={'id':'123','media':[{'type':'photo','url':'http://127.0.0.1/secret'}]}
    save_posts([p],tmp_path)
    record=json.loads((tmp_path/'posts.jsonl').read_text());assert record['images']==[] and record['errors']


def test_public_metadata_import_without_credentials():
    from chart_recover.collect import parse_public_post
    html='''<meta property="og:url" content="https://x.com/founder/status/123">
    <meta property="og:description" content="MRR &amp; growth">
    <meta property="og:image" content="https://pbs.twimg.com/media/abc?format=webp&amp;name=large">
    <meta property="og:image" content="https://example.com/unrelated.png">'''
    p=parse_public_post(html,'https://x.com/founder/status/123')
    assert p['text']=='MRR & growth' and len(p['media'])==1
    assert p['media'][0]['url'].endswith('&name=large')
    assert p['created_at'] is None


@pytest.mark.parametrize('html',['<h1>Log in</h1>','<meta property="og:url" content="https://x.com/founder/status/456">'])
def test_public_import_rejects_missing_or_wrong_post(html):
    from chart_recover.collect import parse_public_post
    with pytest.raises(ValueError):parse_public_post(html,'https://x.com/founder/status/123')


def test_public_collector_stops_at_access_barrier():
    from chart_recover.collect import PublicXCollector
    class Response:
        status_code=403
        closed=False
        def close(self):self.closed=True
    class Session:
        calls=0
        response=Response()
        def get(self,*args,**kw):self.calls+=1;assert not kw['allow_redirects'];return self.response
    s=Session()
    with pytest.raises(RuntimeError,match='HTTP 403'):PublicXCollector(s).lookup('https://x.com/founder/status/123')
    assert s.calls==1 and s.response.closed
