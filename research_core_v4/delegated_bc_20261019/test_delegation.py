import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from . import control as c, science as s

SOURCE='a'*40
HEAD='b'*40

def accounting(n=2,missing=0,value=1.):
    return {'selected':n,'evaluable':n-missing,'unknown':missing,
            'known_subtotal':{'net_eur':value},'complete_net_eur':value if n and not missing else None,
            'paired_entries':n-missing,'paired_model_increment_eur':value}

def summary():
    return {'schema':'mxm.quote.path.empirical.summary.v1','design_sha256':s.DESIGN_SHA,
        'broker_requests':0,'orders':0,'fills':0,'protected_forward':False,
        'alpha_certified':False,'HARD21_demonstrated':False,
        'accounting':{k:accounting() for k in ('model','midpoint','quote_count')},
        'all_original_event_rows':10,'unique_candidate_boundaries':8,'calculable_features':6,
        'entry_proxy_eligible_all':7,'model_proposed_eligible':4,'cost_terms':'HYPOTHETICAL_SYNTHETIC'}

class Delegation(unittest.TestCase):
    def ready(self):
        state=c.genesis(SOURCE,1000)
        return c.propose(state,SOURCE,HEAD,1001,'renew')

    def test_delegation_never_claims_native_owner_review(self):
        self.assertFalse(c.POLICY['native_owner_review_claimed'])
        self.assertFalse(c.POLICY['orders_allowed']);self.assertFalse(c.POLICY['historical_restart_allowed'])

    def test_ordinary_renewal_after_a_year_preserves_root(self):
        state=self.ready();later=1000+365*86400
        renewed=c.propose(state,SOURCE,HEAD,later,'renew')
        self.assertEqual(renewed['owner_root'],list(c.OWNER_ROOT))
        self.assertEqual(renewed['sequence'],0);self.assertEqual(renewed['lease']['index'],365*86400//60)

    def test_duplicate_renew_and_backward_clock_stop(self):
        state=self.ready()
        for now in (1001,999):
            with self.assertRaises(Exception):c.propose(state,SOURCE,HEAD,now,'renew')

    def test_pending_after_crash_cannot_renew_or_reexecute(self):
        state=c.propose(self.ready(),SOURCE,HEAD,1001,'claim',run_id=7)
        for operation in ('renew','claim'):
            with self.assertRaises(Exception):c.propose(state,SOURCE,HEAD,2000,operation,run_id=8)
        self.assertEqual(c.scheduling(state,SOURCE,2000),'PENDING_STOP_NO_REEXECUTION')

    def test_completion_expiry_and_other_run_stop(self):
        state=c.propose(self.ready(),SOURCE,HEAD,1001,'claim',run_id=7)
        for now,run in ((1060,7),(1002,8)):
            with self.assertRaises(Exception):c.propose(state,SOURCE,HEAD,now,'complete',run_id=run,
                result_sha256='c'*64,checkpoint_sha256='d'*64)

    def test_next_task_needs_fresh_workflow_and_lease(self):
        state=c.propose(self.ready(),SOURCE,HEAD,1001,'claim',run_id=7)
        state=c.propose(state,SOURCE,HEAD,1002,'complete',run_id=7,result_sha256='c'*64,checkpoint_sha256='d'*64)
        with self.assertRaises(Exception):c.propose(state,SOURCE,HEAD,1003,'claim',run_id=8)
        state=c.propose(state,SOURCE,HEAD,1061,'renew')
        with self.assertRaises(Exception):c.propose(state,SOURCE,HEAD,1061,'claim',run_id=7)
        claimed=c.propose(state,SOURCE,HEAD,1061,'claim',run_id=8)
        self.assertEqual(claimed['pending']['task'],'B_COLD_RESTORE_2')

    def test_revocation_stops_even_after_lease_expiry(self):
        state=c.propose(self.ready(),SOURCE,HEAD,1001,'revoke')
        self.assertEqual(c.scheduling(state,SOURCE,9000),'REVOKED')
        with self.assertRaises(Exception):c.propose(state,SOURCE,HEAD,9000,'renew')

    def test_root_source_policy_or_intent_tampering_stops(self):
        state=c.propose(self.ready(),SOURCE,HEAD,1001,'claim',run_id=7)
        variants=[]
        for key,value in (('source_sha','c'*40),('policy_sha256','d'*64),('sequence',1)):
            x=copy.deepcopy(state);x[key]=value;variants.append(x)
        x=copy.deepcopy(state);x['pending']['intent']='f'*64;variants.append(x)
        for x in variants:
            with self.assertRaises(Exception):c.validate(x,SOURCE)

    def test_native_rule_actor_and_exact_target_controls(self):
        from .native import check_rule,ACL
        rule={'enforcement':'active','conditions':{'ref_name':{'include':[c.ACTIVE_REF],'exclude':[]}},
              'rules':[{'type':k} for k in ('creation','update','deletion','non_fast_forward')],
              'bypass_actors':ACL}
        check_rule(rule,exact=True)
        for change in ({'bypass_actors':[]},{'bypass_actors':ACL+[{'actor_id':1}]},{'enforcement':'disabled'}):
            with self.assertRaises(Exception):check_rule({**rule,**change},exact=True)
        rule.pop('bypass_actors')
        check_rule(rule)
        with self.assertRaises(Exception):check_rule(rule,exact=True)

    def test_full_four_run_chain_terminates_honestly(self):
        state=c.genesis(SOURCE,1000)
        for n in range(4):
            now=1001+n*60;state=c.propose(state,SOURCE,HEAD,now,'renew')
            state=c.propose(state,SOURCE,HEAD,now,'claim',run_id=10+n)
            state=c.propose(state,SOURCE,HEAD,now+1,'complete',run_id=10+n,
                result_sha256='c'*64,checkpoint_sha256='d'*64)
        self.assertEqual(state['sequence'],4)
        self.assertEqual(c.scheduling(state,SOURCE,9999),'REGISTERED_QUEUE_COMPLETE_NO_CBOT_QUALIFICATION')

class ScientificSupport(unittest.TestCase):
    def test_missing_outcome_has_no_invented_finite_bound(self):
        q=summary();q['accounting']['model']=accounting(missing=1)
        r=s.partial_identification(q)
        self.assertEqual(r['arms']['model']['identified_set']['kind'],'UNBOUNDED_WITHOUT_JUSTIFIED_OUTCOME_BOUNDS')
        self.assertIsNone(r['paired']['midpoint']['complete_increment_eur'])

    def test_complete_simulation_does_not_qualify_cbot(self):
        r=s.partial_identification(summary());a=s.admission(r)
        self.assertFalse(a['cbot_qualified']);self.assertFalse(a['full_research_universe_exhausted'])

    def test_partial_pairing_does_not_promote_subtotal(self):
        q=summary();q['accounting']['midpoint']['paired_entries']=1
        self.assertIsNone(s.partial_identification(q)['paired']['midpoint']['complete_increment_eur'])

    def test_false_complete_or_nonfinite_cost_stops(self):
        for value in (float('nan'),float('inf'),True):
            q=summary();q['accounting']['model']['complete_net_eur']=value
            with self.assertRaises(Exception):s.partial_identification(q)
        q=summary();q['accounting']['model']['unknown']=1
        with self.assertRaises(Exception):s.partial_identification(q)

    def test_denominators_are_separate_and_input_immutable(self):
        q=summary();before=copy.deepcopy(q);r=s.partial_identification(q)
        self.assertEqual(q,before)
        self.assertGreater(r['coverage']['entry_proxy_eligible_all'],r['coverage']['calculable_features'])

class AtomicCheckpoint(unittest.TestCase):
    def test_actual_receive_pack_rejects_stale_parent_and_keeps_cipher_atomic(self):
        from . import native
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);remote=root/'remote.git'
            subprocess.run(['git','init','--bare','-q',str(remote)],check=True)
            with patch.object(native,'REMOTE',str(remote)),patch('research_core_v4.p0_successor_a_20261017.publisher.REMOTE',str(remote)):
                store=native.Store(root/'writer','SYNTHETIC_LOCAL_ONLY',SOURCE)
                state=c.genesis(SOURCE,1000);first=store.cas(None,state)
                updated=c.propose(state,SOURCE,first,1001,'renew');second=store.cas(first,updated)
                with self.assertRaises(Exception):store.cas(first,state)
                claimed=c.propose(updated,SOURCE,second,1001,'claim',run_id=1);third=store.cas(second,claimed)
                # Opaque fabricated cipher exercises exact same native multi-blob commit path.
                cipher=b'SYNTHETIC_ENCRYPTED_FIXTURE_ONLY';store.cipher=cipher
                completed=c.propose(claimed,SOURCE,third,1002,'complete',run_id=1,
                    result_sha256='f'*64,checkpoint_sha256=c.digest(cipher))
                head=store.cas(third,completed);read_head,read_state=store.read()
                self.assertEqual(head,read_head);self.assertEqual(read_state,completed)
                self.assertEqual(store.cipher,cipher)
                cold=native.Store(root/'cold','SYNTHETIC_LOCAL_ONLY',SOURCE)
                self.assertEqual(cold.read(),(head,completed));self.assertEqual(cold.cipher,cipher)

if __name__=='__main__':unittest.main()
