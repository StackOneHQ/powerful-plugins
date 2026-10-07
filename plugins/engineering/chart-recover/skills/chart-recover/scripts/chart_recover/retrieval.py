"""Bounded public-evidence retrieval from a saved corpus or the official X API."""
from __future__ import annotations
import json
import re
from pathlib import Path
from .semantic import METRICS


def plan_queries(context):
    """Queries contain public chart identity only; no secrets or local file data."""
    entity = context.get('entity', '').strip()
    metric = context.get('metric', '')
    if not entity or metric not in METRICS: return []
    # Quote control characters cannot become search operators.
    entity = re.sub(r'["\r\n]', ' ', entity)
    terms = {'mrr': '(MRR OR "monthly recurring revenue")',
             'arr': '(ARR OR "annual recurring revenue")',
             'revenue': '(revenue OR sales OR made)',
             'users': 'users', 'customers': 'customers'}[metric]
    return [f'"{entity}" {terms} -is:retweet']


class CorpusRetriever:
    """Search cached source text. Ranking is retrieval, not evidence acceptance."""
    def __init__(self, documents):
        self.documents = list(documents)

    @classmethod
    def from_jsonl(cls, path):
        with Path(path).open() as f:
            return cls(json.loads(line) for line in f if line.strip())

    def retrieve(self, context, limit=30):
        if not 1 <= limit <= 100: raise ValueError('retrieval limit must be 1..100')
        names = [str(x).casefold() for x in [context.get('entity'), *context.get('aliases', [])] if x]
        if not names: return []
        found, seen = [], set()
        for doc in self.documents:
            text = doc.get('text', doc.get('text_excerpt', ''))
            content = text.casefold()
            entity_match = any(re.search(r'(?<!\w)' + re.escape(n) + r'(?!\w)', content) for n in names)
            metadata_match = str(doc.get('entity', '')).casefold() in names and doc.get('entity_source')
            if not (entity_match or metadata_match): continue
            source = doc.get('url', doc.get('source', ''))
            if not source or (source, text) in seen: continue
            seen.add((source, text))
            metric = context.get('metric', '')
            score = 2 + bool(re.search(METRICS.get(metric, r'(?!)'), content, re.I))
            record = dict(doc, text=text, url=source, retrieval_score=score, retrieval_method='local_public_corpus')
            found.append(record)
        return sorted(found, key=lambda d: (-d['retrieval_score'], d['url']))[:limit]


class XRetriever:
    """Live recent public search; requires X API access, never bypasses barriers."""
    def __init__(self, collector=None):
        if collector is None:
            from .collect import XCollector
            collector = XCollector()
        self.collector = collector

    def retrieve(self, context, limit=30):
        if not 1 <= limit <= 100: raise ValueError('retrieval limit must be 1..100')
        found = []
        for query in plan_queries(context):
            for post in self.collector.search(query, max_pages=1):
                found.append(dict(post, retrieval_method='x_api_recent_search', retrieval_query=query))
                if len(found) >= limit: return found
        return found
