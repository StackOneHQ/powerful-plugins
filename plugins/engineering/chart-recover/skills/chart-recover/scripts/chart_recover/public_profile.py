"""Read a linked public TrustMRR Markdown profile, preserving dated evidence.

This is an ordinary public-document reader, not access to authenticated metrics.
Provider verification is recorded as a source claim, not independently audited.
"""
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit
import requests


def profile_url(url):
    p = urlsplit(url)
    if (p.scheme != 'https' or p.hostname != 'trustmrr.com' or p.port is not None
            or p.username or p.password or p.query or p.fragment):
        raise ValueError('Expected an exact public https://trustmrr.com/startup/<slug> URL')
    match = re.fullmatch(r'/startup/([a-z0-9]+(?:-[a-z0-9]+)*)(?:\.md)?', p.path)
    if not match:
        raise ValueError('Expected a public startup profile, not an API or account URL')
    return 'https://trustmrr.com/startup/' + match[1] + '.md'


def parse_profile(text, url, retrieved_at=None):
    url = profile_url(url)
    lines = text.splitlines()
    names = re.findall(r'^- Name: (.+)$', text, re.M)
    slugs = re.findall(r'^- Slug: `([^`]+)`$', text, re.M)
    expected = url.rsplit('/', 1)[-1][:-3]
    if len(names) != 1 or slugs != [expected]:
        raise ValueError('Profile identity does not match its public URL')
    name = names[0].strip()
    if not name or len(name) > 150:
        raise ValueError('Missing or oversized profile name')
    syncs = re.findall(r'^- Revenue (?:last synced|data last synced): (\S+)$', text, re.M)
    if not syncs or len(set(syncs)) != 1:
        raise ValueError('Missing or conflicting revenue synchronization timestamp')
    try:
        synced = datetime.fromisoformat(syncs[0].replace('Z', '+00:00'))
        if synced.tzinfo is None:
            raise ValueError('Timestamp needs a timezone')
    except ValueError as e:
        raise ValueError('Invalid revenue synchronization timestamp') from e
    sync_date = synced.astimezone(timezone.utc).date()
    digest = hashlib.sha256(text.encode()).hexdigest()
    result = dict(entity=name, source=url, profile=url[:-3], source_sha256=digest,
                  retrieved_at=retrieved_at, synced_at=syncs[0], metric='revenue',
                  currency='$', tables=[], decisions=[],
                  provider_verification_claim=re.findall(r'^- Verified payment provider API source: (.+)$', text, re.M),
                  limitations=['Provider verification is a source claim, not an independent accounting audit.',
                               'Printed dollar amounts retain the $ symbol; no currency code is inferred.',
                               'Printed amounts are treated as rounded to the nearest displayed precision.',
                               'Public tables can be cached separately from charts; synchronization time is retained.'])
    sections = {'### Daily revenue — last 30 days': ('daily_total', 'Date'),
                '### Monthly revenue timeline': ('monthly_total', 'Month')}
    active = None
    for line_no, line in enumerate(lines, 1):
        if line.startswith('#'):
            active = None
            if line in sections:
                aggregation, column = sections[line]
                if any(t['aggregation'] == aggregation for t in result['tables']):
                    raise ValueError('Repeated revenue table section')
                active = dict(aggregation=aggregation, heading=line[4:], date_column=column,
                              rows=[], header_seen=False)
                result['tables'].append(active)
            continue
        if active is None or not line.startswith('|'):
            continue
        cells = [x.strip() for x in line.strip().strip('|').split('|')]
        if cells == [active['date_column'], 'Verified revenue']:
            active['header_seen'] = True
            continue
        if all(re.fullmatch(r':?-+:?', c) for c in cells):
            continue
        if not active['header_seen'] or len(cells) != 2:
            raise ValueError('Unexpected public revenue table structure')
        period, raw = cells
        pattern = r'20\d{2}-\d{2}-\d{2}' if active['aggregation'] == 'daily_total' else r'20\d{2}-\d{2}'
        if not re.fullmatch(pattern, period):
            raise ValueError('Revenue table requires explicit ISO periods')
        try:
            day = date.fromisoformat(period if len(period) == 10 else period + '-01')
        except ValueError as e:
            raise ValueError('Invalid table date') from e
        if active['rows'] and period <= active['rows'][-1]['period']:
            raise ValueError('Duplicate or unordered table dates')
        if day > sync_date:
            raise ValueError('Revenue table contains a future period relative to its sync time')
        row = dict(period=period, quote=line, source=url, source_line=line_no,
                   source_sha256=digest, value=None, low=None, high=None, currency='$',
                   partial=(day == sync_date if len(period) == 10 else period == sync_date.strftime('%Y-%m')))
        amount = re.fullmatch(r'\$((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)', raw)
        if amount:
            row['value'] = float(amount[1].replace(',', ''))
            if not math.isfinite(row['value']):
                raise ValueError('Nonfinite public amount')
            precision = 10 ** (-len(amount[1].split('.')[1])) if '.' in amount[1] else 1
            row['low'], row['high'] = row['value'] - precision / 2, row['value'] + precision / 2
            row['status'] = 'partial_period_excluded' if row['partial'] else 'dated_observation'
        else:
            row['status'] = 'unreadable_amount'
        active['rows'].append(row)
        result['decisions'].append(dict(period=period, aggregation=active['aggregation'],
                                       status=row['status'], source_line=line_no))
    if not result['tables'] or not any(t['rows'] for t in result['tables']):
        raise ValueError('No supported public revenue table found')
    return result


def fetch_profile(url, output, session=None):
    url = profile_url(url)
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    response = (session or requests.Session()).get(
        url, timeout=30, stream=True, allow_redirects=False,
        headers={'User-Agent': 'ChartRecover/0.1 (public chart research)'})
    try:
        if response.status_code != 200:
            raise RuntimeError(f'Public profile unavailable (HTTP {response.status_code}); no redirect or authenticated fallback attempted')
        content = bytearray()
        for chunk in response.iter_content(65536):
            content.extend(chunk)
            if len(content) > 500_000:
                raise ValueError('Public profile exceeds 500KB')
        text = content.decode('utf-8')
        result = parse_profile(text, url, datetime.now(timezone.utc).isoformat())
        (out / 'profile.md').write_bytes(content)
        (out / 'profile.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
        return result
    finally:
        response.close()
