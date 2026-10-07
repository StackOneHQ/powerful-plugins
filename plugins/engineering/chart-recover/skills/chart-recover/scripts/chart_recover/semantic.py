"""Conservative, inspectable binding of dated public claims to chart marks.

This is a deliberately bounded grammar, not general language understanding.
Every rejected claim keeps its reasons. Chart identity and the visible x-axis
need provenance; a matching shape, nearby number or document rank is not proof.
"""
from __future__ import annotations
import calendar
import hashlib
import math
import re
from datetime import date
from urllib.parse import urlsplit
import numpy as np

MONEY = re.compile(r'(?P<currency>US\$|USD\s*\$?|EUR\s*€?|GBP\s*£?|[$€£])\s*'
                   r'(?P<amount>\d[\d,]*(?:\.\d+)?)\s*(?P<suffix>[kmb])?(?!\w|[.,]\d)', re.I)
METRICS = {
    'mrr': r'\b(?:MRR|monthly recurring revenue)\b',
    'arr': r'\b(?:ARR|annual recurring revenue)\b',
    'revenue': r'\b(?:revenue|sales)\b',
    'users': r'\busers\b', 'customers': r'\bcustomers\b',
}
MONTHS = {v.lower(): k for k in range(1, 13) for v in (calendar.month_name[k], calendar.month_abbr[k])}
MONTH_PATTERN = '|'.join(sorted(MONTHS, key=len, reverse=True))
TARGET = re.compile(r'\b(?:target|goal|aim|aiming|hope|hoping|forecast|projected|projection|'
                    r'expect|expected|will|would|could|should|next up|on track|road to)\b', re.I)
NON_TOTAL = re.compile(r'\b(?:increase|increased|decrease|decreased|grew by|up by|down by|'
                       r'added|lost|churned|difference|per customer|per user|per seat|ARPU|average|refund)\b', re.I)


def _norm(value):
    return re.sub(r'\W+', '', str(value)).casefold()


def _period(text, published_at=None):
    """Return a single explicit period, or a disclosed inference, never a guess."""
    found = []
    for m in re.finditer(r'\b(20\d{2})-(0[1-9]|1[0-2])(?:-([0-3]\d))?\b', text):
        try:
            day = int(m[3]) if m[3] else 1
            date(int(m[1]), int(m[2]), day)
            found.append((m[0], 'explicit'))
        except ValueError:
            return None, 'invalid_date'
    pattern = rf'\b(?:(\d{{1,2}})\s+)?({MONTH_PATTERN})\.?\s*(?:(\d{{1,2}}),?\s+)?(20\d{{2}})?\b'
    for m in re.finditer(pattern, text, re.I):
        month = MONTHS[m[2].lower()]
        day = m[1] or m[3]
        year = int(m[4]) if m[4] else None
        basis = 'explicit'
        if year is None:
            if not published_at:
                return None, 'missing_year'
            try:
                published = date.fromisoformat(published_at[:10])
            except (ValueError, TypeError):
                return None, 'invalid_publication_date'
            year = published.year - (month > published.month)
            basis = 'most_recent_named_month_before_publication'
        try:
            value = date(year, month, int(day) if day else 1)
        except ValueError:
            return None, 'invalid_date'
        found.append((value.isoformat() if day else value.strftime('%Y-%m'), basis))
    unique = {p for p, _ in found}
    if len(unique) > 1:
        return None, 'multiple_periods'
    if found:
        return found[0]
    if published_at and re.search(r'\b(?:today|currently|now|just hit|just crossed)\b', text, re.I):
        try:
            return date.fromisoformat(published_at[:10]).isoformat(), 'publication_day_for_current_claim'
        except (TypeError, ValueError):
            return None, 'invalid_publication_date'
    return None, 'missing_period'


