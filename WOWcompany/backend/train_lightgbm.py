"""Notebook LightGBM_base_tuned reproduction, not the notebook's RF winner.
No test rows used for defaults, model fitting, grade policy or reference.
"""
from pathlib import Path
import json, hashlib, importlib.metadata
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.compose import ColumnTransformer, make_column_selector
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.metrics import average_precision_score, roc_auc_score, precision_recall_curve, recall_score
from lightgbm import LGBMClassifier
from risk_model import Features, REQUIRED, aggregate_customers

BASE=Path(__file__).parent
SEED=20261110

def make_pipe():
    prep=ColumnTransformer([
        ('num',Pipeline([('impute',SimpleImputer(strategy='median',add_indicator=True)),('scale',StandardScaler())]),make_column_selector(dtype_include=np.number)),
        ('cat',OneHotEncoder(handle_unknown='ignore',sparse_output=False,dtype=np.float32),make_column_selector(dtype_exclude=np.number))])
    return Pipeline([('features',Features(False,False)),('prep',prep),('model',LGBMClassifier(n_estimators=220,num_leaves=15,learning_rate=.04,min_child_samples=60,reg_lambda=10,class_weight=None,n_jobs=2,verbosity=-1,random_state=SEED))])

def main():
    raw=pd.read_csv(BASE/'data/rental_sales_member_merged.csv',dtype={'고객ID':str})
    d=raw.loc[raw['계약상태'].isin(['계약확정','해약확정'])].reset_index(drop=True)
    y=d['해약'].to_numpy();g=d['고객ID'].to_numpy()
    tr,te=next(StratifiedGroupKFold(n_splits=5,shuffle=True,random_state=SEED).split(d,y,g))
    x=d.iloc[tr].reset_index(drop=True);yt=y[tr];gt=g[tr]
    oof=np.zeros(len(x));aps=[]
    for i,(a,b) in enumerate(StratifiedGroupKFold(n_splits=5,shuffle=True,random_state=SEED+1).split(x,yt,gt)):
        m=make_pipe().fit(x.iloc[a],yt[a]);oof[b]=m.predict_proba(x.iloc[b])[:,1]
        aps.append(average_precision_score(yt[b],oof[b]));print('fold',i+1,aps[-1],flush=True)
    normal=x['계약상태'].eq('계약확정')
    reference=aggregate_customers(x.loc[normal],oof[normal]).raw_score.to_numpy()
    cs=aggregate_customers(x,oof,yt).sort_values('raw_score',ascending=False)
    top=cs.head(int(np.ceil(len(cs)*.05)))
    high_cut=95 if top.y.sum()/cs.y.sum()>=.5 else 90
    p,r,t=precision_recall_curve(yt,oof);threshold=float(t[np.argmax(2*p[:-1]*r[:-1]/np.maximum(p[:-1]+r[:-1],1e-12))])
    model=make_pipe().fit(x,yt);pt=model.predict_proba(d.iloc[te])[:,1]
    metrics=dict(model='LightGBM_base_tuned',test_AP=float(average_precision_score(y[te],pt)),test_ROC_AUC=float(roc_auc_score(y[te],pt)),test_recall=float(recall_score(y[te],pt>=threshold)),cv_AP=float(np.mean(aps)),source='retrained_lightgbm_heldout_test')
    bundle=dict(model=model,strategy='A',group_models={},reference=reference,high_cut=high_cut,threshold=threshold,required_features=REQUIRED,version='2.0',candidate='LightGBM_base_tuned',score_meaning='Train OOF 정상 고객 최대 계약 점수 대비 백분위; 미래 해약 확률 아님',metrics=metrics,provenance='Notebook LightGBM candidate retrained; original winner is RandomForest')
    out=BASE/'models';out.mkdir(exist_ok=True)
    joblib.dump(bundle,out/'wow_risk_model.joblib',compress=3)
    # Representative values from training partition only, no target labels persisted.
    x[REQUIRED].to_csv(out/'default_reference.csv',index=False)
    report=dict(metrics=metrics,high_cut=high_cut,train_rows=len(tr),test_rows=len(te),group_overlap=len(set(g[tr])&set(g[te])),csv_sha256=hashlib.sha256((BASE/'data/rental_sales_member_merged.csv').read_bytes()).hexdigest(),versions={k:importlib.metadata.version(k) for k in ['numpy','pandas','scikit-learn','lightgbm','joblib','shap']})
    (out/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
