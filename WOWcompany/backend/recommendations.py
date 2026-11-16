"""Separate from risk_model: explainable, uncalibrated recommendation suitability.
Only existing CATALOG entries are candidates. All business operational data is synthetic.
"""
import hashlib
import json
import math
import random
from collections import Counter
from datetime import date, timedelta

VERSION = 'b2b-rules-v1'
WEIGHTS = dict(industry=30, capacity=20, complement=10, service=10, visit=10, expansion=15, history=5)
INDUSTRIES = {
    '사무실': dict(purifier=1, air=1, bidet=.7, mattress=.1, softener=.2, chair=.65),
    '숙박업': dict(purifier=.8, air=.85, bidet=1, mattress=1, softener=.9, chair=.4),
    '교육시설': dict(purifier=1, air=1, bidet=.8, mattress=.1, softener=.2, chair=.2),
    '피트니스': dict(purifier=1, air=.8, bidet=.7, mattress=.1, softener=1, chair=.95),
    '음식점': dict(purifier=1, air=.6, bidet=.8, mattress=.05, softener=.9, chair=.15),
    '제조업 사무·휴게공간': dict(purifier=1, air=.8, bidet=.7, mattress=.2, softener=.5, chair=.9),
}
EFFECTS = dict(purifier='음용수 이용 동선과 대기 부담 완화 검토', air='공용 공간의 실내 공기 관리 보완', bidet='공용 화장실 위생 관리 편의 보완', mattress='숙박·휴게 공간의 수면 환경 관리', softener='샤워·세면 공간의 물 사용 편의 개선 검토', chair='직원·이용객 휴식 공간 활용도 향상 검토')
IMAGES = {k: '/images/products/'+('CP-7211' if k=='purifier' else k)+'.png' for k in EFFECTS}

