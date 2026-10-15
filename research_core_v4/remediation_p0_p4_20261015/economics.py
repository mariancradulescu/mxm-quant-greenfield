"""Offline controls and preserved-result classification. No new PnL computation."""
import json
import math
import sqlite3
from .safety import require, canonical, sha

class EquityLedger:
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        self.db.executescript('CREATE TABLE IF NOT EXISTS account(id INTEGER PRIMARY KEY,balance REAL,equity REAL,last_time INTEGER);CREATE TABLE IF NOT EXISTS position(id TEXT PRIMARY KEY,risk REAL,margin REAL,side INTEGER,units REAL,status TEXT,unrealized REAL DEFAULT 0);CREATE TABLE IF NOT EXISTS cashflow(t INTEGER,amount REAL,kind TEXT);CREATE TABLE IF NOT EXISTS event(t INTEGER,kind TEXT,id TEXT,payload TEXT);')
        self.db.execute('INSERT OR IGNORE INTO account VALUES(1,200,200,-1)');self.db.commit()
    def apply(self,e):
        # Costs/FX/funding/gap must be explicit finite controls, including known zero.
        required=('fx','commission','spread','slippage','funding','stop_gap')
        require(all(k in e and isinstance(e[k],(int,float)) and not isinstance(e[k],bool) and math.isfinite(e[k]) for k in required),'COST_OR_FX_UNKNOWN')
        require(e['fx']>0 and all(e[k]>=0 for k in required if k!='fx'),'COST_RANGE')
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            balance,equity,last=self.db.execute('SELECT balance,equity,last_time FROM account').fetchone()
            require(type(e['t']) is int and e['t']>=last,'CHRONOLOGY_REJECTED')
            require(math.isfinite(equity) and equity>0,'EQUITY_INVALID')
            cost=sum(e[k] for k in required if k!='fx')*e['fx']
            if e['kind'] in ('OPEN','PENDING'):
                require(all(isinstance(e[k],(int,float)) and not isinstance(e[k],bool) and math.isfinite(e[k]) for k in ('risk','margin','units','step')),'NONFINITE_TICKET')
                require(e['side'] in (-1,1) and type(e['side']) is int and e['risk']>=0 and e['margin']>=0 and e['units']>0 and e['step']>0 and abs(e['units']/e['step']-round(e['units']/e['step']))<1e-9,'TICKET_LATTICE')
                risk,margin=self.db.execute('SELECT coalesce(sum(risk),0),coalesce(sum(margin),0) FROM position').fetchone()
                next_equity=equity-cost
                require(risk+e['risk']<=.01*next_equity and margin+e['margin']<=.4*next_equity and next_equity-margin-e['margin']>=.6*next_equity,'AGGREGATE_CAPITAL_REJECTED')
                self.db.execute('INSERT INTO position(id,risk,margin,side,units,status) VALUES(?,?,?,?,?,?)',(e['id'],e['risk'],e['margin'],e['side'],e['units'],e['kind']))
                balance-=cost;equity=next_equity
            elif e['kind']=='CLOSE':
                require(isinstance(e.get('gross'),(int,float)) and math.isfinite(e['gross']),'EXIT_UNKNOWN')
                require(e.get('fill_confirmed') is True,'FILL_UNKNOWN')
                require(self.db.execute('DELETE FROM position WHERE id=?',(e['id'],)).rowcount==1,'POSITION_UNKNOWN')
                # Fixture closes are account-currency gross; no fabricated market outcomes.
                balance+=e['gross']-cost;equity=balance+self.db.execute('SELECT coalesce(sum(unrealized),0) FROM position').fetchone()[0]
            elif e['kind']=='MARK':
                require(isinstance(e.get('unrealized'),(int,float)) and math.isfinite(e['unrealized']) and e.get('fresh') is True,'MARK_UNKNOWN')
                require(self.db.execute('UPDATE position SET unrealized=? WHERE id=?',(e['unrealized'],e['id'])).rowcount==1,'MARK_POSITION_UNKNOWN')
                balance-=cost;equity=balance+self.db.execute('SELECT coalesce(sum(unrealized),0) FROM position').fetchone()[0]
            elif e['kind']=='DEPOSIT':
                require(False,'DEPOSITS_OUT_OF_EUR200_SCOPE')
            else:require(False,'EVENT_UNKNOWN')
            require(math.isfinite(balance) and math.isfinite(equity) and equity>0,'EQUITY_INVALID')
            self.db.execute('UPDATE account SET balance=?,equity=?,last_time=?',(balance,equity,e['t']))
            self.db.execute('INSERT INTO event VALUES(?,?,?,?)',(e['t'],e['kind'],e['id'],canonical(e).decode()))
        return {'balance':balance,'equity':equity,'NET_certified_executable':None,'alpha_certified':False}
    def batch(self,events):
        # deterministic close-before-open at equal timestamps; stable IDs.
        for e in sorted(events,key=lambda x:(x['t'],0 if x['kind']=='CLOSE' else 1,x['id'])):self.apply(e)

class EconomicReader:
    def __init__(self,path):
        self.db=sqlite3.connect(path,timeout=5)
        self.db.execute('CREATE TABLE IF NOT EXISTS evaluation(g INTEGER,h TEXT,result BLOB,PRIMARY KEY(g,h))');self.db.commit()
    def evaluate(self,checkpoint,receipt,accepted=None):
        require(checkpoint['generation']==receipt['generation'] and checkpoint['journal_sha256']==receipt['journal_sha256'],'STALE_CHECKPOINT')
        require(receipt.get('state')=='COMMITTED' and receipt.get('owner_readback') is True and receipt.get('writer_active') is False,'CHECKPOINT_NOT_OWNER_COMMITTED')
        require(type(receipt.get('sequence')) is int and receipt['sequence']>=1,'SEQUENCE_INVALID')
        g,h=checkpoint['generation'],checkpoint['journal_sha256']
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            prior=self.db.execute('SELECT result FROM evaluation WHERE g=? AND h=?',(g,h)).fetchone()
            if prior:return json.loads(prior[0])
            result=classify(accepted or {})
            result.update(generation=g,journal_sha256=h,sequence=receipt['sequence'],broker_requests=0,collection_write=False)
            self.db.execute('INSERT INTO evaluation VALUES(?,?,?)',(g,h,canonical(result)))
            return result

def classify(accepted):
    outcome=accepted.get('outcome')
    require(accepted.get('outcomes_read') is True or outcome is None,'OUTCOME_NOT_READ')
    net=None;state='SUPPORT_ONLY'
    if accepted.get('data_blocked'):state='DATA_BLOCKED'
    elif accepted.get('cost_untradable'):state='COST_UNTRADABLE'
    elif outcome is not None:
        require(accepted.get('authenticated') is True and accepted.get('previously_accepted') is True,'UNACCEPTED_OUTCOME')
        require(type(outcome) in (float,int) and math.isfinite(outcome),'OUTCOME_NONFINITE')
        net=outcome;state='NEGATIVE_ACCEPTED' if outcome<=0 else 'ECONOMIC_REFERENCE_AVAILABLE'
    return {'status':state,'NET_reference':net,'NET_certified_executable':None,'new_NET':None,'outcomes_read':bool(outcome is not None),'qualification':'QUALIFICATION_REQUIRED','alpha_certified':False,'HARD21':False,'resolved_unknown':accepted.get('resolved_unknown'),'evidence_source_sha256':accepted.get('source_sha256')}

def optimal_count_bound(tickets):
    # Cardinality is a safe loose upper bound, never claim greedy is optimal.
    return len(tickets)
