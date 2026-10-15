"""Compact immutable encrypted releases with one durable commit pointer."""
import os,json,time,pathlib,subprocess
from collections import Counter
from .preserve_stop_v2 import api,complete_assets
from research_core_v4.full_native_frontier_20261014_v1 import runner_v1 as v1
from . import archive_v2 as ar
E=v1.E;need=v1.need;encode=v1.encode
ROOT_TAG="mxm-native-frontier-repaired-20261014-v2"
def get_or_create(tag,head):
 try:return api("releases/tags/"+tag)
 except Exception as exc:
  import urllib.error
  if not isinstance(exc,urllib.error.HTTPError) or exc.code!=404:raise
 return api("releases","POST",{"tag_name":tag,"target_commitish":head,"name":"MXM immutable native frontier encrypted shards","prerelease":True,"body":json.dumps({"state":"UNCOMMITTED","synthetic":False})})
class RotatingStore(v1.FrontierStore):
 def __init__(self,head,key,public,tmp,tag=ROOT_TAG,limit=750):
  super().__init__(head,key,public,tmp,"real");self.tag=tag;self.limit=limit
  self.anchor=get_or_create(tag,head);body=json.loads(self.anchor["body"])
  self.index=int(body.get("storage_index",0));self.release=get_or_create(tag+"-shard-"+str(self.index),head)
  self.count=len(complete_assets(self.release["id"]))
 def encrypted(self,value,name):
  if self.count>=self.limit:
   self.index+=1;self.release=get_or_create(self.tag+"-shard-"+str(self.index),self.head)
   self.count=len(complete_assets(self.release["id"]));need(self.count<self.limit,"ROTATED_RELEASE_FULL")
  name="r"+os.environ["GITHUB_RUN_ID"]+"-"+os.environ["GITHUB_JOB"].replace("_","-")+"-"+name
  meta=super().encrypted(value,name);meta["release_id"]=self.release["id"]
  self.count+=1;need(self.count<=self.limit,"ASSET_COUNT_LIMIT");return meta
 def commit(self,body):
  body.update(storage_index=self.index,storage_release=self.release["id"],max_assets_per_release=self.limit)
  api("releases/"+str(self.anchor["id"]),"PATCH",{"body":json.dumps(body,sort_keys=True)})
  self.anchor=api("releases/"+str(self.anchor["id"]));need(json.loads(self.anchor["body"])==body,"ANCHOR_COMMIT_READBACK")
def track(db):
 db.executescript("""
 CREATE TABLE IF NOT EXISTS wire(s INTEGER,k TEXT,a INTEGER,b INTEGER,z TEXT,h TEXT,PRIMARY KEY(s,k,a,b));
 CREATE TEMP TABLE IF NOT EXISTS delta_bar(s INTEGER,t INTEGER,PRIMARY KEY(s,t));
 CREATE TEMP TABLE IF NOT EXISTS delta_tick(s INTEGER,k TEXT,t INTEGER,p INTEGER,PRIMARY KEY(s,k,t,p));
 CREATE TEMP TABLE IF NOT EXISTS delta_span(s INTEGER,k TEXT,a INTEGER,b INTEGER,PRIMARY KEY(s,k,a,b));
 CREATE TEMP TABLE IF NOT EXISTS delta_wire(s INTEGER,k TEXT,a INTEGER,b INTEGER,PRIMARY KEY(s,k,a,b));
 CREATE TEMP TRIGGER IF NOT EXISTS track_bar AFTER INSERT ON main.bar BEGIN INSERT OR IGNORE INTO delta_bar VALUES(new.s,new.t); END;
 CREATE TEMP TRIGGER IF NOT EXISTS track_tick AFTER INSERT ON main.tick BEGIN INSERT OR IGNORE INTO delta_tick VALUES(new.s,new.k,new.t,new.p); END;
 CREATE TEMP TRIGGER IF NOT EXISTS track_span AFTER INSERT ON main.span BEGIN INSERT OR REPLACE INTO delta_span VALUES(new.s,new.k,new.a,new.b); END;
 CREATE TEMP TRIGGER IF NOT EXISTS track_span_update AFTER UPDATE ON main.span BEGIN INSERT OR REPLACE INTO delta_span VALUES(new.s,new.k,new.a,new.b); END;
 CREATE TEMP TRIGGER IF NOT EXISTS track_wire AFTER INSERT ON main.wire BEGIN INSERT OR REPLACE INTO delta_wire VALUES(new.s,new.k,new.a,new.b); END;
 """)
