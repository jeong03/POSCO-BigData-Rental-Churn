"""WOW Company API (FastAPI)
- 실제 데이터: rental_sales_member_merged.csv
- 시연용 가상 데이터: 코디/방문일/필터/AS/프로모션/상품명 (고객ID 기반 결정적 생성, 응답에 demo 표시)
- 위험 점수: joblib 모델이 있으면 risk_model.predict_customers 사용(source=joblib_model),
  없으면 CSV 과거 해약률 기반 임시 점수(source=demo_heuristic) — 응답마다 source 로 구분됩니다.
"""
import hashlib, json, math, os, random, secrets, sqlite3, sys, time, urllib.request
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))
CSV = Path(os.getenv("WOW_CSV", BASE / "data" / "rental_sales_member_merged.csv"))
MODEL_PATH = Path(os.getenv("WOW_MODEL_PATH", BASE / "models" / "wow_risk_model.joblib"))
DB = Path(os.getenv("WOW_DB", BASE / "wow.db"))
ADMIN_ID = os.getenv("WOW_ADMIN_ID", "WOW-A0001")
ADMIN_PW = os.getenv("WOW_ADMIN_PASSWORD", "wow1234!")
DEMO_MODE = os.getenv("WOW_DEMO_MODE", "1") == "1"
NOTEBOOK_METRICS = {"model": "D_enhanced (RandomForest)", "test_AP": 0.565, "test_ROC_AUC": 0.861,
                    "test_recall": 0.503, "cv_AP": 0.604, "source": "노트북 출력값(참고용)"}

# ───────────────────────── 데이터 ─────────────────────────
df = pd.read_csv(CSV, dtype={"고객ID": str})
df["계약유형"] = df["계약유형"].replace({"멥버십C": "멤버십C"})
active = df[df["계약상태"] == "계약확정"].reset_index(drop=True)
ACT_IDX = active.groupby("고객ID").indices
ALL_IDX = df.groupby("고객ID").indices

# CSV 에는 모델 코드만 있어 상품명은 시연용 매핑입니다. 실제 상품 마스터가 생기면 이 표만 교체하세요.
PRODUCT = {
    "CP-7211": dict(name="WOW 아이스 정수기", cat="정수기", kind="purifier"),
    "CPI-7400": dict(name="WOW 아이스 플러스 정수기", cat="정수기", kind="purifier"),
    "CHP-5610": dict(name="WOW 냉온 정수기", cat="정수기", kind="purifier"),
    "CP-8310": dict(name="WOW 슬림 정수기", cat="정수기", kind="purifier"),
    "P-150": dict(name="WOW 에어 퓨어", cat="공기청정기", kind="air"),
    "CHP-700": dict(name="WOW 슬림 비데", cat="비데", kind="bidet"),
}
CATALOG = [  # 시연용 카탈로그(가격·혜택은 가상, 정수기 가격은 CSV 중앙값)
    dict(id="air", name="WOW 에어 퓨어", cat="공기청정기", kind="air", price=19900, badge="인기",
         why="환기가 어려운 계절에도 집 공기를 깨끗하게 지켜줘요.", fit=[(25, 49, 1.5, "가족이 함께 쓰는 공간의 공기 관리에 잘 맞아요.")]),
    dict(id="bidet", name="WOW 슬림 비데", cat="비데", kind="bidet", price=17900, badge="추천",
         why="매일 쓰는 욕실 위생을 간편하게 관리해요.", fit=[(50, 120, 1.5, "방문 관리로 위생을 꾸준히 챙길 수 있어 연령대에 인기가 높아요.")]),
    dict(id="mattress", name="WOW 슬림 케어 매트리스", cat="매트리스", kind="mattress", price=29900, badge="신규",
         why="정기 케어로 깨끗한 수면 환경을 유지해요.", fit=[(30, 49, 1.2, "수면 환경 관리에 관심이 많은 연령대의 선택이 많아요.")]),
    dict(id="softener", name="WOW 소프트 연수기", cat="연수기", kind="softener", price=19900, badge="",
         why="정수기와 함께 쓰면 집 전체 물 관리가 한결 편해져요.", fit=[(35, 120, 0.8, "정수기 이용 고객의 결합 상품으로 많이 선택해요.")]),
    dict(id="chair", name="WOW 힐링 안마의자", cat="안마의자", kind="chair", price=49900, badge="",
         why="집에서 편하게 피로를 풀 수 있어요.", fit=[(55, 120, 1.4, "휴식과 건강 관리를 중시하는 분께 어울려요.")]),
    dict(id="purifier", name="WOW 아이스 정수기", cat="정수기", kind="purifier", price=23400, badge="베스트",
         why="WOW 대표 상품으로, 신규 고객이 가장 많이 선택해요.", fit=[(0, 120, 1.0, "처음 렌탈하시는 분께 가장 무난한 대표 상품이에요.")]),
]
PROMOS = [  # 시연용 가상 프로모션
    dict(id="P-NEW", audience="new", title="신규 고객 웰컴 혜택", desc="첫 렌탈 계약 시 설치비 면제 + 첫 달 렌탈료 할인"),
    dict(id="P-BUNDLE", audience="all", title="함께 쓰면 더 가벼워져요", desc="이용 중인 제품에 추가 렌탈 시 월 렌탈료 혜택"),
    dict(id="P-CARE", audience="retention", title="장기 이용 고객 케어 프로모션", desc="무상 케어 방문 1회 + 필터 업그레이드 쿠폰"),
]
COORDIS = ["김수현", "이도윤", "박서연", "최지후", "정하은", "강민재", "윤서아", "한지호"]
CENTERS = ["강남 케어센터", "수원 케어센터", "부산 케어센터", "대구 케어센터", "인천 케어센터", "광주 케어센터"]
CARE = {"정수기": ["필터 교체 주기에 맞춰 방문 케어를 받아보세요.", "장기간 미사용 시 물을 한 번 빼고 사용하세요."],
        "공기청정기": ["프리필터는 2주에 한 번 먼지를 털어주세요.", "벽에서 30cm 이상 띄워 두면 효율이 좋아요."],
        "비데": ["노즐 자동세척 후 주 1회 물티슈로 닦아주세요.", "겨울철엔 온수 설정 온도를 점검하세요."]}


