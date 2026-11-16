"""Six user inputs -> exact notebook REQUIRED columns. Defaults never use labels."""
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

class Conditions(BaseModel):
    model_config=ConfigDict(extra='forbid')
    contract_type: str
    channel: str
    term: int
    customer_type: str
    age_band: str
    gender: str

AGE_MAP={f'{n}대':n+5 for n in range(10,90,10)} | {'90대 이상':95}

class ManualPredictor:
    def __init__(self, df, default_path):
        self.df=df.copy()
        self.reference=pd.read_csv(default_path) if default_path.exists() else df.copy()
        self.reference['계약유형']=self.reference['계약유형'].replace({'멥버십C':'멤버십C'})
        self.default_source='training_partition' if default_path.exists() else 'csv_representative_fallback'

    def options(self):
        return dict(contract_type=sorted(self.df['계약유형'].dropna().unique()),channel=sorted(self.df['유통경로'].dropna().unique()),
                    term=sorted(int(x) for x in self.df['계약기간'].dropna().unique()),customer_type=sorted(self.df['고객유형'].dropna().unique()),
                    age_band=list(AGE_MAP),gender=[dict(value=g,label={'남자':'남성','여자':'여성'}.get(g,g)) for g in sorted(self.df['남여구분'].dropna().unique())])

    def frame(self,b):
        opts=self.options()
        for k,v in b.model_dump().items():
            valid=[o['value'] for o in opts[k]] if k=='gender' else opts[k]
            if v not in valid:raise ValueError(f'{k}: 허용되지 않은 선택값입니다.')
        ref=self.reference
        group=ref[(ref['계약유형']==b.contract_type)&(ref['유통경로']==b.channel)&(ref['계약기간']==b.term)]
        basis='계약유형·유통경로·계약기간 일치 학습군'
        if len(group)<30:group=ref[ref['계약유형']==b.contract_type];basis='동일 계약유형 학습군 (상세 조합 30건 미만)'
        if group.empty:group=ref;basis='전체 학습군 (해당 계약유형 없음)'
        mode=lambda c:group[c].dropna().mode().iloc[0]
        row={'계약유형':b.contract_type,'유통경로':b.channel,'계약기간':b.term,'고객유형':b.customer_type,'남여구분':b.gender}
        for c in ['판매유형','제품군','시']:row[c]=str(mode(c))
        row['월랜탈비용']=float(pd.to_numeric(group['월랜탈비용'],errors='coerce').median())
        row['계약일']=pd.to_datetime(group['계약일']).sort_values().iloc[len(group)//2].date().isoformat()
        # User chooses age AT CONTRACT; compensate for Features.clean's 2026-base conversion.
        row['age_2026']=AGE_MAP[b.age_band]+2026-int(row['계약일'][:4]) if b.customer_type=='개인' else np.nan
        defaults=[dict(feature=c,value=row[c],basis=basis+(' 중앙값' if c in ['월랜탈비용','계약일'] else ' 최빈값')) for c in ['판매유형','제품군','시','월랜탈비용','계약일']]
        defaults.append(dict(feature='age_at_contract',value=AGE_MAP[b.age_band] if b.customer_type=='개인' else None,basis='계약 시점 연령대 중앙값; 사업자는 학습 전처리에 따라 연령 결측'))
        return pd.DataFrame([row]),defaults

    def predict(self,b,risk,example=False):
        frame,defaults=self.frame(b)
        if example:
            return dict(source='example_only',score=87.5,grade='보통',conditions=b.model_dump(),defaults=defaults,factors=[],
                        explanation='화면 확인용 고정 예시입니다. 입력 조건에 대한 AI 예측이 아닙니다.',actions=['정기 만족도 상담과 케어 일정 안내'],score_meaning='예시 점수 · 실제 모델 결과 아님')
        if not risk.bundle:raise RuntimeError('AI 모델이 연결되지 않았습니다. 별도의 화면 예시를 확인할 수 있습니다.')
        raw=risk.rm.predict_raw(risk.bundle,frame)
        score=float(risk.rm.score_percentile(raw,risk.bundle['reference'])[0])
        grade='높음' if score>=risk.bundle['high_cut'] else '보통' if score>=80 else '낮음'
        sv,names=risk.rm.explain_rows(risk.bundle,frame)
        indices=np.argsort(np.abs(sv[0]))[::-1][:5]
        factors=[dict(feature=names[i],contribution=float(sv[0,i]),direction='위험 증가' if sv[0,i]>0 else '위험 감소') for i in indices if abs(sv[0,i])>1e-8]
        strategies={'높음':['담당 코디의 사전 상담 및 서비스 불편 확인','요금 부담 확인 후 맞춤형 할인 혜택 검토','관리 방문·필터 교체 등 케어 서비스 강화'],
                    '보통':['정기 만족도 상담 및 케어 일정 사전 안내','약정 조건과 이용 혜택 재안내'],
                    '낮음':['현재 케어 품질과 정기 관리 유지','장기 이용 고객 프로모션 및 결합 혜택 안내']}
        actions=strategies[grade].copy()
        if any('유통경로' in f['feature'] and f['contribution']>0 for f in factors):actions.append('가입 채널에서 안내한 혜택과 실제 서비스의 일치 여부 확인')
        return dict(source='joblib_model',score=score,grade=grade,conditions=b.model_dump(),defaults=defaults,default_source=self.default_source,
                    factors=factors,actions=actions,score_meaning=risk.bundle['score_meaning'],
                    explanation=f'입력 조건과 대표값을 적용한 계약의 상대 위험 수준은 {grade}입니다. 기준 정상 고객군 대비 백분위 점수이며 미래 해약 확률이 아닙니다. 주요 변수는 모델 기여도이며 실제 해약 원인을 의미하지 않습니다.')
