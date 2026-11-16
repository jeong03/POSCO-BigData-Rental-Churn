import unittest
from unittest.mock import patch
from datetime import date
import numpy as np
from fastapi.testclient import TestClient
import main
from presentation_data import operational_timeline

class AppTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.c=TestClient(main.app)
  token=cls.c.post('/api/auth/admin',json={'admin_id':main.ADMIN_ID,'password':main.ADMIN_PW}).json()['token']
  cls.h={'Authorization':'Bearer '+token}
  cls.p=dict(contract_type='일반',channel='서비스 방문',term=60,customer_type='개인',age_band='30대',gender='여자')
 def test_real_prediction(self):
  a=self.c.post('/api/admin/predict-manual',json=self.p,headers=self.h);self.assertEqual(a.status_code,200);r=a.json()
  self.assertEqual(r['source'],'joblib_model');self.assertTrue(r['factors']);self.assertTrue(0<=r['score']<=100)
  frame,_=main.MANUAL.frame(main.Conditions(**self.p))
  direct=main.RISK.rm.score_percentile(main.RISK.rm.predict_raw(main.RISK.bundle,frame),main.RISK.bundle['reference'])[0]
  self.assertAlmostEqual(r['score'],direct)
  self.assertEqual(r,self.c.post('/api/admin/predict-manual',json=self.p,headers=self.h).json())
 def test_validation(self):
  self.assertEqual(self.c.post('/api/admin/predict-manual',json=self.p).status_code,403)
  for k,v in [('channel','UNKNOWN'),('term',-1),('gender','UNKNOWN'),('age_band','999대')]:
   self.assertEqual(self.c.post('/api/admin/predict-manual',json=self.p|{k:v},headers=self.h).status_code,422)
  self.assertEqual(self.c.post('/api/admin/predict-manual',json={},headers=self.h).status_code,422)
 def test_age_and_options(self):
  opts=self.c.get('/api/admin/predict-options',headers=self.h).json()['options']
  self.assertEqual(set(opts['channel']),set(main.df['유통경로'].dropna()))
  frame,_=main.MANUAL.frame(main.Conditions(**self.p))
  self.assertEqual(main.RISK.bundle['model'][0].transform(frame).iloc[0]['age_at_contract'],35)
  frame,_=main.MANUAL.frame(main.Conditions(**(self.p|{'customer_type':'사업자'})))
  self.assertTrue(np.isnan(main.RISK.bundle['model'][0].transform(frame).iloc[0]['age_at_contract']))
 def test_missing_model(self):
  with patch.object(main.RISK,'bundle',None):
   self.assertEqual(self.c.post('/api/admin/predict-manual',json=self.p,headers=self.h).status_code,503)
   r=self.c.post('/api/admin/predict-example',json=self.p,headers=self.h)
   self.assertEqual(r.status_code,200);self.assertEqual(r.json()['source'],'example_only')
 def test_grades(self):
  with patch.object(main.RISK.rm,'score_percentile') as score:
   for value,grade in [(20,'낮음'),(85,'보통'),(99,'높음')]:
    score.return_value=np.array([value]);r=self.c.post('/api/admin/predict-manual',json=self.p,headers=self.h).json()
    self.assertEqual(r['grade'],grade);self.assertTrue(r['actions'])
 def test_timeline(self):
  for dt in [date(2026,1,1),date(2026,11,11),date(2024,2,29)]:
   o=operational_timeline(43000,dt)
   self.assertEqual(sum(r['cancelled'] for r in o['daily']),o['year']['cancelled'])
   self.assertEqual(sum(r['cancelled'] for r in o['monthly']),o['year']['cancelled'])
   self.assertEqual(o['today'],o['daily'][-1]);self.assertEqual(o['month'],o['monthly'][-1])
   self.assertAlmostEqual(o['year']['rate'],100*o['year']['cancelled']/o['year']['opening'])
   for a,b in zip(o['daily'],o['daily'][1:]):self.assertEqual(a['opening']-a['cancelled'],b['opening'])
 def test_existing(self):
  for path in ['/api/admin/dashboard','/api/admin/risk-customers','/api/products','/api/promotions']:
   self.assertEqual(self.c.get(path,headers=self.h).status_code,200)
  cid=main.RISK.table.iloc[0]['cid']
  self.assertEqual(self.c.get('/api/admin/customer/'+cid,headers=self.h).status_code,200)
  token=self.c.post('/api/auth/customer',json={'customer_id':cid}).json()['token']
  r=self.c.get('/api/me',headers={'Authorization':'Bearer '+token});self.assertEqual(r.status_code,200)
  owned={x['category'] for x in r.json()['contracts']}
  self.assertFalse(owned & {x['cat'] for x in r.json()['recommendations']})
if __name__=='__main__':unittest.main()