def seeded(key):
    return random.Random(int(hashlib.sha256(key.encode()).hexdigest()[:12], 16))


def num(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return v.item() if isinstance(v, np.generic) else v


def contract_view(r):
    code = r["제품군"]
    p = PRODUCT.get(code, dict(name=f"WOW 렌탈 상품({code})", cat="기타", kind="purifier"))
    start = pd.Timestamp(r["계약일"])
    end = start + pd.DateOffset(months=int(r["계약기간"]))
    return dict(product_code=code, product_name=p["name"], category=p["cat"], kind=p["kind"],
                monthly_fee=int(r["월랜탈비용"]), term_months=int(r["계약기간"]), start_date=start.date().isoformat(),
                end_date=end.date().isoformat(), sales_type=r["판매유형"], contract_type=r["계약유형"],
                channel=r["유통경로"], pay_type=r["납부유형"], status=r["계약상태"])


def next_cycle(start, months, today):
    n = 1
    d = start + pd.DateOffset(months=months)
    while d.date() <= today and n < 400:
        n += 1
        d = start + pd.DateOffset(months=months * n)
    return d.date()


def demo_care(cid, contracts):  # 시연용 가상 데이터
    rnd = seeded(cid)
    today = date.today()
    coordi = dict(name=rnd.choice(COORDIS), center=rnd.choice(CENTERS), rating=round(rnd.uniform(4.3, 5.0), 1),
                  review_count=rnd.randint(40, 420), demo=True)
    slot = rnd.choice(["09:00 - 11:00", "11:00 - 13:00", "14:00 - 16:00", "16:00 - 18:00"])
    for c in contracts:
        s = pd.Timestamp(c["start_date"])
        c["next_visit"] = next_cycle(s, 4, today).isoformat()
        c["next_filter"] = next_cycle(s, 6, today).isoformat()
        c["visit_slot"] = slot
        c["care_tips"] = CARE.get(c["category"], ["정기 방문 케어를 이용해 주세요."])
    as_hist = [dict(id=f"D-{i}", date=(pd.Timestamp(today) - pd.Timedelta(days=rnd.randint(60, 500))).date().isoformat(),
                    title=rnd.choice(["출수량 점검", "필터 교체 문의", "소음 점검"]), status="처리완료", demo=True)
               for i in range(rnd.randint(0, 2))]
    return coordi, as_hist


# ───────────────────────── DB ─────────────────────────
def run(sql, args=(), fetch=False):
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    try:
        cur = c.execute(sql, args)
        rows = [dict(r) for r in cur.fetchall()] if fetch else None
        c.commit()
        return rows if fetch else cur.lastrowid
    finally:
        c.close()


for stmt in [
    "CREATE TABLE IF NOT EXISTS as_requests(id INTEGER PRIMARY KEY, customer_id TEXT, product_code TEXT, symptom TEXT, preferred_date TEXT, memo TEXT, status TEXT, created_at TEXT)",
    "CREATE TABLE IF NOT EXISTS consultations(id INTEGER PRIMARY KEY, receipt_no TEXT, customer_id TEXT, name TEXT, phone TEXT, topic TEXT, interest TEXT, memo TEXT, consent INTEGER, created_at TEXT)",
    "CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY, customer_id TEXT, rating INTEGER, comment TEXT, created_at TEXT)",
    "CREATE TABLE IF NOT EXISTS chat_logs(id INTEGER PRIMARY KEY, customer_id TEXT, role TEXT, text TEXT, created_at TEXT)",
    "CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY, customer_id TEXT, text TEXT, created_by TEXT, created_at TEXT)",
    "CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT)"]:
    run(stmt)
now = lambda: datetime.now().isoformat(timespec="seconds")

# ───────────────────────── 위험 점수 서비스 ─────────────────────────
GRADE_HIGH, GRADE_MID = 95.0, 80.0


def _model_frame(frame):
    return frame.drop(columns=[c for c in ["해약", "해약여부"] if c in frame])


class RiskService:
    def __init__(self):
        self.bundle = self.rm = None
        self.error = "모델 파일(joblib)이 아직 연결되지 않았습니다."
        self.table = None
        self._reasons = {}
        if MODEL_PATH.exists():
            try:
                import joblib, risk_model
                b = joblib.load(MODEL_PATH)
                miss = set(risk_model.REQUIRED) - set(active.columns)
                if miss:
                    raise ValueError("CSV에 모델 필수 열 없음: " + ", ".join(sorted(miss)))
                self.bundle, self.rm, self.error = b, risk_model, None
            except Exception as e:  # 모델 로드 실패 → 시연용 점수로 폴백하되 오류는 노출
                self.error = f"모델 로드 실패: {e}"
        self.source = "joblib_model" if self.bundle else "demo_heuristic"
        self._build()

    def _build(self):
        if self.bundle:
            out = self.rm.predict_customers(self.bundle, _model_frame(active), with_reasons=False)
            t = pd.DataFrame({"cid": out["고객ID"], "score": out["위험점수"].astype(float), "grade": out["위험등급"],
                              "rank": out["관리우선순위"].astype(int), "rep": out["representative_row"].astype(int),
                              "n": out["정상계약기록수"].astype(int)})
        else:
            lab = df[df["계약상태"].isin(["계약확정", "해약확정"])]
            p0 = (lab["해약여부"] == "해약").mean()
            self.cols = ["판매유형", "계약유형", "유통경로", "제품군"]
            self.rate = {c: ((lab[lab["해약여부"] == "해약"].groupby(c).size().reindex(lab[c].unique(), fill_value=0) + 50 * p0)
                             / (lab.groupby(c).size() + 50)).to_dict() for c in self.cols}
            self.p0 = float(p0)
            lr = np.mean([np.log(active[c].map(self.rate[c]).fillna(p0) / p0) for c in self.cols], axis=0)
            active["_s"] = np.exp(lr)
            g = active.groupby("고객ID")["_s"].agg(["max", "size"])
            rep = active.groupby("고객ID")["_s"].idxmax()
            t = pd.DataFrame({"cid": g.index, "raw": g["max"].to_numpy(), "n": g["size"].to_numpy(), "rep": rep.loc[g.index].to_numpy()})
            t["score"] = t["raw"].rank(pct=True) * 100
            t["grade"] = np.select([t["score"] >= GRADE_HIGH, t["score"] >= GRADE_MID], ["고위험", "중위험"], default="저위험")
            t = t.sort_values(["raw", "cid"], ascending=[False, True]).reset_index(drop=True)
            t["rank"] = np.arange(1, len(t) + 1)
        self.table = t.sort_values("rank").reset_index(drop=True)
        self.by_id = self.table.set_index("cid")

    def reasons(self, cid):
        """주요 위험 관련 특성. SHAP/과거해약률 모두 '예측 기여요인·상관'이며 인과가 아님."""
        if cid in self._reasons:
            return self._reasons[cid]
        rows = active.iloc[ACT_IDX[cid]]
        if self.bundle:
            try:
                o = self.rm.predict_customers(self.bundle, _model_frame(rows), with_reasons=True)
                r = [s for s in o["주요위험요인_SHAP"].iloc[0].split("; ") if s]
            except Exception as e:
                r = [f"SHAP 계산 실패: {e}"]
        else:
            row = active.iloc[int(self.by_id.loc[cid, "rep"])]
            items = [(self.rate[c].get(row[c], self.p0) / self.p0, c, row[c], self.rate[c].get(row[c], self.p0)) for c in self.cols]
            r = [f"{c}={v} (과거 해약률 {rt:.1%} / 전체 {self.p0:.1%})" for ratio, c, v, rt in sorted(items, reverse=True) if ratio > 1.1]
        self._reasons[cid] = r
        return r

    def single(self, cid):
        """고객 단건 조회. 실제 모델: 해당 고객 계약만으로 재계산(배치 내부 순위 사용 안 함)."""
        base = dict(source=self.source, customer_id=cid)
        if self.bundle:
            o = self.rm.predict_customers(self.bundle, _model_frame(active.iloc[ACT_IDX[cid]]), with_reasons=True).iloc[0]
            base.update(score=float(o["위험점수"]), grade=o["위험등급"], contracts_scored=int(o["정상계약기록수"]),
                        population_rank=int(o["기준고객군예상순위"]) if "기준고객군예상순위" in o else None,
                        reasons=[s for s in o["주요위험요인_SHAP"].split("; ") if s])
            self._reasons[cid] = base["reasons"]
        else:
            r = self.by_id.loc[cid]
            base.update(score=float(r["score"]), grade=r["grade"], contracts_scored=int(r["n"]),
                        population_rank=int(r["rank"]), reasons=self.reasons(cid))
        base["score_meaning"] = ("Train OOF 정상 고객 최대 계약 점수 대비 백분위(미래 해약 확률 아님)" if self.bundle else
                                 "시연용 임시 점수: CSV 과거 해약률 기반 상대 순위(실제 AI 모델 아님, 확률 아님)")
        return base


RISK = RiskService()
from manual_prediction import ManualPredictor, Conditions
from presentation_data import operational_timeline
MANUAL = ManualPredictor(df, MODEL_PATH.parent / 'default_reference.csv')
if RISK.bundle and RISK.bundle.get('metrics'):
    NOTEBOOK_METRICS = RISK.bundle['metrics']


def actions_for(reasons):
    t = " ".join(reasons)
    a = []
    if any(k in t for k in ["relative_price", "월랜탈비용", "total_amount", "제품군"]):
        a.append("약정 요금·혜택 이해 여부와 부담을 직접 확인")
    if any(k in t for k in ["계약유형", "계약기간", "sales_contract", "판매유형"]):
        a.append("연장·약정 조건 안내 및 이용 만족 확인")
    if any(k in t for k in ["유통경로", "type_channel"]):
        a.append("가입 채널의 안내 내용과 실제 서비스 일치 여부 확인")
    return (a or ["사용 불편·관리 방문 만족을 직접 확인(인구특성만으로 대응 결정 금지)"]) + ["고객 동의 기반 상담, 계약 변경은 고객 확인 후 진행"]


# ───────────────────────── 인증 ─────────────────────────
SESS = {}


def session(authorization: str = Header(None)):
    tok = (authorization or "").removeprefix("Bearer ").strip()
    s = SESS.get(tok)
    if s and s["exp"] < time.time():
        SESS.pop(tok, None)
        s = None
    return s


def need_customer(s=Depends(session)):
    if not s or s["role"] != "customer":
        raise HTTPException(401, "고객 로그인이 필요합니다.")
    return s


def need_admin(s=Depends(session)):
    if not s or s["role"] != "admin":
        raise HTTPException(403, "관리자 권한이 필요합니다.")
    return s


def new_session(role, uid):
    tok = secrets.token_urlsafe(32)
    SESS[tok] = dict(role=role, id=uid, exp=time.time() + 8 * 3600)
    return tok


app = FastAPI(title="WOW Company API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("WOW_CORS", "http://localhost:5173").split(","),
                   allow_methods=["*"], allow_headers=["*"])


class CustomerLogin(BaseModel):
    customer_id: str


class AdminLogin(BaseModel):
    admin_id: str
    password: str


@app.get("/api/status")
def status():
    return dict(model=dict(connected=bool(RISK.bundle), source=RISK.source, error=RISK.error, path=str(MODEL_PATH),
                           candidate=(RISK.bundle or {}).get("candidate"), version=(RISK.bundle or {}).get("version"),
                           notebook_metrics=NOTEBOOK_METRICS),
                data=dict(contracts=len(df), customers=df["고객ID"].nunique(), active_customers=len(ACT_IDX),
                          date_min=df["계약일"].min(), date_max=df["계약일"].max()),
                llm=dict(enabled=bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("LLM_API_KEY"))), demo_mode=DEMO_MODE)


