import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

BASE_CAT=['판매유형','계약유형','유통경로','제품군','고객유형','시','남여구분']
BASE_NUM=['계약기간','월랜탈비용','age_at_contract']
REQUIRED=['판매유형','계약유형','유통경로','제품군','고객유형','시','남여구분','계약기간','월랜탈비용','age_2026','계약일']


class Features(BaseEstimator,TransformerMixin):
    def __init__(self,enhanced=False,omit_sex=False):
        self.enhanced=enhanced
        self.omit_sex=omit_sex
    def fit(self,X,y=None):
        d=self.clean(X)
        self.price_=d.groupby(['제품군','판매유형','계약기간'],dropna=False)['월랜탈비용'].median().to_dict()
        self.fallback_=float(d['월랜탈비용'].median())
        return self
    def clean(self,X):
        missing=set(REQUIRED)-set(X.columns)
        if missing:raise ValueError('필수 입력 열 누락: '+', '.join(sorted(missing)))
        d=X.copy()
        for c in BASE_CAT:d[c]=d[c].fillna('미상').astype(str).str.strip()
        d['계약유형']=d['계약유형'].replace({'멥버십C':'멤버십C'})
        for c in ['계약기간','월랜탈비용','age_2026']:d[c]=pd.to_numeric(d[c],errors='coerce')
        date=pd.to_datetime(d['계약일'],errors='coerce')
        if date.isna().any():raise ValueError('계약일은 유효한 YYYY-MM-DD여야 합니다.')
        if (d['계약기간'].le(0)|d['월랜탈비용'].lt(0)).any():raise ValueError('계약기간은 양수, 월랜탈비용은 0 이상이어야 합니다.')
        d['age_at_contract']=d['age_2026']-(2026-date.dt.year)
        d.loc[d['고객유형'].ne('개인'),'age_at_contract']=np.nan
        d.loc[~d['age_at_contract'].between(0,110),'age_at_contract']=np.nan
        d['contract_weekend']=np.where(date.dt.dayofweek.ge(5),'Weekend','Weekday')
        return d
    def transform(self,X):
        d=self.clean(X);cats=BASE_CAT.copy();nums=BASE_NUM.copy()
        if self.omit_sex:cats.remove('남여구분')
        if self.enhanced:
            d['total_amount_rebuilt']=d['월랜탈비용']*d['계약기간']
            med=np.array([self.price_.get(k,self.fallback_) for k in d[['제품군','판매유형','계약기간']].itertuples(index=False,name=None)])
            d['relative_price_rebuilt']=d['월랜탈비용'].to_numpy()/np.maximum(med,1)
            d['sales_contract']=d['판매유형']+'|'+d['계약유형']
            d['type_channel']=d['계약유형']+'|'+d['유통경로']
            cats+=['contract_weekend','sales_contract','type_channel'];nums+=['total_amount_rebuilt','relative_price_rebuilt']
        out=d[cats+nums].copy()

        return out


class NativeFill(BaseEstimator,TransformerMixin):
    def fit(self,X,y=None):return self
    def transform(self,X):
        d=X.copy()
        for c in d.select_dtypes(include='number'):d[c]=d[c].fillna(-999)
        return d


def aggregate_customers(frame,p,y=None):
    z=pd.DataFrame({'고객ID':frame['고객ID'].astype(str).to_numpy(),'raw_score':p})
    if y is not None:z['y']=np.asarray(y)
    agg={'raw_score':'max'}
    if y is not None:agg['y']='max'
    return z.groupby('고객ID',sort=True).agg(agg).reset_index()

def score_percentile(raw,reference):
    r=np.sort(reference)
    return 100*(np.searchsorted(r,raw,side='left')+np.searchsorted(r,raw,side='right'))/(2*len(r))


def predict_raw(bundle,frame):
    if bundle['strategy'] in ['B','C']:
        p=bundle['model'].predict_proba(frame)[:,1]
        group=frame['판매유형'].astype(str) if bundle['strategy']=='B' else frame['계약유형'].astype(str).replace({'멥버십C':'멤버십C'})
        for key,model in bundle['group_models'].items():
            mask=group.eq(key)
            if mask.any():p[mask]=model.predict_proba(frame.loc[mask])[:,1]
        return p
    return bundle['model'].predict_proba(frame)[:,1]