def delta(db,st):
 return {"schema":"mxm.native.compact.delta.v2","bars":db.execute("SELECT x.* FROM bar x JOIN delta_bar d USING(s,t) ORDER BY s,t").fetchall(),"ticks":db.execute("SELECT x.* FROM tick x JOIN delta_tick d USING(s,k,t,p) ORDER BY s,k,t,p").fetchall(),"spans":db.execute("SELECT x.* FROM span x JOIN delta_span d USING(s,k,a,b) ORDER BY s,k,a,b").fetchall(),"wire":db.execute("SELECT x.* FROM wire x JOIN delta_wire d USING(s,k,a,b) ORDER BY s,k,a,b").fetchall(),"records":{str(s):st["identity_records"][str(s)] for s in sorted(st.pop("_record_dirty_ids",set())) if str(s) in st["identity_records"]},"raw":st.pop("_raw",[]),"parent_ledger":st.get("ledger_head")}
def apply(db,data,st):
 db.execute('SAVEPOINT delta_apply')
 try:
  for sid,t,o,h,l,c,vol in data.get("bars",[]):ar.putbar(db,sid,t,[o,h,l,c,vol])
  db.executemany("INSERT OR IGNORE INTO tick VALUES(?,?,?,?)",data.get("ticks",[]))
  for row in data.get("spans",[]):ar.span(db,*row)
  for row in data.get("wire",[]):
   old=db.execute('SELECT * FROM wire WHERE s=? AND k=? AND a=? AND b=?',row[:4]).fetchone()
   need(old is None or tuple(old)==tuple(row),'WIRE_REPLAY_CONFLICT')
   if old is None:db.execute('INSERT INTO wire VALUES(?,?,?,?,?,?)',row)
  db.execute('RELEASE delta_apply')
 except BaseException:
  db.execute('ROLLBACK TO delta_apply');db.execute('RELEASE delta_apply');raise
 st.setdefault("identity_records",{}).update(data.get("records",{}))
def clear(db):
 for table in ("delta_bar","delta_tick","delta_span","delta_wire"):db.execute("DELETE FROM "+table)
 db.commit()
def compact(db,store,st):
 # Snapshots replace current restore references, while immutable ledger retains raw provenance.
 chunks=[];chunk={"bars":[],"ticks":[],"spans":[],"wire":[],"records":{}}
 for group in range(64):
  data={name:db.execute("SELECT * FROM "+table+" WHERE s%64=? ORDER BY s",(group,)).fetchall() for name,table in (("bars","bar"),("ticks","tick"),("spans","span"),("wire","wire"))}
  data["records"]={sid:r for sid,r in st["identity_records"].items() if int(sid)%64==group}
  if len(encode(chunk))+len(encode(data))>48*1024*1024 and any(chunk[n] for n in ("bars","ticks","spans","wire","records")):
   chunks.append(chunk);chunk={"bars":[],"ticks":[],"spans":[],"wire":[],"records":{}}
  for name in ("bars","ticks","spans","wire"):chunk[name].extend(data[name])
  chunk["records"].update(data["records"])
 chunks.append(chunk);refs=[]
 for idx,data in enumerate(chunks):
  need(len(encode(data))<120*1024*1024,"SNAPSHOT_BUNDLE_SIZE")
  refs.append(store.encrypted(json.loads(encode(data)),"snapshot-"+str(st["generation"])+"-"+str(idx)+".mxmenc"))
 st["snapshots_v2"]=refs;st["increments_v2"]=[];st["shards"]={};st["record_shards"]={}
