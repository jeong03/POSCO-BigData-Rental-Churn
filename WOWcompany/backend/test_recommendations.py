"""Run with: python -m unittest -v test_app test_recommendations
All writes isolated in a temporary database. No CSV mutations.
"""
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import main
from recommendations import RecommendationService, WEIGHTS
from pypdf import PdfReader

class RecommendationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.original_db=main.DB
        cls.db=Path(cls.tmp.name)/'test.db'
        with sqlite3.connect(main.DB) as src, sqlite3.connect(cls.db) as dst:src.backup(dst)
        cls.patch=patch.object(main,'DB',cls.db);cls.patch.start()
        cls.client=TestClient(main.app)
        cls.h={'Authorization':'Bearer '+cls.client.post('/api/auth/admin',json={'admin_id':main.ADMIN_ID,'password':main.ADMIN_PW}).json()['token']}
        cls.ids={t:list(main.active.loc[main.active['고객유형'].eq(t),'고객ID'].unique()[:12]) for t in ['개인','사업자']}
        cls.checksum=hashlib.sha256(main.CSV.read_bytes()).hexdigest()
    @classmethod
    def tearDownClass(cls):
        assert cls.checksum==hashlib.sha256(main.CSV.read_bytes()).hexdigest()
        cls.patch.stop();cls.tmp.cleanup()
    def get(self,cid):
        r=self.client.get('/api/admin/customer/'+cid,headers=self.h)
        self.assertEqual(r.status_code,200,r.text);return r.json()
    def test_personal_exact_legacy_ranking_12_ids(self):
        for cid in self.ids['개인']:
            d=self.get(cid)
            tok=self.client.post('/api/auth/customer',json={'customer_id':cid}).json()['token']
            old=self.client.get('/api/me',headers={'Authorization':'Bearer '+tok}).json()['recommendations']
            self.assertEqual([(p['id'],p['score'],p['reason']) for p in old],[(p['id'],p['score'],p['reason']) for p in d['recommendations']])
            self.assertIsNone(d['business']);self.assertEqual(d['customer_type'],'개인')
    def test_business_12_ids_and_persistence(self):
        sequences=set(); profiles=[]
        reloaded=RecommendationService(main.run,main.CATALOG,main.PRODUCT,main.recommend)
        for cid in self.ids['사업자']:
            d=self.get(cid);self.assertEqual(d['customer_type'],'사업자');self.assertEqual(len(d['recommendations']),3)
            self.assertEqual(d['business'],self.get(cid)['business']);self.assertEqual(d['business'],reloaded.profile(cid,[]))
            self.assertEqual(len(d['contract_history']),len(main.ALL_IDX[cid]));self.assertEqual(d['business']['source'],'synthetic')
            sequences.add(tuple(p['id'] for p in d['recommendations']));profiles.append(d['business'])
            for p in d['recommendations']:
                self.assertTrue(0<=p['suitability']<=100);self.assertIn(p['id'],{x['id'] for x in main.CATALOG})
                self.assertIn('가상',p['reason']);self.assertTrue(p['evidence']);self.assertTrue(p['effect'])
                self.assertTrue((main.BASE.parent/'frontend'/'public'/p['image'].lstrip('/')).exists())
                self.assertAlmostEqual(p['suitability'],round(max(0,min(100,sum(p['score_breakdown'].values())-p['duplicate_penalty'])),1))
        self.assertGreater(len(sequences),2);self.assertEqual(sum(WEIGHTS.values()),100)
    def test_consultation_full_lifecycle_and_pdf(self):
        for cid in [self.ids['개인'][0],self.ids['사업자'][0]]:
            d=self.get(cid);path=f'/api/admin/customer/{cid}/consultations'
            body=dict(product_id=d['recommendations'][0]['id'],content='현장 설치 공간 확인',assignee='영업 담당자 테스트')
            r=self.client.post(path,json=body,headers=self.h);self.assertEqual(r.status_code,201,r.text);c=r.json()
            self.assertEqual(json.loads(c['recommendation'])['id'],body['product_id'])
            u=dict(content='견적 안내 완료',assignee='영업 담당자 테스트',status='계약완료',result='고객 동의 및 계약 확인')
            self.assertEqual(self.client.patch(path+'/'+str(c['id']),json=u,headers=self.h).status_code,200)
            self.assertEqual(self.client.get(path,headers=self.h).json()[0]['result'],u['result'])
            self.assertEqual(self.client.patch(path+'/'+str(c['id']),json=u|{'result':''},headers=self.h).status_code,422)
            other=self.ids['개인'][2]
            self.assertEqual(self.client.patch(f'/api/admin/customer/{other}/consultations/{c["id"]}',json=u,headers=self.h).status_code,404)
            rep=self.client.post('/api/admin/report',json={'customer_id':cid,'note':'<확인> & 후속 상담'},headers=self.h)
            self.assertEqual(rep.status_code,200,rep.text);rep=rep.json()
            for text in ['AI 추가 계약 추천 TOP 3','고객 동의 및 계약 확인','전체 계약 이력']:self.assertIn(text,rep['text'])
            if d['business']:self.assertIn('가상',rep['text']);self.assertIn(d['business']['name'],rep['text'])
            pdf=self.client.get(f'/api/admin/report/{rep["id"]}/pdf',headers=self.h)
            self.assertEqual(pdf.status_code,200);self.assertTrue(pdf.content.startswith(b'%PDF'))
            text=''.join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
            self.assertIn('TOP 3',text);self.assertIn(cid,text)
            saved=self.client.get(f'/api/admin/report/{rep["id"]}',headers=self.h).json()
            self.assertEqual(saved['text'],rep['text'])
            self.assertIn(rep['id'],[x['id'] for x in self.client.get(f'/api/admin/customer/{cid}/reports',headers=self.h).json()])
            self.assertEqual(self.client.post(path,json=body|{'product_id':'unknown'},headers=self.h).status_code,422)
            self.assertEqual(self.client.post(path,json=body|{'assignee':' '},headers=self.h).status_code,422)
    def test_admin_only_access(self):
        cid=self.ids['사업자'][0];other=self.ids['개인'][0]
        tok=self.client.post('/api/auth/customer',json={'customer_id':other}).json()['token']
        requests=[('GET',f'/api/admin/customer/{cid}',None),('GET',f'/api/admin/customer/{cid}/consultations',None),('POST',f'/api/admin/customer/{cid}/consultations',dict(product_id='air',content='test',assignee='test')),('PATCH',f'/api/admin/customer/{cid}/consultations/1',dict(content='test',assignee='test',status='접수')),('GET',f'/api/admin/customer/{cid}/reports',None),('GET','/api/admin/report/1',None),('GET','/api/admin/report/1/pdf',None),('POST','/api/admin/report',dict(customer_id=cid))]
        for h in [{},{'Authorization':'Bearer '+tok}]:
            for method,path,body in requests:self.assertEqual(self.client.request(method,path,json=body,headers=h).status_code,403,path)
    def test_inactive_unknown_missing_type(self):
        self.assertEqual(self.client.get('/api/admin/customer/DOES-NOT-EXIST',headers=self.h).status_code,404)
        inactive=next(cid for cid in main.ALL_IDX if cid not in main.ACT_IDX)
        d=self.get(inactive);self.assertFalse(d['active']);self.assertTrue(d['contract_history'])
        self.assertEqual(self.client.post('/api/admin/report',json={'customer_id':inactive},headers=self.h).status_code,200)
        missing=main.df.loc[main.df['고객유형'].isna(),'고객ID'].iloc[0]
        d=self.get(missing);self.assertEqual(d['recommendations'],[]);self.assertIn('확인',d['recommendation_warning'])
        rows=main.df.iloc[main.ALL_IDX[self.ids['사업자'][0]]].copy();rows['고객유형']='UNKNOWN'
        d=main.RECOMMENDATIONS.build('test',rows,[]);self.assertEqual(d['recommendations'],[])
    def test_input_changes_affect_score(self):
        cid=self.ids['사업자'][1];d=self.get(cid);rows=main.df.iloc[main.ALL_IDX[cid]]
        b=d['business'];changed=b|{'employees':500,'area_m2':3000,'industry':'숙박업','expansion':dict(planned=True,extra_area_m2=180,content='확장',source='synthetic')}
        with patch.object(main.RECOMMENDATIONS,'profile',return_value=changed):
            output=main.RECOMMENDATIONS.build(cid,rows,d['contract_history'])
        self.assertNotEqual([(x['id'],x['suitability']) for x in d['recommendations']],[(x['id'],x['suitability']) for x in output['recommendations']])
    def test_csv_and_risk_preserved(self):
        self.assertEqual(self.checksum,hashlib.sha256(main.CSV.read_bytes()).hexdigest())
        self.assertEqual(main.RISK.source,'joblib_model')
        cid=self.ids['개인'][0]
        self.assertEqual(main._legacy_detail(cid)['risk'],self.get(cid)['risk'])

if __name__=='__main__':unittest.main()
