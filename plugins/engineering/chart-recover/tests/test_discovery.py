import json
from chart_recover.discovery import discover_urls,discover


def test_discovery_uses_only_explicit_post_links_and_deduplicates():
    html='''<a href="https://x.com/alice/status/123?utm_source=public">Post</a>
    <a href="https://x.com/alice/status/123">Same</a><a href="https://x.com/alice">Profile</a>
    <a href="https://x.com/bob/status/456">Post</a><a href="http://localhost/secret">Ignore</a>'''
    assert discover_urls(html)==['https://x.com/alice/status/123','https://x.com/bob/status/456']


def test_discovery_records_failures_and_limits_reads(tmp_path):
    class Response:
        status_code=200
        def iter_content(self,n):yield b'<a href="https://x.com/alice/status/123">a</a><a href="https://x.com/bob/status/456">b</a><a href="https://x.com/c/status/789">c</a>'
        def close(self):pass
    class Session:
        def get(self,url,**kw):assert url=='https://braginpublic.com/feed';return Response()
    class Collector:
        calls=[]
        def lookup(self,url):
            self.calls.append(url)
            if url.endswith('456'):raise RuntimeError('Public page unavailable')
            return [dict(id='123',url=url,text='Public revenue',media=[])]
    collector=Collector();result=discover(tmp_path,2,Session(),collector,download=False)
    assert len(collector.calls)==2 and result['discovered_urls']==3
    assert result['stored_posts']==1 and result['records'][-1]['status']=='unavailable'
    assert json.loads((tmp_path/'posts.jsonl').read_text())['discovered_via']=='https://braginpublic.com/feed'