def persist(db,store,st,label,groups=()):
 st.pop("_record_dirty",None)
 data=delta(db,st)
 if any(data[n] for n in ("bars","ticks","spans","wire","records","raw")):
  meta=store.encrypted(json.loads(encode(data)),"delta-"+str(st["generation"]+1)+"-"+label+".mxmenc")
  st.setdefault("increments_v2",[]).append(meta);st["ledger_head"]=meta
 st["generation"]+=1;st["last_run"]=int(os.environ["GITHUB_RUN_ID"]);st["last_job"]=os.environ["GITHUB_JOB"]
 if len(st.get("increments_v2",[]))>=100:compact(db,store,st)
 snapshot={key:value for key,value in st.items() if key!="identity_records" and not key.startswith("_")}
 snapshot["parent_checkpoint"]=st.get("last_checkpoint")
 meta=store.encrypted(json.loads(encode(snapshot)),"manifest-"+str(st["generation"])+"-"+label+".mxmenc")
 body={"schema":"mxm.native.frontier.repaired.public.v2","source_head":store.head,"state":st["phase"],"generation":st["generation"],"current_journal":meta,"identities_evaluated":st["identity_cursor"],"identities_total":len(st["eligible"]),"remaining":len(st["eligible"])-st["identity_cursor"],"new_requests":st["requests"],"coverage_states":ar.proof_table(db),"pending_request_count":len(st.get("pending_requests",[])),"pilot_executed":st.get("pilot") is not None,"candidate_qualification":v1.qualifying([e for r in st["identity_records"].values() for e in r.get("events",[])]),"cold_resume_count":len(st["resume_proofs"]),"old_run_terminal":True,"OWNER_READBACK_SUCCESS":True,"actual_orders":0,"actual_fills":0,"alpha_certified":False,"HARD21":False,"ledger_head":st.get("ledger_head"),"run_id":int(os.environ["GITHUB_RUN_ID"]),"job":os.environ["GITHUB_JOB"]}
 store.commit(body);st["last_checkpoint"]=meta;clear(db)
 print(json.dumps(body,sort_keys=True),flush=True);return meta
def restore(db,store):
 body=json.loads(store.anchor["body"]);st=store.restore(body["current_journal"]);st["identity_records"]={}
 for meta in st.get("shards",{}).values():apply(db,store.restore(meta),st)
 for meta in st.get("record_shards",{}).values():st["identity_records"].update(store.restore(meta)["records"])
 for meta in st.get("snapshots_v2",[]):apply(db,store.restore(meta),st)
 for meta in st.get("increments_v2",[]):apply(db,store.restore(meta),st)
 st["last_checkpoint"]=body["current_journal"];st["resume_proofs"].append({"state":"VERIFIED_OWNER_CROSS_RELEASE_COLD_PROCESS_RESUME","from_generation":st["generation"],"to_run":int(os.environ["GITHUB_RUN_ID"]),"to_job":os.environ["GITHUB_JOB"],"canonical_sha256":body["current_journal"]["canonical_sha256"]})
 track(db);clear(db)
 for req in st.pop("pending_requests",[]):
  ar.span(db,req["s"],req["k"],req["a"],req["b"],"UNCERTAIN_WIRE")
  st["uncertain_wire"].append(req)
 st["pending_requests"]=[]
 return st
def smoke(store):
 tag=ROOT_TAG+"-storage-smoke-"+os.environ["GITHUB_RUN_ID"]
 test=RotatingStore(store.head,store.key,store.public,store.tmp,tag,2);refs=[]
 for idx in range(3):refs.append(test.encrypted({"synthetic_validation":True,"index":idx,"no_market_data":True},"rotation-"+str(idx)+".mxmenc"))
 need(len({r["release_id"] for r in refs})==2,"ROTATION_NOT_EXERCISED")
 path=store.tmp/"rotation-locators.json";path.write_text(json.dumps(refs))
 # The key stays inside runner tmp; only locator JSON and a safe PASS exit are returned.
 cmd=["python3","-m","research_core_v4.critical_frontier_repair_20261014_v2.storage_v2","--cold-smoke",str(path),str(store.key)]
 need(subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=180).returncode==0,"INDEPENDENT_PROCESS_ROTATION_READBACK")
 return {"state":"VERIFIED_MACHINE_SIDE_ROTATION_AND_INDEPENDENT_COLD_PROCESS","synthetic_not_alpha":True,"capacity":2,"releases":sorted({r["release_id"] for r in refs}),"canonical_sha256":[r["canonical_sha256"] for r in refs]}
if __name__=="__main__":
 import sys,tempfile
 need(len(sys.argv)==4 and sys.argv[1]=="--cold-smoke","COLD_SMOKE_ARGS")
 with tempfile.TemporaryDirectory(dir=os.environ["RUNNER_TEMP"]) as td:
  store=v1.FrontierStore(os.environ["GITHUB_SHA"],pathlib.Path(sys.argv[3]),E.a.ROOT/E.w.old.PUBLIC_KEY,pathlib.Path(td),"real")
  for idx,ref in enumerate(json.loads(pathlib.Path(sys.argv[2]).read_text())):
   need(store.restore(ref)=={"synthetic_validation":True,"index":idx,"no_market_data":True},"COLD_SMOKE_VALUE")

