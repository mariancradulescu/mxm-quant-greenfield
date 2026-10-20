"""Artificial route mutations of the real operational entry-point anchors."""
import os
import unittest
from unittest.mock import patch
from . import runtime
from .common import LabError,encoded

SHA='a'*40
REF='refs/heads/'+runtime.SOURCE_BRANCH


class Route:
    def __init__(self):
        self.rules=[{'type':k,'ruleset_id':3} for k in ('update','deletion','non_fast_forward')]
        self.freeze={'enforcement':'active','bypass_actors':[],
            'conditions':{'ref_name':{'include':[REF],'exclude':[]}},
            'rules':[{'type':k} for k in ('creation','update','deletion','non_fast_forward')]}
    def json(self,path):
        if path=='git/ref/heads/mxm-o04-active-v1':return {'object':{'sha':runtime.AUTHORITY}}
        if path=='git/ref/heads/'+runtime.SOURCE_BRANCH:return {'object':{'sha':SHA}}
        if path=='rulesets/25222248':return {'id':25222248,'enforcement':'active','bypass_actors':[],
            'conditions':{'ref_name':{'include':['refs/heads/mxm-o04-*'],'exclude':[]}},
            'rules':[{'type':k} for k in ('deletion','non_fast_forward','required_linear_history')]}
        if path=='rules/branches/'+runtime.SOURCE_BRANCH:return self.rules
        if path=='rulesets/3':return self.freeze
        raise KeyError(path)


class SourceFreeze(unittest.TestCase):
    def check(self,route):
        with patch.dict(os.environ,{'LAB_SOURCE_SHA':SHA}),patch.object(runtime.old,'owner_unchanged'), \
             patch.object(runtime,'file_at',return_value=encoded({'revoked':False,'pending':None})), \
             patch.object(runtime.subprocess,'check_output',return_value=SHA+'\n'):
            runtime.anchors(route)

    def test_exact_applied_no_bypass_source_freeze_admits(self):self.check(Route())

    def test_append_only_or_missing_applied_freeze_cannot_start_operation(self):
        for mode in ('no_update','no_deletion','no_nonff'):
            route=Route();kind={'no_update':'update','no_deletion':'deletion','no_nonff':'non_fast_forward'}[mode]
            route.rules=[r for r in route.rules if r['type']!=kind]
            with self.subTest(mode=mode),self.assertRaises(LabError):self.check(route)

    def test_missing_bypass_actors_or_disabled_or_wrong_scope_refused(self):
        for mode in ('omitted','app','disabled','wildcard','excluded','no_creation','no_update'):
            route=Route();freeze=route.freeze
            if mode=='omitted':freeze.pop('bypass_actors')
            elif mode=='app':freeze['bypass_actors']=[{'actor_id':5343530,'actor_type':'Integration','bypass_mode':'always'}]
            elif mode=='disabled':freeze['enforcement']='disabled'
            elif mode=='wildcard':freeze['conditions']['ref_name']['include']=['refs/heads/mxm-o04-*']
            elif mode=='excluded':freeze['conditions']['ref_name']['exclude']=[REF]
            else:freeze['rules']=[r for r in freeze['rules'] if r['type']!=mode[3:]]
            with self.subTest(mode=mode),self.assertRaises(LabError):self.check(route)


if __name__=='__main__':unittest.main()