@app.get("/api/demo/sample-customers")
def samples():
    if not DEMO_MODE:
        return []
    t = RISK.table
    multi = t[t["n"] >= 2]
    pick = [("고위험 시연", t[t["grade"] == "고위험"].iloc[3]), ("중위험 시연", t[t["grade"] == "중위험"].iloc[3]),
            ("저위험 · 2건 계약", multi[multi["grade"] == "저위험"].iloc[0]), ("저위험 시연", t[t["grade"] == "저위험"].iloc[5])]
    return [dict(customer_id=r["cid"], label=l) for l, r in pick]


@app.post("/api/auth/customer")
def login_customer(b: CustomerLogin):
    cid = b.customer_id.strip()
    if cid not in ALL_IDX:
        raise HTTPException(404, "등록되지 않은 고객ID입니다.")
    if cid not in ACT_IDX:
        raise HTTPException(403, "이용 중인 정상 계약이 없는 고객입니다.")
    return dict(token=new_session("customer", cid), role="customer", id=cid)


@app.post("/api/auth/admin")
def login_admin(b: AdminLogin):
    if not (secrets.compare_digest(b.admin_id, ADMIN_ID) and secrets.compare_digest(b.password, ADMIN_PW)):
        raise HTTPException(401, "관리자 ID 또는 비밀번호가 올바르지 않습니다.")
    return dict(token=new_session("admin", b.admin_id), role="admin", id=b.admin_id)


