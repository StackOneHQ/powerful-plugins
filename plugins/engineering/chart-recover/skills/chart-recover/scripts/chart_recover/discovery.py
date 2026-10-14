"""Bounded discovery through a public founder-post directory, without X login."""
from html.parser import HTMLParser
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlsplit
import json
import requests
from .collect import POST_URL,PublicXCollector,save_posts

FEED='https://braginpublic.com/feed'


class _Links(HTMLParser):
    def __init__(self):super().__init__();self.urls=[];self.seen=set()
    def handle_starttag(self,tag,attrs):
        if tag!='a':return
        href=dict(attrs).get('href','');match=POST_URL.fullmatch(href)
        if match and match[2] not in self.seen:
            self.seen.add(match[2]);self.urls.append(f'https://x.com/{match[1]}/status/{match[2]}')


def discover_urls(html):
    parser=_Links();parser.feed(html);return parser.urls


def _feed_response(session):
    url=FEED
    for _ in range(4):
        response=session.get(url,timeout=30,stream=True,allow_redirects=False)
        if response.status_code not in (301,302,303,307,308):return response
        target=urljoin(url,response.headers.get('Location',''))
        response.close()
        parts=urlsplit(target)
        if parts.scheme!='https' or parts.hostname!=urlsplit(FEED).hostname or parts.port not in (None,443) or parts.username or parts.password:
            raise ValueError('Discovery redirect must remain on the public directory HTTPS host')
        url=target
    raise RuntimeError('Public discovery directory exceeded the redirect limit')


def discover(folder,limit=10,session=None,collector=None,download=True):
    """Collect up to limit visible post links, recording failures without retry.

    This feed is curated and biased toward founders who disclose revenue. It
    does not represent all of X and cannot establish which images omit axes.
    """
    if not 1<=limit<=50:raise ValueError('discovery limit must be 1..50')
    out=Path(folder);out.mkdir(parents=True,exist_ok=True)
    session=session or requests.Session();collector=collector or PublicXCollector(session)
    records=[]
    summary=dict(source=FEED,discovered_urls=0,requested=limit,records=records,stored_posts=0,downloaded_images=0,
                 observed_at=datetime.now(timezone.utc).isoformat(),status='collecting',
                 limitations='Curated public revenue feed; post media are chart candidates, not confirmed hidden-axis charts.')
    response=None
    try:
        response=_feed_response(session)
        if response.status_code!=200:raise RuntimeError(f'Public discovery directory unavailable: HTTP {response.status_code}')
        body=bytearray()
        for chunk in response.iter_content(65536):
            body.extend(chunk)
            if len(body)>5_000_000:raise ValueError('Discovery page exceeds 5MB')
    except (ValueError,RuntimeError,requests.RequestException,OSError) as error:
        summary['status']='failed'
        records.append(dict(url=FEED,status='unavailable',reason=str(error)))
        (out/'discovery.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        raise
    finally:
        if response is not None:response.close()
    urls=discover_urls(body.decode('utf-8',errors='replace'))
    summary['discovered_urls']=len(urls)
    for url in urls[:limit]:
        try:
            posts=collector.lookup(url)
            for p in posts:p['discovered_via']=FEED
            result=save_posts(posts,out,download=download)
            records.append(dict(url=url,status='collected',media_exposed=sum(len(p.get('media',[])) for p in posts),added=result['added']))
        except (ValueError,RuntimeError,requests.RequestException,OSError) as error:
            records.append(dict(url=url,status='unavailable',reason=str(error)))
        (out/'discovery.json').write_text(json.dumps(summary,indent=2), encoding="utf-8")
    if (out/'posts.jsonl').exists():
        posts=[json.loads(line) for line in (out/'posts.jsonl').read_text(encoding="utf-8").splitlines() if line.strip()]
        summary['stored_posts']=len(posts);summary['downloaded_images']=sum(len(p.get('images',[])) for p in posts)
    summary['status']='complete'
    (out/'discovery.json').write_text(json.dumps(summary,indent=2), encoding="utf-8");return summary
