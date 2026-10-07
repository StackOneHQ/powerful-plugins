"""Read-only X API collection and reproducible import of public post records."""
from __future__ import annotations
import hashlib
import json
import os
import re
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from html.parser import HTMLParser
import requests
from PIL import Image


POST_URL=re.compile(r'https://(?:www\.)?(?:x|twitter)\.com/([A-Za-z0-9_]+)/status/(\d+)(?:\?[^#]*)?(?:#.*)?')


class _PublicMetadata(HTMLParser):
    def __init__(self):
        super().__init__();self.fields={}

    def handle_starttag(self,tag,attrs):
        if tag!='meta':return
        attrs=dict(attrs);name=attrs.get('property',attrs.get('name',''))
        if name and attrs.get('content'):self.fields.setdefault(name,[]).append(attrs['content'])


def parse_public_post(html,url):
    """Read the public post's Open Graph metadata, not private app state."""
    match=POST_URL.fullmatch(url)
    if not match:raise ValueError('Expected public X post URL')
    parser=_PublicMetadata();parser.feed(html);fields=parser.fields
    canonical=fields.get('og:url',[''])[0];actual=POST_URL.fullmatch(canonical)
    if not actual or actual[2]!=match[2]:raise ValueError('Public page does not expose matching post metadata')
    text=fields.get('og:description',fields.get('twitter:description',['']))[0]
    if not text:raise ValueError('Public post text unavailable; use an authorized API or browser export')
    media=[];seen=set()
    for image in fields.get('og:image',fields.get('twitter:image',[])):
        parts=urlsplit(image)
        if parts.scheme=='https' and parts.hostname=='pbs.twimg.com' and parts.path.startswith('/media/') and image not in seen:
            seen.add(image);media.append(dict(type='photo',url=image))
    return dict(id=actual[2],author=actual[1],url=f'https://x.com/{actual[1]}/status/{actual[2]}',
                text=text,media=media,created_at=fields.get('article:published_time',[None])[0],
                collection_method='public_open_graph_metadata',collected_at=datetime.now(timezone.utc).isoformat(),
                collection_limits='Only media exposed by public page metadata; may omit additional photos. No authentication or access-barrier bypass.')


class PublicXCollector:
    """One ordinary read of a public URL; refuse login, challenge or error pages."""
    def __init__(self,session=None):self.session=session or requests.Session()

    def lookup(self,url):
        match=POST_URL.fullmatch(url)
        if not match:raise ValueError('Expected public X post URL')
        canonical=f'https://x.com/{match[1]}/status/{match[2]}'
        response=self.session.get(canonical,timeout=30,stream=True,allow_redirects=False,
                                  headers={'User-Agent':'ChartRecover/0.1 (public chart research)'})
        try:
            if response.status_code!=200:raise RuntimeError(f'Public X page unavailable (HTTP {response.status_code}); use authorized API access or import a browser-observed record.')
            content=bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content)>5_000_000:raise ValueError('Public page exceeds 5MB')
            return [parse_public_post(content.decode('utf-8',errors='replace'),canonical)]
        finally:
            response.close()


def normalize_response(payload):
    media={m['media_key']:m for m in payload.get('includes',{}).get('media',[])}
    users={u['id']:u for u in payload.get('includes',{}).get('users',[])}
    posts=payload.get('data',[])
    if isinstance(posts,dict):posts=[posts]
    result=[]
    for post in posts:
        author=users.get(post.get('author_id'),{}).get('username','i')
        result.append(dict(id=post['id'],url=f"https://x.com/{author}/status/{post['id']}",
                           author=author,text=post.get('text',''),created_at=post.get('created_at'),
                           links=[{k:u[k] for k in ('url','expanded_url','display_url') if isinstance(u.get(k),str)}
                                  for u in post.get('entities',{}).get('urls',[]) if isinstance(u,dict)],
                           media=[media[k] for k in post.get('attachments',{}).get('media_keys',[]) if k in media],
                           collection_method='x_api_v2',collected_at=datetime.now(timezone.utc).isoformat()))
    return result