@app.post("/api/auth/logout")
def logout(authorization: str = Header(None)):
    SESS.pop((authorization or "").removeprefix("Bearer ").strip(), None)
    return dict(ok=True)


# ───────────────────────── 상품·추천·상담 (공개) ─────────────────────────
def pub(p):
    return {k: v for k, v in p.items() if k not in ("fit", "why")} | dict(price_is_demo=True, demo_asset=True, source="presentation_catalog")


def recommend(age, gender, owned, interest=None):
    out = []
    cohort = active
    if gender in ('남자','여자'):
        cohort = cohort[cohort['남여구분'].eq(gender)]
    if age is not None:
        cohort = cohort[pd.to_numeric(cohort['age_2026'],errors='coerce').between((age//10)*10,(age//10)*10+9)]
    affinity = cohort['제품군'].map(lambda c: PRODUCT.get(c,{}).get('cat','기타')).value_counts(normalize=True)
    for p in CATALOG:
        if p["cat"] in owned:
            continue
        s, why = 1.0 + float(affinity.get(p["cat"],0)), p["why"]
        if age is not None:
            for lo, hi, bonus, txt in p["fit"]:
                if lo <= age <= hi:
                    s += bonus
                    why = txt
        if '정수기' in owned and p['cat']=='연수기':
            s += .6
            why = '이용 중인 정수기와 함께 생활 속 물 관리를 완성해 보세요.'
        if interest and interest == p["cat"]:
            s += 2
            why = f"관심 제품군({interest})과 일치해요. " + p["why"]
        out.append(pub(p) | dict(score=s, reason=why))
    return sorted(out, key=lambda x: -x["score"])[:3]


@app.get("/api/products")
def products():
    return [pub(p) for p in CATALOG]


@app.get("/api/promotions")
def promotions(audience: str = "new"):
    return [p | dict(demo=True) for p in PROMOS if p["audience"] in (audience, "all")]


class Rec(BaseModel):
    age: int | None = None
    gender: str | None = None
    interest: str | None = None


@app.post("/api/public/recommend")  # 신규 고객: 위험 모델 미사용, 별도 규칙 기반 추천
def pub_recommend(b: Rec):
    return dict(items=recommend(b.age, b.gender, set(), b.interest), method="규칙 기반 추천(해약 위험 모델 미사용)")


class Consult(BaseModel):
    name: str = ""
    phone: str = ""
    topic: str = "렌탈 계약 상담"
    interest: str = ""
    memo: str = ""
    consent: bool = False


@app.post("/api/public/consult")
def consult(b: Consult, s=Depends(session)):
    cid = s["id"] if s and s["role"] == "customer" else None
    if not b.consent:
        raise HTTPException(400, "개인정보 수집·이용에 동의해야 상담을 신청할 수 있습니다.")
    if not cid and (not b.name.strip() or len(b.phone.replace("-", "")) < 9):
        raise HTTPException(400, "이름과 연락처를 입력해 주세요.")
    rid = run("INSERT INTO consultations(customer_id,name,phone,topic,interest,memo,consent,created_at) VALUES(?,?,?,?,?,?,1,?)",
              (cid, b.name.strip(), b.phone.strip(), b.topic, b.interest, b.memo, now()))
    no = f"C{datetime.now():%Y%m%d}-{rid:04d}"
    run("UPDATE consultations SET receipt_no=? WHERE id=?", (no, rid))
    return dict(receipt_no=no, message="상담 신청이 접수되었습니다. 담당자가 확인 후 연락드립니다.")


# ───────────────────────── 고객 ─────────────────────────
@app.get("/api/me")
def me(s=Depends(need_customer)):
    cid = s["id"]
    rows = active.iloc[ACT_IDX[cid]]
    contracts = [contract_view(r) for _, r in rows.iterrows()]
    coordi, as_hist = demo_care(cid, contracts)
    first = rows.iloc[0]
    age = num(first["age_2026"])
    owned = {c["category"] for c in contracts}
    grade = RISK.by_id.loc[cid, "grade"]
    db_as = run("SELECT * FROM as_requests WHERE customer_id=? ORDER BY id DESC", (cid,), True)
    db_con = run("SELECT receipt_no,topic,memo,created_at FROM consultations WHERE customer_id=? ORDER BY id DESC", (cid,), True)
    nxt = min(contracts, key=lambda c: c["next_visit"])
    return dict(
        customer_id=cid, profile=dict(type=first["고객유형"], region=first["시"], gender=num(first["남여구분"]), age=age),
        contracts=contracts, total_monthly=sum(c["monthly_fee"] for c in contracts), coordi=coordi,
        next_visit=dict(date=nxt["next_visit"], slot=nxt["visit_slot"], product=nxt["product_name"], demo=True),
        as_requests=db_as, as_history_demo=as_hist, consults=db_con,
        recommendations=recommend(age, num(first["남여구분"]), owned),
        promotions=sorted([p | dict(demo=True) for p in PROMOS if p["audience"] == "all" or (p["audience"] == "retention" and grade in ("고위험", "중위험"))],
                          key=lambda p: p["audience"] != "retention"),
        reviews=run("SELECT rating,comment,created_at FROM reviews WHERE customer_id=? ORDER BY id DESC LIMIT 3", (cid,), True))


class ASReq(BaseModel):
    product_code: str
    symptom: str
    preferred_date: str = ""
    memo: str = ""


@app.post("/api/me/as")
def as_create(b: ASReq, s=Depends(need_customer)):
    if b.product_code not in set(active.iloc[ACT_IDX[s["id"]]]["제품군"]):
        raise HTTPException(400, "이용 중인 제품이 아닙니다.")
    rid = run("INSERT INTO as_requests(customer_id,product_code,symptom,preferred_date,memo,status,created_at) VALUES(?,?,?,?,?,?,?)",
              (s["id"], b.product_code, b.symptom, b.preferred_date, b.memo, "접수", now()))
    return dict(id=rid, message="AS 신청이 접수되었습니다.")


class Review(BaseModel):
    rating: int
    comment: str = ""


@app.post("/api/me/review")
def review(b: Review, s=Depends(need_customer)):
    if not 1 <= b.rating <= 5:
        raise HTTPException(400, "평점은 1~5 입니다.")
    run("INSERT INTO reviews(customer_id,rating,comment,created_at) VALUES(?,?,?,?)", (s["id"], b.rating, b.comment, now()))
    return dict(ok=True)


# ───────────────────────── 챗봇 ─────────────────────────
SYSTEM = ("당신은 렌탈 기업 WOW Company 의 상담 챗봇입니다. 아래 제공된 상품·고객 정보만 근거로 한국어로 짧게 답하세요. "
          "모르는 내용은 상담 신청을 안내하고, 계약 변경·해지·신청을 임의로 확정하지 마세요. 프로모션 금액을 지어내지 마세요.\n"
          "상품: " + ", ".join(f"{p['name']}({p['cat']})" for p in CATALOG))


class Chat(BaseModel):
    message: str


def llm_reply(msg, ctx):
    key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("LLM_API_KEY")
    if not key:
        return None
    body = json.dumps(dict(model=os.getenv("LLM_MODEL", "claude-sonnet-5-5"), max_tokens=500, system=SYSTEM + "\n" + ctx,
                           messages=[dict(role="user", content=msg)])).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", body,
                                 {"content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)["content"][0]["text"]
    except Exception:
        return None


@app.post("/api/chat")
def chat(b: Chat, s=Depends(session)):
    cid = s["id"] if s and s["role"] == "customer" else None
    contracts = [contract_view(r) for _, r in active.iloc[ACT_IDX[cid]].iterrows()] if cid else []
    ctx = "고객 이용 중 계약: " + "; ".join(f"{c['product_name']} 월 {c['monthly_fee']:,}원, {c['term_months']}개월, 계약일 {c['start_date']}" for c in contracts) if cid else "비로그인(신규) 고객"
    m, action, src = b.message, None, "rule"
    reply = llm_reply(m, ctx)
    if reply:
        src = "llm"
    elif any(k in m for k in ["고장", "AS", "에이에스", "안 나", "안나", "새", "소리", "냄새", "수리"]):
        reply, action = "불편을 드려 죄송해요. 증상을 확인해 AS 접수를 도와드릴게요. 아래 버튼에서 신청하시면 담당자가 방문 일정을 안내해요.", dict(type="as", label="AS 신청하기") if cid else dict(type="consult", label="상담 신청하기")
    elif any(k in m for k in ["필터", "교체", "관리", "청소", "세척"]):
        reply = "필터는 보통 6개월 주기로, 방문 케어는 4개월 주기로 안내돼요. " + ("나의 렌탈 현황에서 제품별 다음 일정을 확인하실 수 있어요." if cid else "")
    elif any(k in m for k in ["요금", "렌탈료", "약정", "계약", "납부"]):
        reply = ("이용 중인 계약은 " + ctx.split(": ", 1)[1] + " 이에요. " if cid else "") + "계약 변경·해지는 챗봇이 확정할 수 없어요. 상담 신청을 남겨주시면 담당자가 안내드려요."
        action = dict(type="consult", label="상담 신청하기")
    elif any(k in m for k in ["추천", "신제품", "프로모션", "혜택", "이벤트"]):
        reply = "고객님께 맞는 상품과 진행 중인 프로모션을 안내해 드릴 수 있어요. 홈 화면의 추천 영역에서 확인해 보세요. 세부 조건은 상담으로 확인이 필요해요."
        action = dict(type="consult", label="상담 신청하기")
    else:
        reply, action = "해당 문의는 챗봇이 정확히 답하기 어려워요. 상담 신청을 남겨주시면 담당자가 확인 후 연락드릴게요.", dict(type="consult", label="상담 신청하기")
    for role, text in (("user", m), ("bot", reply)):
        run("INSERT INTO chat_logs(customer_id,role,text,created_at) VALUES(?,?,?,?)", (cid, role, text, now()))
    return dict(reply=reply, action=action, source=src, llm_enabled=src == "llm")


# ───────────────────────── 관리자 ─────────────────────────
def setting(k, d):
    r = run("SELECT v FROM settings WHERE k=?", (k,), True)
    return float(r[0]["v"]) if r else d


class Target(BaseModel):
    target_cancel_rate: float


@app.put("/api/admin/settings")
def put_settings(b: Target, _=Depends(need_admin)):
    if not 0 < b.target_cancel_rate < 100:
        raise HTTPException(400, "목표 해약률은 0~100(%) 사이여야 합니다.")
    run("INSERT OR REPLACE INTO settings(k,v) VALUES('target_cancel_rate',?)", (str(b.target_cancel_rate),))
    return dict(ok=True)


@app.get("/api/admin/dashboard")
def dashboard(_=Depends(need_admin)):
    lab = df["해약여부"] == "해약"
    n_act = len(ACT_IDX)
    t = RISK.table
    trend = df.assign(d=pd.to_datetime(df["계약일"])).set_index("d").resample("W").size()
    by_prod = df[df["계약상태"] == "계약확정"].groupby("제품군").size()
    by_sales = df.groupby("판매유형").agg(contracts=("고객ID", "size"), cancel=("해약", "sum"))
    return dict(
        operational=operational_timeline(n_act), data_sources={"kpi":"actual_csv","operational":"presentation_synthetic","risk":RISK.source},
        source=RISK.source, model_connected=bool(RISK.bundle),
        kpi=dict(total_customers=int(df["고객ID"].nunique()), active_customers=n_act, total_contracts=len(df),
                 cancelled_contracts=int(lab.sum()), cancel_rate_contract=float(lab.mean() * 100),
                 cancel_rate_customer=float(df[lab]["고객ID"].nunique() / df["고객ID"].nunique() * 100)),
        grades={g: int((t["grade"] == g).sum()) for g in ["고위험", "중위험", "저위험"]},
        top=[dict(pct=p, count=math.ceil(n_act * p / 100), min_score=float(t["score"].iloc[math.ceil(n_act * p / 100) - 1])) for p in (5, 10, 20)],
        by_product=[dict(code=k, name=PRODUCT.get(k, {}).get("name", k), contracts=int(v)) for k, v in by_prod.items()],
        by_sales=[dict(name=k, contracts=int(r["contracts"]), cancelled=int(r["cancel"])) for k, r in by_sales.iterrows()],
        trend=[dict(week=k.date().isoformat(), contracts=int(v)) for k, v in trend.items()],
        target=dict(target_cancel_rate=setting("target_cancel_rate", 1.8), current=float(lab.mean() * 100), basis="계약 단위 누적 해약 비율"),
        realtime=dict(available=False, reason="CSV에 해약 발생일이 없어 오늘/이달 해약률을 계산할 수 없습니다. 최신 데이터 연결 시 활성화됩니다."),
        filters=dict(sales=sorted(active["판매유형"].unique()), ctype=sorted(active["계약유형"].unique()), product=sorted(active["제품군"].unique())),
        model=dict(notebook_metrics=NOTEBOOK_METRICS, score_meaning=RISK.single(t["cid"].iloc[0])["score_meaning"]))


@app.get("/api/admin/risk-customers")
def risk_list(grade: str = "", sales: str = "", ctype: str = "", product: str = "", q: str = "", top: int = 0,
              page: int = 1, size: int = Query(20, le=100), _=Depends(need_admin)):
    t = RISK.table
    if top:
        t = t.iloc[: math.ceil(len(t) * top / 100)]
    rep = active.iloc[t["rep"].to_numpy()].reset_index(drop=True)
    t = t.reset_index(drop=True)
    m = pd.Series(True, index=t.index)
    if grade:
        m &= t["grade"] == grade
    if sales:
        m &= rep["판매유형"] == sales
    if ctype:
        m &= rep["계약유형"] == ctype
    if product:
        m &= rep["제품군"] == product
    if q:
        m &= t["cid"].str.contains(q.strip())
    sel = t[m]
    total = len(sel)
    sel = sel.iloc[(page - 1) * size: page * size]
    items = []
    for i, r in sel.iterrows():
        c = rep.iloc[i]
        cid = r["cid"]
        items.append(dict(customer_id=cid, score=float(r["score"]), grade=r["grade"], rank=int(r["rank"]), contracts=int(r["n"]),
                          sales_type=c["판매유형"], contract_type=c["계약유형"], product=PRODUCT.get(c["제품군"], {}).get("name", c["제품군"]),
                          channel=c["유통경로"], monthly_fee=int(c["월랜탈비용"]), top_reason=(RISK.reasons(cid) or ["-"])[0]))
    return dict(total=total, page=page, size=size, items=items, source=RISK.source)


def _legacy_detail(cid):
    if cid not in ALL_IDX:
        raise HTTPException(404, "고객ID를 찾을 수 없습니다.")
    if cid not in ACT_IDX:
        info = df.iloc[ALL_IDX[cid]].iloc[0]
        return dict(customer_id=cid, active=False, message="정상(계약확정) 계약이 없어 위험도를 산출하지 않습니다.",
                    profile=dict(type=info["고객유형"], region=info["시"]), contracts=[])
    rows = active.iloc[ACT_IDX[cid]]
    contracts = [contract_view(r) for _, r in rows.iterrows()]
    coordi, as_hist = demo_care(cid, contracts)
    f = rows.iloc[0]
    risk = RISK.single(cid)
    return dict(customer_id=cid, active=True, profile=dict(type=f["고객유형"], region=f["시"], gender=num(f["남여구분"]), age=num(f["age_2026"])),
                contracts=contracts, total_monthly=sum(c["monthly_fee"] for c in contracts), coordi=coordi, risk=risk,
                priority=("즉시 상담" if risk["grade"] == "고위험" else "우선 관리" if risk["grade"] == "중위험" else "일반 관리"),
                actions=actions_for(risk["reasons"]), as_count=len(as_hist) + run("SELECT COUNT(*) n FROM as_requests WHERE customer_id=?", (cid,), True)[0]["n"])


from recommendations import RecommendationService, report_lines
RECOMMENDATIONS = RecommendationService(run, CATALOG, PRODUCT, recommend)


def detail(cid):
    d = _legacy_detail(cid)
    rows = df.iloc[ALL_IDX[cid]]
    history = [contract_view(r) for _, r in rows.iterrows()]
    d['profile'] = {k: num(v) for k,v in d['profile'].items()}
    d['contract_history'] = history
    d.update(RECOMMENDATIONS.build(cid, rows, history))
    if d.get('business') and d.get('coordi'):
        d['coordi']['name'] = d['business']['coordi']
        d['as_count'] = len(d['business']['as_history']) + len(d.get('actual_as_history', []))
    d['rental_consultations'] = run('SELECT * FROM rental_consultations WHERE customer_id=? ORDER BY id DESC', (cid,), True)
    return d


@app.get("/api/admin/customer/{cid}")
def admin_customer(cid: str, _=Depends(need_admin)):
    return detail(cid.strip())


class ReportReq(BaseModel):
    customer_id: str
    note: str = ""


@app.post("/api/admin/report")
def report(b: ReportReq, s=Depends(need_admin)):
    d = detail(b.customer_id.strip())
    if not d["active"]:
        L = [f"[고객 관리 보고서] 고객ID {d['customer_id']}", f"작성일 {date.today()}", d['message']] + report_lines(d)
        if b.note.strip(): L += ['관리자 메모', b.note.strip()]
        text = "\n".join(L)
        rid = run("INSERT INTO reports(customer_id,text,created_by,created_at) VALUES(?,?,?,?)", (d['customer_id'], text, s['id'], now()))
        return dict(id=rid, text=text, sendable=False)

    r, p = d["risk"], d["profile"]
    L = [f"[고객 관리 보고서] 고객ID {d['customer_id']}", f"작성일 {date.today()} / 담당 코디(시연용 가상): {d['coordi']['name']} ({d['coordi']['center']})", "",
         "1. 고객 개요", (f"- 유형 {p['type']} / 지역 {p['region']}" if d.get('business') else f"- 유형 {p['type']} / 지역 {p['region']} / 성별 {p.get('gender') or '-'} / 나이 {p.get('age') or '-'}"),
         f"- 정상 계약 {len(d['contracts'])}건, 월 렌탈료 합계 {d['total_monthly']:,}원", "", "2. 이용 중 계약"]
    L += [f"- {c['product_name']}({c['product_code']}) {c['sales_type']}/{c['contract_type']} 월 {c['monthly_fee']:,}원, {c['term_months']}개월, 계약일 {c['start_date']}, 가입경로 {c['channel']}" for c in d["contracts"]]
    L += ["", "3. AI 위험 평가", f"- 평가 방식: {'실제 AI 모델(joblib)' if r['source'] == 'joblib_model' else '시연용 임시 점수(실제 AI 모델 아님)'}",
          f"- 위험점수 {r['score']:.1f} / 위험등급 {r['grade']} / 관리 우선순위 {d['priority']}", f"- 점수 의미: {r['score_meaning']}",
          "- 주요 위험 관련 특성(모델 기여요인·통계적 연관이며 해약의 실제 원인이 아님):"]
    L += [f"  · {x}" for x in r["reasons"]] or ["  · 없음"]
    L += ["", "4. 권장 상담·유지 방안(상담 가설, 효과 미검증)"] + [f"- {a}" for a in d["actions"]]
    if b.note.strip():
        L += ["", "5. 관리자 메모", b.note.strip()]
    L += ["", "※ 고객 동의 없이 계약을 변경하지 않으며, 본 점수는 미래 해약 확률이 아닌 상대적 관리 우선순위입니다."]
    L += report_lines(d)
    text = "\n".join(L)
    rid = run("INSERT INTO reports(customer_id,text,created_by,created_at) VALUES(?,?,?,?)", (d["customer_id"], text, s["id"], now()))
    return dict(id=rid, text=text, sendable=False, send_note="알림·메시징 연동 전이라 발송은 비활성입니다. 복사/다운로드를 사용하세요.")


@app.get("/api/admin/predict-options")
def predict_options(_=Depends(need_admin)):
    return dict(options=MANUAL.options(),model_connected=bool(RISK.bundle))


@app.post("/api/admin/predict-manual")
def predict_manual(payload: Conditions, _=Depends(need_admin)):
    try:
        return MANUAL.predict(payload,RISK)
    except ValueError as e:
        raise HTTPException(422,str(e))
    except RuntimeError as e:
        raise HTTPException(503,str(e))


@app.post("/api/admin/predict-example")
def predict_example(payload: Conditions, _=Depends(need_admin)):
    try:
        return MANUAL.predict(payload,RISK,example=True)
    except ValueError as e:
        raise HTTPException(422,str(e))

# Local coordination workflow only. This queues an internal request, never sends SMS/email.
run("CREATE TABLE IF NOT EXISTS report_handoffs(id INTEGER PRIMARY KEY, report_id INTEGER UNIQUE, status TEXT, created_at TEXT)")

@app.post('/api/admin/report/{report_id}/handoff')
def queue_report(report_id: int, _=Depends(need_admin)):
    if not run('SELECT id FROM reports WHERE id=?',(report_id,),True):
        raise HTTPException(404,'보고서를 찾을 수 없습니다.')
    run("INSERT OR IGNORE INTO report_handoffs(report_id,status,created_at) VALUES(?,?,?)",(report_id,'전달 요청 접수',now()))
    row=run('SELECT * FROM report_handoffs WHERE report_id=?',(report_id,),True)[0]
    return dict(id=row['id'],status=row['status'],source='local_workflow',message='코디 전달 요청이 저장되었습니다. 외부 문자·이메일은 발송되지 않습니다.')

from recommendation_api import install as install_recommendation_api
install_recommendation_api(app, run, need_admin, detail, now, BASE)
