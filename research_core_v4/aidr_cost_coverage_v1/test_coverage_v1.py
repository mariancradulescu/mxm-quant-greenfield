"""Small synthetic tests only; no real events or sources read."""
import unittest
from . import coverage_kernel_v1 as k
class Coverage(unittest.TestCase):
 def setUp(self):
  self.t=1787184000
  self.e={'ordinal':1,'symbol_id':127,'decision_timestamp':self.t,'entry_reference_boundary':self.t,'exit_reference_boundary':self.t+3600,'direction':1,'fixed_week':0,'response_support_status':'SUPPORTED','receipt_semantics':'SYNTHETIC'}
 def row(self,t):return {'timestamp_ms':t*1000,'two_sided':True,'fresh':None,'row_sha256':'0'*64}
 def source(self,rows,sid=127,name='A'):return {'source':name,'member':'x','member_sha256':'0'*64,'symbol_id':sid,'kind':'BOUNDARY','records':rows}
 def index(self,s):return {'schema':'mxm.aidr.existing.cost.availability.v1','compiled_without_event_access':True,'start_ms':self.t*1000,'sources':s}
 def cat(self,s):return k.intersect([self.e],self.index(s))['records'][0]['coverage']['category']
 def test_five_categories_and_overlay(self):
  r=self.row;t=self.t;s=self.source
  cases=[([s([r(t),r(t+3600)])],0),([s([r(t)])],1),([],2),([s([dict(r(t),two_sided=False),dict(r(t+3600),two_sided=False)])],3),([s([])],4)]
  for sources,i in cases:self.assertEqual(self.cat(sources),k.CATEGORIES[i])
  self.assertEqual(k.intersect([self.e],self.index([]))['unresolved_cost_semantics_overlay'],1)
 def test_no_side_stitching_or_symbol_transfer(self):
  t=self.t;r=self.row;s=self.source
  self.assertEqual(self.cat([s([r(t)]),s([r(t+3600)],name='B')]),k.CATEGORIES[1])
  self.assertEqual(self.cat([s([r(t),r(t+3600)],sid=126)]),k.CATEGORIES[2])
 def test_other_law_direction_is_unresolved(self):
  t=self.t;j={'source':'N','member':'x','member_sha256':'0'*64,'symbol_id':127,'kind':'JOINT','records':[{'entry_ms':t*1000,'exit_ms':(t+3600)*1000,'source_event_direction':'UP','resolved':True,'row_sha256':'0'*64}]}
  self.assertEqual(self.cat([j]),k.CATEGORIES[3])
 def test_duplicate_and_count_denial(self):
  with self.assertRaises(AssertionError):k.intersect([self.e,self.e],self.index([]))
  with self.assertRaises(AssertionError):k.intersect([self.e],self.index([self.source([self.row(self.t),self.row(self.t)])]))
  with self.assertRaises(AssertionError):k.intersect([self.e],self.index([]),{})
  k.intersect([self.e],self.index([]),{(1,0,'SUPPORTED'):1})
if __name__=='__main__':unittest.main()

