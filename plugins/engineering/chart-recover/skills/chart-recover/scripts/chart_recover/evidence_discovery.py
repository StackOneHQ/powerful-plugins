"""Find bounded public-profile hypotheses from post links or a public catalog.

Catalog matches retrieve candidates; they never establish chart identity or
provide numerical anchors. No search/pagination or private API is used.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import unicodedata
import requests
from PIL import Image
from .public_profile import profile_url, fetch_profile, parse_profile
from .ocr import read_text
from .autopilot import consensus_tokens

DISCOVERY_URL='https://trustmrr.com/api/ai/discovery'
GROUPS=('recentlyAddedStartups','fastestGrowingStartups')
GENERIC_NAMES={'anonymous startup','confidential startup','private venture','private enterprise',
               'stealth company','stealth venture','hidden business','unnamed company',
               'revenue','mrr','arr','startup','sales','growth'}


def normalized(text):
    return ' '.join(unicodedata.normalize('NFKC',text).casefold().split())


def exact_name(name,text):
    name=normalized(name)
    return len(name)>=4 and name not in GENERIC_NAMES and bool(re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',normalized(text)))


def parse_catalog(payload):
    if not isinstance(payload,dict) or not all(k in payload for k in GROUPS):
        raise ValueError('Missing documented discovery groups')
    entries={}
    for group in GROUPS:
        rows=payload[group]
        if not isinstance(rows,list) or len(rows)>25:
            raise ValueError('Discovery group exceeds its documented 25-entry bound')
        for index,row in enumerate(rows):
            if not isinstance(row,dict) or not isinstance(row.get('name'),str) or not isinstance(row.get('slug'),str):
                raise ValueError('Discovery entry needs a name and canonical slug')
            name=row['name'].strip();url=profile_url('https://trustmrr.com/startup/'+row['slug'])
            if not name or len(name)>150:raise ValueError('Invalid discovery name')
            if url in entries and entries[url]['name']!=name:raise ValueError('Conflicting names for a discovery slug')
            entry=entries.setdefault(url,dict(name=name,url=url,slug=row['slug'],locations=[]))
            entry['locations'].append(dict(group=group,index=index))
    return list(entries.values())


def post_profile_links(context):
    observations=[]
    source=context.get('source')
    if isinstance(source,str):observations.append(('source_url',source))
    text=context.get('post_text','')
    if isinstance(text,str):
        observations.extend(('post_text_url',u.rstrip('.,;:)]}')) for u in re.findall(r'https?://[^\s<>"\']+',text[:20000]))
    links=context.get('post_links',[])
    if isinstance(links,list):
        for link in links[:100]:
            if isinstance(link,dict) and isinstance(link.get('expanded_url'),str):
                observations.append(('post_api_expanded_url',link['expanded_url']))
    found={};rejected=[]
    for kind,url in observations:
        try:canonical=profile_url(url)
        except ValueError:
            rejected.append(dict(url=url,basis=kind,reason='Not an exact supported public startup profile URL.'));continue
        found.setdefault(canonical,dict(url=canonical,basis=[]))['basis'].append(dict(kind=kind,observed_url=url))
    return list(found.values()),rejected


def header_lines(tokens,height):
    rows=[]
    for t in sorted(tokens,key=lambda t:(t['box'][1],t['box'][0])):
        x,y,w,h=t['box'];center=y+h/2
        if center>height*.35:continue
        row=next((r for r in rows if abs(r['y']-center)<max(5,h*.6)),None)
        if row is None:row=dict(y=center,tokens=[]);rows.append(row)
        row['tokens'].append(t)
    return [dict(text=' '.join(t['text'] for t in sorted(r['tokens'],key=lambda t:t['box'][0])),
                 boxes=[t['box'] for t in r['tokens']]) for r in rows]


class EvidenceDiscovery:
    def __init__(self,output,cache=None,session=None):
        self.output=Path(output);self.output.mkdir(parents=True,exist_ok=True)
        self.cache=Path(cache).resolve() if cache else None
        self.session=session or requests.Session();self._catalog=None;self._catalog_error=None
        self._profiles={};self._profile_errors={}

    def catalog(self):
        if self._catalog is not None:return self._catalog
        if self._catalog_error:raise ValueError(self._catalog_error)
        try:
            if self.cache:
                path=(self.cache/'discovery.json').resolve()
                if not path.is_relative_to(self.cache):raise ValueError('Catalog cache path escapes its directory')
                with path.open('rb') as f:content=f.read(2_000_001)
                retrieved_at=None
            else:
                response=self.session.get(DISCOVERY_URL,timeout=30,stream=True,allow_redirects=False,
                    headers={'User-Agent':'ChartRecover/0.1 (public chart research)'})
                try:
                    if response.status_code!=200:raise ValueError(f'Public discovery unavailable (HTTP {response.status_code}); no fallback attempted')
                    body=bytearray()
                    for chunk in response.iter_content(65536):
                        body.extend(chunk)
                        if len(body)>2_000_000:raise ValueError('Public discovery exceeds 2MB')
                    content=bytes(body);retrieved_at=datetime.now(timezone.utc).isoformat()
                finally:response.close()
            if len(content)>2_000_000:raise ValueError('Public discovery exceeds 2MB')
            entries=parse_catalog(json.loads(content))
            (self.output/'catalog.raw.json').write_bytes(content)
            self._catalog=dict(source=DISCOVERY_URL,source_sha256=hashlib.sha256(content).hexdigest(),
                               retrieved_at=retrieved_at,mode='offline_snapshot' if self.cache else 'live_public_snapshot',entries=entries)
            (self.output/'catalog.json').write_text(json.dumps(self._catalog,indent=2), encoding="utf-8")
            return self._catalog
        except (ValueError,OSError,requests.RequestException) as e:
            self._catalog_error=str(e)
            (self.output/'catalog-error.json').write_text(json.dumps(dict(source=DISCOVERY_URL,error=str(e),mode='offline_snapshot' if self.cache else 'live_public_snapshot'),indent=2), encoding="utf-8")
            raise

    def discover(self,image,context,output):
        out=Path(output);out.mkdir(parents=True,exist_ok=True)
        candidates,rejected=post_profile_links(context)
        result=dict(status='candidates_found' if candidates else 'no_candidate',candidates=candidates,
                    rejected_links=rejected,profile_url_supplied=False,
                    policy='At most three source hypotheses; no ranking by monetary agreement. Discovery does not establish identity.',
                    catalog_used=False)
        if not candidates:
            try:
                catalog=self.catalog();result.update(catalog_used=True,catalog_source=catalog['source'],catalog_sha256=catalog['source_sha256'])
                scans=[read_text(image,scale=s) for s in (2.,3.)]
                tokens,disagreements=consensus_tokens(scans[0]['tokens'],scans[1]['tokens'])
                with Image.open(image) as im:height=im.height
                headers=header_lines(tokens,height);result.update(ocr=scans,ocr_disagreements=disagreements,image_headers=headers)
                for entry in catalog['entries']:
                    basis=[]
                    for header in headers:
                        if exact_name(entry['name'],header['text']):basis.append(dict(kind='catalog_name_in_image_header',**header))
                    if exact_name(entry['name'],context.get('post_text') or ''):basis.append(dict(kind='catalog_name_in_post_text',name=entry['name']))
                    if basis:candidates.append(dict(url=entry['url'],name=entry['name'],catalog_locations=entry['locations'],basis=basis))
                result['status']='candidates_found' if candidates else 'no_candidate'
            except (ValueError,OSError,RuntimeError,requests.RequestException) as e:
                result.update(status='discovery_unavailable',reason=str(e))
        if len(candidates)>3:
            result.update(status='too_many_candidates',reason='More than three supported sources match; no subset selected and no profile fetched.')
        (out/'discovery.json').write_text(json.dumps(result,indent=2,allow_nan=False), encoding="utf-8");return result

    def profile(self,url,output):
        canonical=profile_url(url)
        if canonical in self._profile_errors:raise ValueError(self._profile_errors[canonical])
        if canonical not in self._profiles:
            try:
                if not self.cache:
                    profile=fetch_profile(canonical,output,session=self.session)
                    text=(Path(output)/'profile.md').read_text(encoding="utf-8")
                else:
                    slug=canonical.rsplit('/',1)[1][:-3]
                    path=(self.cache/'profiles'/f'{slug}.md').resolve()
                    if not path.is_relative_to(self.cache):raise ValueError('Profile cache path escapes its directory')
                    with path.open('rb') as f:content=f.read(500_001)
                    if len(content)>500_000:raise ValueError('Public profile exceeds 500KB')
                    text=content.decode('utf-8');profile=parse_profile(text,canonical)
                self._profiles[canonical]=(profile,text)
            except (ValueError,OSError,RuntimeError,requests.RequestException) as e:
                self._profile_errors[canonical]=str(e);raise
        profile,text=self._profiles[canonical]
        out=Path(output);out.mkdir(parents=True,exist_ok=True)
        (out/'profile.md').write_text(text, encoding="utf-8");(out/'profile.json').write_text(json.dumps(profile,indent=2), encoding="utf-8")
        return profile
