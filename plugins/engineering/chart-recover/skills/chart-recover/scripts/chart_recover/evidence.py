"""Conservative claim discovery. A mention is a lead, not a chart anchor."""
import re
import numpy as np

MONEY=re.compile(r'(?P<currency>[$€£])\s*(?P<amount>\d[\d,]*(?:\.\d+)?)\s*(?P<suffix>[kKmMbB])?\b')
METRIC=re.compile(r'\b(MRR|ARR|revenue|users|customers|subscriptions|downloads)\b',re.I)


def claims_from_text(text,source,entity=None):
    claims=[]
    for m in MONEY.finditer(text):
        amount=float(m['amount'].replace(',',''))*{'':1,'k':1e3,'m':1e6,'b':1e9}[(m['suffix'] or '').lower()]
        context=text[max(0,m.start()-50):min(len(text),m.end()+60)]
        metric=METRIC.search(text[m.end():m.end()+25]) or METRIC.search(text[max(0,m.start()-30):m.start()])
        claims.append(dict(value=amount,currency=m['currency'],metric=metric[0].lower() if metric else None,
                           entity=entity,source=source,quote=context,matched=False,
                           status='lead_requires_metric_period_and_point_match'))
    for m in re.finditer(r'\b(\d+(?:\.\d+)?)\s*[x×]\b',text,re.I):
        claims.append(dict(ratio=float(m[1]),source=source,matched=False,status='relative_claim_not_absolute_anchor'))
    return claims


def match_reference(shape,candidates,*,top_k=5):
    """Rank candidate series by affine-invariant shape; this never establishes identity.

    Caller supplies aligned time windows. Time alignment/domain identity must
    be verified outside this scorer. Positive scale + translation only.
    """
    shape=np.asarray(shape,dtype=float)
    if len(shape)<4 or np.ptp(shape)==0:return []
    out=[];grid=np.linspace(0,1,len(shape));target=(shape-shape.mean())/shape.std()
    for candidate in candidates:
        values=np.asarray(candidate['values'],dtype=float)
        if len(values)<4 or not np.isfinite(values).all() or np.ptp(values)==0:continue
        v=np.interp(grid,np.linspace(0,1,len(values)),values);v=(v-v.mean())/v.std()
        corr=float(np.mean(v*target));err=float(np.sqrt(np.mean((v-target)**2)))
        out.append(dict(id=candidate['id'],source=candidate.get('source'),correlation=corr,
                        shape_rmse=err,status='candidate_only',
                        warning='Shape similarity is not identity or independent scale evidence.'))
    return sorted(out,key=lambda x:x['shape_rmse'])[:top_k]
