"""Outcome-blind enrollment and immutable successor chronology."""
import datetime as dt
import sqlite3
import re
from .safety import canonical, require, sha

def consecutive(weeks):
    require(all(re.fullmatch(r'[0-9]{4}-W[0-9]{2}',w) for w in weeks),'ISO_WEEK_FORMAT')
    starts=sorted({dt.date.fromisocalendar(int(w[:4]),int(w[-2:]),1) for w in weeks})
    run=best=0;previous=None
    for d in starts:
        run=run+1 if previous is not None and (d-previous).days==7 else 1
        best=max(best,run);previous=d
    return best

def qualifying(records):
    model=[r for r in records if r['kind']=='REOPEN' and r['entry'].get('eligible') and r['feature'].get('model_side')]
    dates={r['date'] for r in model};weeks={r['iso'] for r in model};classes={r['class'] for r in model}
    return {'model_entry_support':len(model),'paired_endpoints':sum(bool(r.get('_native_accounting_context',{}).get('paired_reference')) for r in model),'censored':sum(not r.get('_native_accounting_context',{}).get('paired_reference') for r in model),'dates':len(dates),'weeks':len(weeks),'consecutive_weeks':consecutive(weeks),'classes':len(classes),'gate_pass':len(model)>=48 and len(dates)>=12 and consecutive(weeks)>=3 and len(classes)>=2,'gate':'MIN48_EXANTE_12_DATES_3_CONSECUTIVE_ISO_WEEKS_2_CLASSES;SUPPORT_NOT_POWER','alpha_certified':False}

def lineage(record):
    required=('id','first_seen','design_sha256','baseline_sha256','split','feature_max_time','decision_time','outcome_time','dependence')
    require(all(k in record for k in required),'LINEAGE_MISSING')
    require(all(re.fullmatch(r'[a-f0-9]{64}',record[k]) for k in ('design_sha256','baseline_sha256')),'DESIGN_DIGEST_REQUIRED')
    require(record['feature_max_time']<=record['decision_time']<record['outcome_time'],'FUTURE_LEAKAGE')
    require(record['first_seen']<=record['decision_time'],'FIRST_SEEN_AFTER_OUTCOME')
    dev,hold=record['split']['development'],record['split']['confirmation']
    require(all(a<b for a,b in dev+hold),'SPLIT_RANGE')
    matrix=[{'development_index':i,'confirmation_index':j,'overlap':max(0,min(b,d)-max(a,c)),'restricted_use':'DEVELOPMENT_IF_REUSED'} for i,(a,b) in enumerate(dev) for j,(c,d) in enumerate(hold)]
    require(not any(r['overlap'] for r in matrix),'CONTAMINATED_HOLDOUT')
    require(bool(record['dependence']),'DEPENDENCE_UNKNOWN')
    return {**record,'overlap_matrix':matrix}

class CandidateLedger:
    def __init__(self,path):
        self.db=sqlite3.connect(path);self.db.execute('CREATE TABLE IF NOT EXISTS proposal(id TEXT PRIMARY KEY,h TEXT,payload BLOB)');self.db.commit()
    def append(self,record):
        record=lineage(record);raw=canonical(record);h=sha(raw)
        old=self.db.execute('SELECT h FROM proposal WHERE id=?',(record['id'],)).fetchone()
        require(old is None or old[0]==h,'IMMUTABLE_FIRST_SEEN')
        with self.db:self.db.execute('INSERT OR IGNORE INTO proposal VALUES(?,?,?)',(record['id'],h,raw))
        return h

def bijection(inputs,outputs):
    def keyed(rows):
        d={r['id']:r for r in rows};require(len(d)==len(rows),'PARITY_DUPLICATE');return d
    a,b=keyed(inputs),keyed(outputs)
    require(set(a)==set(b),'PARITY_ID_MISMATCH')
    if not a:return {'state':'UNSUPPORTED_EMPTY','n':0}
    supported=0
    for i in a:
        if a[i].get('valid') is False:
            require(b[i].get('abstain') is True,'INVALID_VECTOR_NOT_ABSTAINED');continue
        require(abs(a[i]['value']-b[i]['value'])<=1e-9,'PARITY_NUMERIC_MISMATCH');supported+=1
    return {'state':'PASS' if supported else 'UNSUPPORTED_ALL_ABSTAIN','n':supported}

def population(name,ids,reason):
    require(name in {'CATALOG5326','PREFILTER1576','ELIGIBLE1562','PRIMARY145','LEGACY349'},'POPULATION_UNKNOWN')
    require(len(ids)==len(set(ids)) and bool(reason),'POPULATION_MEMBERSHIP')
    return {'population':name,'n':len(ids),'membership_sha256':sha(canonical(sorted(ids))),'reason':reason}