class XCollector:
    def __init__(self,token=None,session=None):
        self.token=token or os.getenv('X_BEARER_TOKEN')
        if not self.token:raise ValueError('Set X_BEARER_TOKEN for X API access, or import public post JSONL records.')
        self.session=session or requests.Session()

    def _get(self,path,params):
        response=self.session.get('https://api.x.com/2/'+path,params=params,
                                  headers={'Authorization':'Bearer '+self.token},timeout=30)
        if response.status_code==429:raise RuntimeError('X rate limit reached; retain results and retry after the provider reset.')
        if response.status_code in (401,403):raise RuntimeError('X API authentication or plan access required.')
        response.raise_for_status();return response.json()

    @staticmethod
    def _fields():return {'expansions':'attachments.media_keys,author_id','tweet.fields':'created_at,attachments,text,entities,author_id',
                          'media.fields':'url,type,alt_text,width,height','user.fields':'username'}

    def search(self,query,max_pages=1):
        if not 1<=max_pages<=100:raise ValueError('max_pages must be 1..100')
        params=dict(self._fields(),query=query,max_results=100);seen=set()
        for _ in range(max_pages):
            payload=self._get('tweets/search/recent',params)
            for post in normalize_response(payload):
                if post['id'] not in seen:seen.add(post['id']);yield post
            token=payload.get('meta',{}).get('next_token')
            if not token:break
            params['next_token']=token

    def lookup(self,url):
        m=re.fullmatch(r'https://(?:www\.)?(?:x|twitter)\.com/[^/]+/status/(\d+)(?:\?.*)?',url)
        if not m:raise ValueError('Expected public X post URL')
        return normalize_response(self._get('tweets/'+m[1],self._fields()))


def save_posts(posts,folder,download=True):
    """Append deduplicated post manifest. Images are inbound only, max 20MB."""
    out=Path(folder);out.mkdir(parents=True,exist_ok=True);manifest=out/'posts.jsonl'
    existing={}
    if manifest.exists():
        existing={p['id']:p for p in map(json.loads,manifest.read_text(encoding="utf-8").splitlines())}
    count=0
    for post in posts:
        post=dict(post)
        if not re.fullmatch(r'\d+',post['id']):raise ValueError('Post id must be numeric')
        if post['id'] in existing:continue
        post.setdefault('collected_at',datetime.now(timezone.utc).isoformat());post['images']=[]
        for i,media in enumerate(post.get('media',[])):
            if media.get('type')!='photo' or not media.get('url'):continue
            url=media['url'];parts=urlsplit(url)
            if parts.scheme!='https' or parts.hostname!='pbs.twimg.com' or not parts.path.startswith('/media/'):
                post.setdefault('errors',[]).append('Skipped media outside the X image CDN');continue
            if not download:continue
            try:
                r=requests.get(url,timeout=30,stream=True,allow_redirects=False);r.raise_for_status()
                if r.status_code!=200:raise ValueError('Unexpected image redirect/status')
                content=bytearray()
                for chunk in r.iter_content(65536):
                    content.extend(chunk)
                    if len(content)>20_000_000:raise ValueError('Image exceeds 20MB')
                path=out/f"{post['id']}-{i}.image";path.write_bytes(content)
                with Image.open(path) as im:im.verify()
                post['images'].append(dict(path=path.name,source_url=url,sha256=hashlib.sha256(content).hexdigest()))
            except (requests.RequestException,ValueError,OSError) as e:
                post.setdefault('errors',[]).append(type(e).__name__+': media download failed')
        existing[post['id']]=post;count+=1
        manifest.write_text(''.join(json.dumps(p)+'\n' for p in existing.values()), encoding="utf-8")
    return dict(added=count,total=len(existing),manifest=str(manifest))
