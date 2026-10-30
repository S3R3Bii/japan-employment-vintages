import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from cli import compare
class GuardTests(unittest.TestCase):
 def setUp(self):
  self.now=dict(region='Authored region',concept='employed_persons',sex='total',adjustment='original',unit='ten_thousand_persons',dataset_vintage='authored-v1',period='2021-02',count='101');self.lag=dict(self.now,period='2020-02',count='100')
 def test_exact_available(self):self.assertEqual(compare(self.now,self.lag)['growth'],'1/100')
 def test_mixed_version_unavailable(self):self.lag['dataset_vintage']='older';self.assertEqual(compare(self.now,self.lag)['status'],'unavailable')
 def test_wrong_region_unavailable(self):self.lag['region']='different';self.assertEqual(compare(self.now,self.lag)['status'],'unavailable')
 def test_missing_version(self):del self.lag['dataset_vintage'];self.assertEqual(compare(self.now,self.lag)['status'],'unavailable')
 def test_wrong_lag(self):self.lag['period']='2020-03';self.assertEqual(compare(self.now,self.lag)['status'],'unavailable')
 def test_no_numeric_float(self):self.now['count']=101.0;self.assertEqual(compare(self.now,self.lag)['status'],'unavailable')
 def test_zero_unknown(self):self.now['count']='0';self.assertEqual(compare(self.now,self.lag)['status'],'unavailable')
 def test_fraction_not_native_integer(self):self.now['count']='101.5';self.assertEqual(compare(self.now,self.lag)['status'],'unavailable')
if __name__=='__main__':unittest.main()
