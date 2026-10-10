"""Fabricated edge-case tests ONLY; never counted as authentic market evidence."""
import unittest,math
from research_core_v4.cloud_native_covariance_v1.kernel_v1 import feature,resample
class KernelCases(unittest.TestCase):
 def test_constant_degeneracy(self):
  self.assertEqual(feature([1.0]*13,[1.001]*13)['direction'],0)
 def test_invalid_prices(self):
  self.assertIsNone(feature([1.0]*13,[0.99]*13))
  self.assertIsNone(feature([math.nan]*13,[1.001]*13))
 def test_positive_and_negative_concordance(self):
  for orientation in (-1,1):
   mids=[100.0];spreads=[.005]
   for i in range(12):
    d=(i%3-1)*.0001
    mids.append(mids[-1]*math.exp(d));spreads.append(spreads[-1]+orientation*d)
   b=[2*m/(1+math.exp(s)) for m,s in zip(mids,spreads)];a=[v*math.exp(s) for v,s in zip(b,spreads)]
   self.assertEqual(feature(b,a)['direction'],orientation)
 def test_scale_invariance(self):
  b=[100+i*.03+(i%2)*.01 for i in range(13)];a=[v+.1+(i%3)*.01 for i,v in enumerate(b)]
  one=feature(b,a);two=feature([x*1000 for x in b],[x*1000 for x in a])
  self.assertEqual(one['direction'],two['direction']);self.assertAlmostEqual(one['correlation'],two['correlation'],places=9)
 def pages(self,future=False,ambiguous=False):
  pages=[]
  for side,offset in [('bid',0),('ask',100)]:
   values=[(1000000-70000+i*1000,10000000+offset+i) for i in range(71)]
   if future:values.append((1001000,99999999+offset))
   if ambiguous:values.insert(5,(values[4][0],values[4][1]+5))
   values=list(reversed(values));encoded=[{'timestamp':values[0][0],'tick':values[0][1]}]
   for previous,current in zip(values,values[1:]):encoded.append({'timestamp':current[0]-previous[0],'tick':current[1]-previous[1]})
   pages.append({'side':side,'encoded':encoded,'hasMore':False})
  return pages
 def test_causal_samples_ignore_future(self):
  a,why=resample(self.pages(),1000000);b,_=resample(self.pages(future=True),1000000)
  self.assertEqual(why,'SUPPORTED');self.assertEqual(len(a),13);self.assertEqual(a,b)
 def test_pagination_and_ambiguity_fail_closed(self):
  p=self.pages();p[0]['hasMore']=True
  self.assertIsNone(resample(p,1000000)[0])
  self.assertEqual(resample(self.pages(ambiguous=True),1000000)[1],'AMBIGUOUS_SAME_MS')
if __name__=='__main__':unittest.main()