def parse_document(document, entity=None, aliases=()):
    """Extract literal monetary leads; callers can inspect every decision.

    Entity metadata is used only when accompanied by entity_source provenance.
    A bare dollar sign stays '$': it is not silently converted into USD.
    """
    text = document.get('text', document.get('text_excerpt', ''))
    source = document.get('url', document.get('source', ''))
    claims = []
    names = [x for x in (entity, *aliases) if x]
    for clause in re.split(r'(?<=[.!?])\s+|[;\n]+', text):
        money = list(MONEY.finditer(clause))
        if not money:
            continue
        metric_hits = []
        # Suppress the word 'revenue' inside the two recurring-revenue phrases.
        metric_text = re.sub(METRICS['mrr'], ' MRR ', clause, flags=re.I)
        metric_text = re.sub(METRICS['arr'], ' ARR ', metric_text, flags=re.I)
        for key, pattern in METRICS.items():
            if re.search(pattern, metric_text, re.I):
                metric_hits.append(key)
        if not metric_hits and re.search(r'\b(?:made|generated|earned)\b', clause, re.I):
            metric_hits = ['revenue']
        metric = metric_hits[0] if len(metric_hits) == 1 else None
        claim_entity, entity_basis = None, None
        if any(re.search(r'(?<!\w)' + re.escape(n) + r'(?!\w)', clause, re.I) for n in names):
            claim_entity, entity_basis = entity, 'literal_name_in_clause'
        if document.get('entity') and document.get('entity_source'):
            claim_entity, entity_basis = document['entity'], document['entity_source']
        period, period_basis = _period(clause, document.get('created_at'))
        aggregation = ('snapshot' if metric in ('mrr', 'arr', 'users', 'customers') else
                       'cumulative' if re.search(r'\b(?:all[- ]time|lifetime|cumulative|since launch)\b', clause, re.I) else
                       'monthly_total' if metric == 'revenue' and period and len(period) == 7 else None)
        for m in money:
            multiplier = {'': 1, 'k': 1000, 'm': 1e6, 'b': 1e9}[(m['suffix'] or '').lower()]
            amount = float(m['amount'].replace(',', '')) * multiplier
            decimals = len(m['amount'].split('.')[1]) if '.' in m['amount'] else 0
            precision = multiplier * 10**(-decimals)
            token = m['currency'].upper().strip()
            currency = 'USD' if token.startswith(('US$', 'USD')) else 'EUR' if token.startswith(('EUR', '€')) else 'GBP' if token.startswith(('GBP', '£')) else '$'
            before, after = clause[:m.start()], clause[m.end():]
            operator = ('lower_bound' if re.search(r'\b(?:over|above|passed|crossed|more than|at least|past)\s*$', before, re.I) or re.match(r'\s*\+', after) else
                        'upper_bound' if re.search(r'\b(?:under|below|less than|at most)\s*$', before, re.I) else
                        'approximate' if re.search(r'\b(?:about|around|roughly|approximately|nearly|almost)\s*$', before, re.I) else 'reported')
            issues = []
            if len(money) != 1: issues.append('multiple_amounts_in_clause')
            if len(metric_hits) != 1: issues.append('missing_or_ambiguous_metric')
            if TARGET.search(clause): issues.append('target_or_forecast')
            if NON_TOTAL.search(clause): issues.append('change_or_unit_amount_not_total')
            if re.search(r'\b(?:net|gross|adjusted|booked|recognized|annualized|run[- ]rate)\b',clause,re.I):
                issues.append('metric_definition_qualifier_needs_review')
            if re.search(r'\b(?:valuation|funding|profit|expense|cost|burn|GMV|bookings)\b',clause,re.I):
                issues.append('other_financial_measure_in_clause')
            if re.search(r'\b(?:their|competitor|portfolio|combined|across|versus|compared|says|said)\b',clause,re.I):
                issues.append('entity_relationship_needs_review')
            if re.search(r'\b(?:not|never|wasn.t|isn.t|didn.t|incorrect|false)\b', clause, re.I): issues.append('negation_or_disputed_claim')
            if re.search(r'[-−(]\s*$',before) or re.match(r'\s*[-−]',m['amount']): issues.append('signed_amount_needs_review')
            integer=m['amount'].split('.')[0].rstrip(',')
            if ',' in integer and not re.fullmatch(r'\d{1,3}(?:,\d{3})+',integer): issues.append('ambiguous_number_format')
            if not math.isfinite(amount): issues.append('nonfinite_amount')
            if not claim_entity: issues.append('entity_not_bound')
            if not period: issues.append(period_basis)
            if operator != 'reported': issues.append(operator + '_not_point_value')
            if not aggregation: issues.append('aggregation_not_bound')
            if urlsplit(source).scheme not in ('http', 'https') or not urlsplit(source).hostname:
                issues.append('missing_public_source_url')
            claim = dict(value=amount, currency=currency, metric=metric, aggregation=aggregation,
                         entity=claim_entity, entity_basis=entity_basis, period=period, period_basis=period_basis,
                         operator=operator, reported_precision=precision, abbreviated=bool(m['suffix']),
                         source=source, quote=clause.strip(), matched=False, issues=issues,
                         status='lead_requires_metric_period_and_point_match')
            claim['id'] = hashlib.sha256((source + '\n' + clause + '\n' + str(m.start())).encode()).hexdigest()[:20]
            claims.append(claim)
    return claims


