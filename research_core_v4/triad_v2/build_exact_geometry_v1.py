"""Predictor-only frozen geometry builder. No price or outcome loader."""
from pathlib import Path
import json,hashlib,base64,io
import numpy as np
P=Path(__file__).parent
ROOT=P.parent.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def build():
 inv=json.loads((ROOT/'research_core_v4/triad_v1/CANONICAL_FX_RELATION_COHORT_INVENTORY_V1.json').read_text())
 old=json.loads((ROOT/'research_core_v4/triad_v1/EXACT_SUPPORT_PREFIX_RAW_RESULT_V1.json').read_text())
 sup=json.loads((P/'EXACT_SUPPORT_RAW_RESULT_V1.json').read_text())
 blob=base64.b64decode(sup['actual_masks_npz_base64']);assert hashlib.sha256(blob).hexdigest()==sup['actual_masks_npz_sha256']
 masks=np.load(io.BytesIO(blob),allow_pickle=False)
 ids=inv['identities'];rels=inv['complete_relations'];coh=['G10_MONETARY_TRIADS','MANAGED_EXTENSION_TRIADS','OTHER_EXTENSION_TRIADS'];aids=[a['symbol_id'] for a in ids];targets=sorted(set(r['target_symbol_id'] for r in rels));assert len(targets)==44
 fits={f['relation_id']:f for f in old['prefix_fits']};scale={t:float(np.median([fits[r['relation_id']]['ownleg60min_RMS'] for r in rels if r['target_symbol_id']==t])) for t in targets};default=float(np.median(list(scale.values())))
 currency=sorted(inv['unique_currencies']);lines=[]
 for ai,a in enumerate(ids):
  ca,cb=sorted([a['base'],a['quote']]);ia,ib=currency.index(ca)+1,currency.index(cb)+1
  # Five reproducible currency contrasts plus eight quote-book shared factors.
  load=[np.sin(ia*(j+1)*np.sqrt(2))-np.sin(ib*(j+1)*np.sqrt(2)) for j in range(5)]+[.25*np.sin((ai+1)*(j+1)*np.sqrt(3)) for j in range(8)]
  lines.append(' '.join(format(float(z),'.17g') for z in [scale.get(a['symbol_id'],default)]+load))
 for r in rels:
  rr=[coh.index(r['cohort']),targets.index(r['target_symbol_id']),fits[r['relation_id']]['residual_RMS']]
  for q in r['closure_terms']:
   ai=aids.index(q['symbol_id']);rr += [ai,q['coefficient']*ids[ai]['canonical_sign']]
  lines.append(' '.join(map(str,rr)))
 for t in targets:
  cs={r['cohort'] for r in rels if r['target_symbol_id']==t};assert len(cs)==1
  lines.append(f'{coh.index(cs.pop())} {aids.index(t)}')
 for a in [masks['causal_relation_membership'][90:],masks['full_clock_horizon'][90:]]:lines.append(' '.join(map(str,a.astype(int).ravel())))
 signs=np.random.default_rng(2026100524).choice([-1,1],size=(1023,15));lines.append(' '.join(map(str,signs.ravel())))
 text='\n'.join(lines)+'\n';(P/'EXACT_SYNTHETIC_GEOMETRY_V1.txt').write_text(text)
 return {'geometry_sha256':hashlib.sha256(text.encode()).hexdigest(),'sign_bank_seed':2026100524,'sign_bank_sha256':hashlib.sha256(signs.astype('<i4').tobytes()).hexdigest(),'asset_ids':aids,'target_ids':targets,'cohorts':coh,'source_bindings':{str(f.relative_to(ROOT)):sha(f) for f in [ROOT/'research_core_v4/triad_v1/CANONICAL_FX_RELATION_COHORT_INVENTORY_V1.json',ROOT/'research_core_v4/triad_v1/EXACT_SUPPORT_PREFIX_RAW_RESULT_V1.json',P/'EXACT_SUPPORT_RAW_RESULT_V1.json']},'price_or_response_read':False,'prefix_normalizations_conditioned_fixed':True}
if __name__=='__main__':
 result=build();(P/'EXACT_SYNTHETIC_GEOMETRY_BINDINGS_V1.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,indent=2))