def predict_customers(bundle,frame,with_reasons=True):
    frame=pd.DataFrame(frame).copy().reset_index(drop=True)
    if '고객ID' not in frame:raise ValueError('고객ID가 필요합니다.')
    if frame['고객ID'].isna().any():raise ValueError('고객ID 결측 불가')
    if '계약상태' in frame and not frame['계약상태'].eq('계약확정').all():raise ValueError('운영 점수는 계약확정 계약에만 적용합니다.')
    raw=predict_raw(bundle,frame)
    chosen=pd.DataFrame({'고객ID':frame['고객ID'].astype(str),'p':raw,'row':np.arange(len(frame))}).sort_values(['p','row'],ascending=[False,True]).drop_duplicates('고객ID')
    out=chosen[['고객ID','row','p']].rename(columns={'p':'model_output','row':'representative_row'}).copy()
    out['위험점수']=score_percentile(out['model_output'].to_numpy(),bundle['reference'])
    out['위험등급']=np.select([out['위험점수']>=bundle['high_cut'],out['위험점수']>=80],['고위험','중위험'],default='저위험')
    out=out.sort_values(['model_output','고객ID'],ascending=[False,True]).reset_index(drop=True)
    out['관리우선순위']=np.arange(1,len(out)+1)
    if 'active_reference' in bundle:
        ref=np.sort(bundle['active_reference'])
        out['기준고객군예상순위']=len(ref)-np.searchsorted(ref,out['model_output'],side='right')+1
    out['정상계약기록수']=out['고객ID'].map(frame['고객ID'].astype(str).value_counts())
    if 'group_support' in bundle:
        flags=[]
        for row in out['representative_row']:
            record=frame.iloc[row];key=str(record['계약유형']).replace('멥버십C','멤버십C')
            support=bundle['group_support'].get(key,{})
            if support.get('n',0)<100 or support.get('positive',0)<30:flag='소표본 유형: 수동 검토 필수'
            elif record['판매유형']=='렌탈':flag='렌탈 구분력 제한: 상담 참고용'
            else:flag='미래 성능 미검증: 상담 참고용'
            flags.append(flag)
        out['검토유의사항']=flags
    if with_reasons:
        rows=out['representative_row'].to_numpy();sv,names=explain_rows(bundle,frame.iloc[rows])
        labels=[]
        for vals in sv:
            ix=np.argsort(vals)[::-1];pos=[i for i in ix if vals[i]>1e-8][:3]
            labels.append('; '.join(f'{names[i]} ({vals[i]:+.4f})' for i in pos) or '양의 SHAP 기여 없음')
        out['주요위험요인_SHAP']=labels
    return out


def explain_pipeline(pipe,frame):
    import shap
    x=pipe[:-1].transform(frame);m=pipe[-1]
    f=pipe[0].transform(frame)
    if m.__class__.__name__=='CatBoostClassifier':
        from catboost import Pool
        sv=m.get_feature_importance(Pool(x,cat_features=list(x.select_dtypes(exclude='number').columns)),type='ShapValues')[:,:-1]
        return sv,list(x.columns)
    if hasattr(pipe.named_steps['prep'],'get_feature_names_out'):
        expanded=pipe.named_steps['prep'].get_feature_names_out()
    else:expanded=np.array(f.columns)
    if m.__class__.__name__=='LogisticRegression':

        sv=(x-pipe._shap_background_mean)*m.coef_[0]
    else:
        sv=shap.TreeExplainer(m).shap_values(x)
        if isinstance(sv,list):sv=sv[1]
        if np.asarray(sv).ndim==3:sv=np.asarray(sv)[:,:,1]
    sv=np.asarray(sv);names=list(f.columns);merged=np.zeros((len(frame),len(names)))
    for j,name in enumerate(expanded):
        short=name.split('__',1)[-1]
        matches=[c for c in names if short==c or short.startswith(c+'_') or short=='missingindicator_'+c]
        if matches:merged[:,names.index(max(matches,key=len))]+=sv[:,j]
    return merged,names

def explain_rows(bundle,frame):
    if bundle['strategy'] not in ['B','C']:return explain_pipeline(bundle['model'],frame)
    group=frame['판매유형'].astype(str) if bundle['strategy']=='B' else frame['계약유형'].astype(str).replace({'멥버십C':'멤버십C'})
    all_names=list(bundle['model'][0].transform(frame).columns);out=np.zeros((len(frame),len(all_names)))
    for key in group.unique():
        mask=group.eq(key).to_numpy();v,n=explain_pipeline(bundle['group_models'].get(key,bundle['model']),frame.loc[mask])
        for j,c in enumerate(n):out[mask,all_names.index(c)]=v[:,j]
    return out,all_names