def _coordinate(series, period, context):
    """Map a date to observed marks; never read a truth table or hidden values."""
    points = series['points']
    periods = context.get('periods')
    if periods is not None:
        if not context.get('period_source'): return None, 'missing_period_axis_provenance'
        if len(periods) != len(points) or len(set(periods)) != len(periods): return None, 'period_mark_count_or_uniqueness_mismatch'
        if period not in periods: return None, 'period_not_on_chart'
        i = periods.index(period)
        return dict(pixel=series['coordinates'][i], point_index=i, period=period,
                    method='unique_period_to_mark', axis_source=context['period_source']), None
    axis = context.get('time_axis', {})
    ticks = axis.get('ticks', [])
    if not axis.get('source') or axis.get('scale') != 'calendar_days' or len(ticks) < 2:
        return None, 'missing_verified_time_axis'
    if series['kind'] not in ('line', 'area'): return None, 'calendar_interpolation_requires_single_line_or_area'
    try:
        days = np.array([date.fromisoformat(t['date']).toordinal() for t in ticks], float)
        xs = np.array([float(t['pixel_x']) for t in ticks])
        day = date.fromisoformat(period).toordinal()
    except (ValueError, KeyError, TypeError):
        return None, 'time_axis_requires_exact_iso_days'
    if not np.isfinite(xs).all() or np.any(np.diff(days) <= 0) or np.any(np.diff(xs) <= 0): return None, 'nonmonotonic_time_axis'
    coef = np.polyfit(days - days[0], xs, 1)
    x_error = float(axis.get('pixel_error', 2))
    if not np.isfinite(x_error) or x_error < 0: return None, 'invalid_time_axis_pixel_error'
    if np.max(np.abs(np.polyval(coef, days-days[0])-xs)) > x_error: return None, 'nonlinear_time_axis'
    if not days[0] <= day <= days[-1]: return None, 'period_not_on_chart'
    x = float(np.polyval(coef, day-days[0]))
    px = np.array([p['x'] for p in points]); py = np.array(series['coordinates'])
    if np.any(np.diff(px) <= 0): return None, 'nonmonotonic_trace'
    if x < px[0]-x_error or x > px[-1]+x_error: return None, 'date_outside_observed_trace'
    index = min(max(int(np.searchsorted(px, x)), 1), len(px)-1)
    if px[index]-px[index-1] > max(3, np.median(np.diff(px))*2.5): return None, 'trace_gap_at_date'
    y = float(np.interp(x, px, py))
    y_error = max(abs(float(np.interp(x+delta, px, py))-y) for delta in (-x_error, x_error))
    return dict(pixel=y, pixel_x=x, period=period, alignment_pixel_error=y_error,
                method='calendar_days_interpolation', axis_source=axis['source']), None


def bind_documents(documents, geometry, context, *, pixel_error=2.5):
    """Return accepted anchors and a full rejection ledger, without silent repair."""
    from .growth import derive_previous_month_claims
    claims, decisions, anchors, seen, growth_decisions = [], [], [], set(), []
    for doc in documents:
        direct=parse_document(doc, context.get('entity'), context.get('aliases', []))
        growth=derive_previous_month_claims(doc,direct)
        growth_decisions.extend(growth['decisions'])
        for claim in direct+growth['claims']:
            if claim['id'] in seen: continue
            seen.add(claim['id']); claims.append(claim)
            reasons = list(claim['issues'])
            if geometry.get('quality_issues'): reasons.append('geometry_needs_review')
            if not context.get('source'): reasons.append('missing_chart_identity_provenance')
            for key in ('entity', 'metric', 'currency', 'aggregation'):
                if not context.get(key) or _norm(claim.get(key)) != _norm(context.get(key)):
                    reasons.append(key + '_mismatch')
            if claim['period_basis'] != 'explicit' and not context.get('allow_inferred_periods', False):
                reasons.append('inferred_period_needs_review')
            if claim['abbreviated'] and context.get('rounding_policy') != 'nearest':
                reasons.append('abbreviated_amount_needs_rounding_policy')
            selected = [s for s in geometry['series'] if s['id'] == context.get('series')]
            if len(selected) != 1: reasons.append('series_not_explicitly_bound')
            elif selected[0]['kind'].startswith('stacked'): reasons.append('stack_boundary_semantics_need_review')
            mapping = None
            if not reasons:
                mapping, issue = _coordinate(selected[0], claim['period'], context)
                if issue: reasons.append(issue)
            decision = dict(claim_id=claim['id'], source=claim['source'], period=claim['period'],
                            status='rejected' if reasons else 'accepted', reasons=list(dict.fromkeys(reasons)))
            if not reasons:
                # Abbreviations use an explicitly chosen rounding assumption.
                # Unabbreviated disclosures are treated as their reported numbers.
                half = claim['reported_precision']/2 if claim['abbreviated'] else 0.
                anchor = dict(pixel=mapping['pixel'], low=claim.get('interval_low',claim['value']-half), high=claim.get('interval_high',claim['value']+half),
                              pixel_error=pixel_error+mapping.get('alignment_pixel_error', 0),
                              source=claim['source'], series=selected[0]['id'], matched=True,
                              claim_id=claim['id'], correspondence=mapping,
                              assumptions=['Disclosure is truthful and describes the chart context.'])
                if half: anchor['assumptions'].append('Abbreviated value was rounded to nearest displayed precision.')
                if claim['period_basis'] != 'explicit': anchor['assumptions'].append(claim['period_basis'])
                if claim.get('derivation'):
                    anchor['derivation']=claim['derivation']
                    anchor['assumptions'].extend(claim['derivation_assumptions'])
                anchors.append(anchor); decision['correspondence'] = mapping
            decisions.append(decision)
    return dict(claims=claims, decisions=decisions, anchors=anchors,growth_decisions=growth_decisions,
                policy='Explicit identity/metric/currency/aggregation/series and dated x alignment; source truth remains conditional.')
