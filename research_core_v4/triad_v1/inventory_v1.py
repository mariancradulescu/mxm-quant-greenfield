"""Pure authoritative identity/provenance inventory; no market-price or response inputs."""
import pathlib,json,hashlib,itertools,collections
R=pathlib.Path('.');B=R/'research_core_v4/triad_v1'
def read(p):return json.loads((R/p).read_bytes())
def sha(p):return hashlib.sha256((R/p).read_bytes()).hexdigest()
c=read('research_core_v3/state/INCLUSIVE_FULL_DEPTH_DISCOVERY_CORE_V1.json');m=read('research_core_v3/state/PRIMARY_145_INPUT_MANIFEST_V1.json');ledger=read(str(B/'ACCEPTED_FX_ARCHIVE_RECOVERY_LEDGER_V1.json'));assert ledger['all75_recovered']
fx=[x for x in c['primary_core'] if x['asset_class']=='Forex (Spot)'];manifest={x['symbol_id']:x for x in m['primary_series']};edges={};curr=set();ident=[]
G10=set('USD EUR GBP JPY CHF AUD CAD NZD NOK SEK'.split());MANAGED=set('DKK SGD CNH'.split())
# Fixed monetary/liquidity anchor hierarchy; no observed prices or outcomes.
priority='USD EUR GBP JPY CHF AUD CAD NZD NOK SEK DKK SGD CNH MXN PLN HUF ZAR TRY THB ILS RON'.split()
for x in fx:
 s=x['broker_symbol'];assert len(s)==6 and s.isalpha() and s.isupper();a,b=s[:3],s[3:];assert a!=b;key=tuple(sorted([a,b]));assert key not in edges,'multiple accepted identities per unorderedpair require prospective law';edges[key]={'symbol_id':x['symbol_id'],'symbol':s,'base':a,'quote':b,'canonical_sign':1 if a==key[0] else -1,'series_sha256':manifest[x['symbol_id']]['series_sha256']};curr.update(key);ident.append(edges[key])
assert set(curr)<=set(priority)
complete=[];incomplete=[]
for a,b,currc in itertools.combinations(sorted(curr),3):
 keys=[(a,b),(a,currc),(b,currc)];present=[k for k in keys if k in edges]
 if len(present)!=3:
  incomplete.append({'currencies':[a,b,currc],'present_edges':[list(k) for k in present],'missing_edges':[list(k) for k in keys if k not in edges]});continue
 cs=[a,b,currc];anchor=min(cs,key=priority.index);others=sorted(set(cs)-{anchor});target=edges[tuple(others)];ng=set(cs)-G10
 cohort='G10_MONETARY_TRIADS' if not ng else ('MANAGED_EXTENSION_TRIADS' if ng<=MANAGED else 'OTHER_EXTENSION_TRIADS')
 def term(u,v,coef):
  e=edges[tuple(sorted([u,v]))];return {'symbol_id':e['symbol_id'],'coefficient':coef*(1 if e['base']==u else -1)}
 # log(target u/v) - log(u/anchor) + log(v/anchor).
 u,v=others;terms=[term(u,v,1),term(u,anchor,-1),term(v,anchor,1)]
 complete.append({'relation_id':'/'.join(cs),'currencies':cs,'anchor':anchor,'target_symbol_id':target['symbol_id'],'target_canonical_sign':target['canonical_sign'],'cohort':cohort,'closure_terms':terms})
counts=collections.Counter(x['cohort'] for x in complete)
out={'schema':'mxm.v4.triad.canonical-currency-inventory.v1','accepted_FX_identities':75,'unique_currencies':sorted(curr),'unique_currency_count':len(curr),'complete_canonical_triads':len(complete),'structurally_incomplete_currency_triples':len(incomplete),'all_possible_currency_triples':len(complete)+len(incomplete),'incomplete_with_two_edges':sum(len(x['present_edges'])==2 for x in incomplete),'identities':ident,'complete_relations':complete,'incomplete_relations':incomplete,'cohort_definition':{'G10_MONETARY_TRIADS':'All three currencies in fixedG10 monetary/liquidity set; latent globally traded currency relations.','MANAGED_EXTENSION_TRIADS':'At least one nonG10 currency and every nonG10 currency in fixedDKK,SGD,CNH managed/peg set.','OTHER_EXTENSION_TRIADS':'Other completed extended currency relation, paid separately; no universal direction with other cohorts.'},'G10_set':sorted(G10),'managed_extension_set':sorted(MANAGED),'anchor_priority':priority,'cohort_sizes':dict(counts),'membership_uses_only':['authoritative accepted identity','currency algebra','fixed currency structural taxonomy','verified provenance'],'future_response_or_alpha_used':False,'prices_opened':False,'no_individual_triad_hypotheses':True,'bindings':{p:sha(p) for p in ['research_core_v3/state/INCLUSIVE_FULL_DEPTH_DISCOVERY_CORE_V1.json','research_core_v3/state/PRIMARY_145_INPUT_MANIFEST_V1.json',str(B/'ACCEPTED_FX_ARCHIVE_RECOVERY_LEDGER_V1.json')]}}
(B/'CANONICAL_FX_RELATION_COHORT_INVENTORY_V1.json').write_text(json.dumps(out,sort_keys=True,indent=2)+'\n');print(json.dumps({k:out[k] for k in ['unique_currency_count','complete_canonical_triads','structurally_incomplete_currency_triples','incomplete_with_two_edges','cohort_sizes']}))
