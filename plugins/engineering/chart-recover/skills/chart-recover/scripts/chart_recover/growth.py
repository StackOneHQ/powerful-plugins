"""Derive a prior monthly amount from an explicitly scoped growth disclosure.

This supplies a numerical constraint, not independent corroboration. The
current amount, metric, entity and month must already be bound by the text
reader. Both rounding intervals and the derivation are retained.
"""
import hashlib
import math
import re

GROWTH = re.compile(
    r'^\s*(?P<metric>monthly recurring revenue|annual recurring revenue|revenue|sales|MRR|ARR)'
    r'\s+(?:(?:was|is|has|had)\s+)?(?P<direction>up|down|grew|increased|decreased|rose|fell)'
    r'\s+(?:by\s+)?(?P<percent>\d+(?:\.\d+)?)\s*%\s+'
    r'(?P<comparison>(?:(?:on|from|versus|vs\.?|compared with|compared to)\s+(?:the\s+)?(?:last|previous)\s+month)'
    r'|month[- ]over[- ]month|MoM)\b', re.I)
DISPUTED = re.compile(r'\b(?:not|never|incorrect|false|mistake|correction|would|could|should|forecast|'
                      r'target|expect|projected|hypothetical|competitor|their|combined|portfolio)\b', re.I)


def previous_month(period):
    year,month=map(int,period.split('-'))
    if not 1<=month<=12 or year<1:raise ValueError('Invalid monthly period')
    year,month=(year-1,12) if month==1 else (year,month-1)
    if year<1:raise ValueError('Prior month is outside supported calendar')
    return f'{year:04d}-{month:02d}'


def previous_amount_interval(amount,precision,percent,direction):
    """Conservative interval division; percentage precision comes from text."""
    value=float(amount);half=float(precision)/2
    pct=float(percent);decimals=len(percent.split('.')[1]) if '.' in percent else 0
    pct_half=.5*10**-decimals
    if not all(math.isfinite(v) for v in (value,half,pct)) or value-half<=0 or half<0 or pct<0:
        raise ValueError('Need a finite positive amount and an unsigned percentage')
    sign=-1 if direction.lower() in ('down','decreased','fell') else 1
    factors=sorted(1+sign*p/100 for p in (pct-pct_half,pct+pct_half))
    if factors[0]<=0:raise ValueError('Percentage interval does not imply a positive finite prior amount')
    low=(value-half)/factors[1];high=(value+half)/factors[0]
    if not all(math.isfinite(v) for v in (low,high)):raise ValueError('Derived amount is not finite')
    return dict(value=value/(1+sign*pct/100),low=low,high=high,
                current_interval=[value-half,value+half],percentage_interval=[pct-pct_half,pct+pct_half],factor_interval=factors)


def derive_previous_month_claims(document,base_claims):
    """Accept a narrow, explicit month-over-month sentence; retain rejections."""
    from .semantic import _period
    text=document.get('text',document.get('text_excerpt',''));derived=[];decisions=[]
    for clause in re.split(r'(?<=[.!?])\s+|[;\n]+',text):
        match=GROWTH.match(clause)
        if not match:continue
        metric=match['metric'].lower()
        metric={'monthly recurring revenue':'mrr','annual recurring revenue':'arr','sales':'revenue'}.get(metric,metric)
        candidates=[c for c in base_claims if c.get('metric')==metric and not c.get('issues')
                    and c.get('operator')=='reported' and c.get('period') and len(c['period'])==7
                    and c.get('aggregation') in ('monthly_total','snapshot')]
        decision=dict(source=document.get('url',document.get('source','')),quote=clause.strip(),metric=metric,status='rejected',reasons=[])
        if DISPUTED.search(clause):decision['reasons'].append('Growth statement is qualified, disputed or about another entity.')
        if len(candidates)!=1:decision['reasons'].append('Need exactly one valid current monetary claim for this metric, entity and month in the same document.')
        # Other monetary claims for the metric would make the antecedent unclear,
        # even when they were rejected for missing dates or another issue.
        if len([c for c in base_claims if c.get('metric')==metric])!=1:
            decision['reasons'].append('Multiple monetary claims make the growth antecedent ambiguous.')
        if decision['reasons']:
            decisions.append(decision);continue
        current=candidates[0]
        explicit_period,period_basis=_period(clause,document.get('created_at'))
        years=re.findall(r'\b20\d{2}\b',clause)
        if (explicit_period and explicit_period!=current['period']) or period_basis in ('multiple_periods','invalid_date','missing_year') or any(y!=current['period'][:4] for y in years):
            decision['reasons'].append('An explicit date in the growth statement does not match the current monthly claim.')
            decisions.append(decision);continue
        try:
            interval=previous_amount_interval(current['value'],current['reported_precision'],match['percent'],match['direction'])
            period=previous_month(current['period'])
        except (ValueError,OverflowError) as error:
            decision['reasons'].append(str(error));decisions.append(decision);continue
        claim=dict(current,value=interval['value'],period=period,operator='derived_range',
                   interval_low=interval['low'],interval_high=interval['high'],
                   quote=current['quote']+'\n'+clause.strip(),
                   derivation=dict(operation='previous_month = current_month / (1 + signed_change)',
                                   current_claim_id=current['id'],current_period=current['period'],
                                   direction=match['direction'].lower(),percent=match['percent'],
                                   current_interval=interval['current_interval'],percentage_interval=interval['percentage_interval'],
                                   factor_interval=interval['factor_interval'],independent_evidence=False),
                   derivation_assumptions=['The stated monetary amount and percentage were rounded to their displayed precision.',
                                           'The explicit month-over-month statement refers to the single current amount for this metric in the document.',
                                           'The derived prior amount depends on the current disclosure; it is not independent corroboration.'])
        claim['id']=hashlib.sha256((current['id']+'\n'+clause+'\n'+period).encode()).hexdigest()[:20]
        derived.append(claim);decision.update(status='derived',claim_id=claim['id'],current_claim_id=current['id'],period=period)
        decisions.append(decision)
    return dict(claims=derived,decisions=decisions)