class RecommendationService:
    def __init__(self, run, catalog, products, recommend):
        self.run, self.catalog, self.products, self.personal = run, catalog, products, recommend
        run('CREATE TABLE IF NOT EXISTS business_profiles(customer_id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL)')
        run('''CREATE TABLE IF NOT EXISTS rental_consultations(id INTEGER PRIMARY KEY, customer_id TEXT NOT NULL,
            product_id TEXT NOT NULL, content TEXT NOT NULL, assignee TEXT NOT NULL, status TEXT NOT NULL,
            result TEXT NOT NULL, recommendation TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')

    def profile(self, cid, contracts):
        saved = self.run('SELECT payload FROM business_profiles WHERE customer_id=?', (cid,), True)
        if saved: return json.loads(saved[0]['payload'])
        r = random.Random(int(hashlib.sha256(('b2b:'+cid).encode()).hexdigest(),16))
        industry = r.choice(list(INDUSTRIES)); employees = r.choice([8,15,25,40,65,90,150])
        area = employees*r.choice([7,12,18]); expansion = r.choice([False,False,True])
        today = date.today(); dt = lambda n: (today-timedelta(days=n)).isoformat()
        kinds = [c['kind'] for c in contracts if c['status']=='계약확정']
        focus = r.choice(kinds or ['purifier']); visit_focus = r.choice(['air','purifier','bidet','softener'])
        complaints = [dict(date=dt(45),kind=focus,content='공용 공간 이용 시간대 혼잡 문의',status='상담 예정',source='synthetic')] if r.random()<.5 else []
        service = [dict(date=dt(20+i*30),kind=focus,content='작동 상태 점검 요청',status='처리완료',source='synthetic') for i in range(r.randrange(3))]
        p = dict(customer_id=cid,name=f'가상 {industry} {cid[-5:]}',industry=industry,employees=employees,area_m2=area,
                 operating_status=r.choice(['정상 운영 · 주 5일','정상 운영 · 주 6일','교대 운영']),
                 coordi=r.choice(['김수현','이도윤','박서연','최지후']),source='synthetic',source_label='시연용 가상 사업장 정보 · 실사 확인 필요',
                 complaints=complaints,as_history=service,
                 visits=[dict(date=dt(r.randint(3,25)),kind=visit_focus,content='공용 공간 추가 설치 위치 및 관리 동선 확인 필요',source='synthetic')],
                 activities=[dict(date=dt(10),content='신규 공간 개설을 위한 시설 검토' if expansion else '기존 공용 공간의 정기 운영 점검',source='synthetic')],
                 expansion=dict(planned=expansion,extra_area_m2=r.choice([60,100,180]) if expansion else 0,content='신규 공간 도입 검토' if expansion else '확장 계획 기록 없음',source='synthetic'))
        self.run('INSERT OR IGNORE INTO business_profiles VALUES(?,?,?)',(cid,json.dumps(p,ensure_ascii=False),today.isoformat()))
        return json.loads(self.run('SELECT payload FROM business_profiles WHERE customer_id=?',(cid,),True)[0]['payload'])

    def build(self, cid, rows, contracts):
        types = set(rows['고객유형'].dropna().astype(str).str.strip())
        if len(types)!=1 or not types <= {'개인','사업자'}:
            return dict(customer_type='확인 필요', recommendations=[], business=None, recommendation_warning='CSV 고객유형이 누락되거나 혼재되어 추천을 중단했습니다. 원본 정보를 확인해 주세요.')
        ctype = next(iter(types)); current=[c for c in contracts if c['status']=='계약확정']
        if ctype=='개인':
            # Match /api/me: first active row, same age/gender, same owned categories.
            active_rows=rows[rows['계약상태']=='계약확정']; f=(active_rows if len(active_rows) else rows).iloc[0]
            age = float(f['age_2026']) if str(f['age_2026']) not in ('nan','None','<NA>') else None
            items=self.personal(age,f['남여구분'],{c['category'] for c in current})
            items=[p | dict(suitability=round(100*p['score']/(1+p['score']),1),effect=EFFECTS[p['kind']],image=IMAGES[p['kind']],score_method='기존 개인 추천 원점수 s를 100×s/(1+s)로 단조 변환',source='existing_personal_rules') for p in items]
            return dict(customer_type=ctype,business=None,recommendations=items,recommendation_method='기존 개인 추천 순위 유지 · 계약 확률 아님')
        b=self.profile(cid,contracts); counts=Counter(c['kind'] for c in current)
        # Contract rows are a proxy for units, never verified equipment inventory.
        hist=Counter(c['kind'] for c in contracts); actual_as=self.run('SELECT * FROM as_requests WHERE customer_id=?',(cid,),True)
        items=[]
        for p in self.catalog:
            k=p['kind']; n=counts[k]; industry=INDUSTRIES[b['industry']][k]
            required={'purifier':math.ceil(b['employees']/25),'air':math.ceil(b['area_m2']/80),'bidet':math.ceil(b['employees']/30)}.get(k,1)
            shortage=max(0,(required-n)/required)
            complaints=sum(x['kind']==k for x in b['complaints'])
            synth_as=sum(x['kind']==k for x in b['as_history'])
            real_as=sum(self.products.get(x['product_code'],{}).get('kind')==k for x in actual_as)
            visit=any(x['kind']==k for x in b['visits'])
            expansion=b['expansion']['planned'] and industry>=.6
            factors=dict(industry=industry,capacity=shortage*industry,complement=(1 if not n and counts else .3)*industry,
                         service=min(1,(complaints+synth_as+real_as)/2),visit=float(visit),expansion=float(expansion),history=.6 if hist[k] else .3)
            penalty=18 if n and shortage==0 else 6 if n else 0
            contributions={key:round(WEIGHTS[key]*v,2) for key,v in factors.items()}
            score=round(max(0,min(100,sum(contributions.values())-penalty)),1)
            evidence=[f"CSV 정상 계약 기준 {p['cat']} {n}건(실제 설치 대수는 상담 시 확인)",f"가상 사업장 정보: {b['industry']}, 직원 {b['employees']}명, {b['area_m2']}㎡"]
            reasons=[f"가상 사업장 정보의 {b['industry']} 업종, 직원 {b['employees']}명·면적 {b['area_m2']}㎡와 CSV 정상 {p['cat']} 계약 {n}건을 반영했습니다."]
            if k in ('purifier','air','bidet'):
                reasons += [f"가상 직원 수·면적과 내부 상담 기준상 검토 수량 {required}건 대비 정상 계약 {n}건으로, {'추가 설치 수요를 확인합니다' if shortage else '중복 보유를 감점했습니다'}. 이 수량은 제품의 인증 용량이 아닙니다."]
            if synth_as or complaints: reasons += [f'가상 기록에 관련 클레임 {complaints}건·AS {synth_as}건이 있어, 원인 확인과 기존 제품 수리를 우선 상담합니다.']
            if real_as: reasons += [f'실제 앱 AS 접수 {real_as}건이 있어 처리 결과를 확인합니다(고장 확정 아님).']
            if visit: reasons += [f"가상 방문 기록({b['visits'][0]['date']})의 추가 설치 위치 점검 항목을 반영했습니다."]
            if expansion: reasons += [f"가상 신규 공간 {b['expansion']['extra_area_m2']}㎡ 검토 기록에 따라 추가 수요 확인을 제안합니다."]
            items.append({key:v for key,v in p.items() if key not in ('fit','why')} | dict(suitability=score,reason=' '.join(reasons),evidence=evidence,effect=EFFECTS[k]+' (효과 미검증)',image=IMAGES[k],source='mixed_csv_synthetic',price_is_demo=True,score_breakdown=contributions,duplicate_penalty=penalty))
        return dict(customer_type=ctype,business=b,recommendations=sorted(items,key=lambda p:(-p['suitability'],p['id']))[:3],recommendation_method=VERSION+' · 규칙 기반 적합도, 계약 확률 아님',recommendation_weights=WEIGHTS,
                    inventory_note='보유량은 CSV 정상 계약 건수를 대용 지표로 사용. 중복 행·실제 설치 대수·제품 용량은 상담 시 확인.',actual_as_history=actual_as)


def report_lines(d):
    L=['','6. 전체 계약 이력 (CSV)']
    L += [f"- {c['product_name']} / {c['status']} / {c['sales_type']} / {c['term_months']}개월 / 월 {c['monthly_fee']:,}원 / {c['start_date']}" for c in d['contract_history']]
    b=d.get('business')
    if b:
        L += ['', '7. 사업장 운영 정보 [시연용 가상 데이터]',f"- {b['name']} / {b['industry']} / 직원 {b['employees']}명 / {b['area_m2']}㎡ / {b['operating_status']}",f"- 담당 코디: {b['coordi']} (가상)",f"- 확장: {b['expansion']['content']} / 추가 {b['expansion']['extra_area_m2']}㎡"]
        for key,label in [('complaints','클레임'),('as_history','AS'),('visits','방문'),('activities','사업 활동')]:
            L += [f"- {label} [가상]: {x['date']} {x['content']} {x.get('status','')}" for x in b[key]] or [f'- {label}: 가상 기록 없음']
        L += [f"- AS [실제 앱 접수]: {x['created_at']} {x['symptom']} / {x['status']}" for x in d.get('actual_as_history',[])]
        L += [d['inventory_note']]
    L += ['','8. AI 추가 계약 추천 TOP 3',d.get('recommendation_method',d.get('recommendation_warning','')),'※ 적합도는 계약 확률이 아니며, 카탈로그 명칭·가격·이미지는 기존 시연용 상품 마스터입니다.']
    for i,p in enumerate(d['recommendations'],1):
        L += [f"TOP {i}. {p['name']} / 월 {p['price']:,}원 / 적합도 {p['suitability']}점",p['reason'],'기대 효과: '+p['effect']]
    L += ['','9. 권장 상담 전략 및 후속 조치','- 사업장 운영 정보와 실제 설치 수량을 먼저 확인합니다.' if b else '- 이용 중인 상품과 관심 제품을 고객에게 확인합니다.','- 미처리 AS·불편 해소를 우선하고, 설치 공간·예산·이용 수요를 확인한 뒤 추가 계약을 제안합니다.','- 상담 담당자 지정 → 고객 동의 확인 → 현장 확인 → 견적 안내 → 결과 기록']
    for c in d.get('rental_consultations',[]):
        L += [f"- 상담 #{c['id']} / {c['product_id']} / {c['assignee']} / {c['status']} / 내용: {c['content']} / 결과: {c['result'] or '미기록'}"]
    return L
