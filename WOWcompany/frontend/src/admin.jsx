import { useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar,
  Cell,
} from "recharts";
import { api, downloadPdf } from "./api";
import { RecommendationPanel, BusinessPanel } from "./recommendations";
import {
  Card,
  Btn,
  Field,
  inputCls,
  won,
  useAsync,
  Logo,
  Err,
  Spin,
  SourceBadge,
  GradeChip,
  cls,
} from "./ui";

const D = true;
const NAV = [
  ["dashboard", "대시보드"],
  ["risk", "이탈 위험 고객"],
  ["lookup", "AI 해약 위험도 예측"],
];
const GC = { 고위험: "#f26d5b", 중위험: "#f5b94a", 저위험: "#34d399" };
const tip = {
  contentStyle: {
    background: "#3B4B63",
    border: "1px solid #52637A",
    borderRadius: 8,
    fontSize: 12,
  },
};

export function AdminApp({ tab, params, go, session }) {
  const st = useAsync(() => api("/status"), []);
  const m = st.data?.model;
  return (
    <div className="admin-theme min-h-screen bg-dk-bg text-slate-200 lg:flex">
      <aside className="bg-[#1E293B] lg:w-60 shrink-0 border-b lg:border-b-0 lg:border-r border-dk-line p-4 lg:min-h-screen flex flex-col gap-4">
        <Logo dark sub="BUSINESS CONSOLE" />
        <nav className="grid grid-cols-3 lg:flex lg:flex-col gap-1 lg:mt-4 text-xs lg:text-sm font-semibold">
          {NAV.map(([k, l]) => (
            <button
              key={k}
              onClick={() => go("#/a/" + k)}
              className={cls(
                "rounded-lg px-3 py-2.5 text-left",
                tab === k
                  ? "bg-dk-blue/20 text-white border-l-2 border-dk-blue"
                  : "text-slate-400 hover:bg-white/5",
              )}
            >
              {l}
            </button>
          ))}
        </nav>
        <div className="mt-auto rounded-xl border border-dk-line p-3 text-xs">
          <div className="flex items-center gap-2 font-bold">
            <i
              className={cls(
                "h-2 w-2 rounded-full",
                m?.connected ? "bg-emerald-400" : "bg-dk-amber",
              )}
            />
            {m?.connected ? "AI 모델 연결됨" : "AI 모델 연결 전"}
          </div>
          <p className="mt-1 text-slate-400">
            {m?.connected
              ? `${m.candidate} v${m.version}`
              : "모델 파일을 연결하면 분석을 시작할 수 있습니다."}
          </p>
          {m?.error &&
            m.connected === false &&
            m.error.startsWith("모델 로드") && (
              <p className="mt-1 text-dk-red">{m.error}</p>
            )}
          <div className="mt-3 text-slate-500">
            {session.id} · 운영관리자{" "}
            <button className="underline ml-1" onClick={() => go("#/", true)}>
              로그아웃
            </button>
          </div>
        </div>
      </aside>
      <main className="flex-1 p-5 lg:p-8 min-w-0">
        {tab === "dashboard" && <Dashboard go={go} />}

        {tab === "risk" && <RiskList params={params} go={go} />}

        {tab === "customer" && (
          <CustomerDetailPage key={params.id} id={params.id} go={go} />
        )}

        {tab === "lookup" && <Lookup params={params} />}
      </main>
    </div>
  );
}

const Kpi = ({ label, value, sub, tone }) => (
  <Card
    dark
    className={cls("p-4", tone === "red" && "!border-dk-red/40 bg-dk-red/5")}
  >
    <div className="text-xs text-slate-400">{label}</div>
    <div
      className={cls(
        "mt-1 text-2xl font-extrabold",
        tone === "red" ? "text-dk-red" : "text-white",
      )}
    >
      {value}
    </div>
    {sub && <div className="text-[11px] text-slate-500 mt-1">{sub}</div>}
  </Card>
);

function Dashboard({ go }) {
  const {
    data: d,
    error,
    loading,
    reload,
  } = useAsync(() => api("/admin/dashboard"), []);
  const [tr, setTr] = useState(""),
    [msg, setMsg] = useState("");
  if (loading) return <Spin dark />;
  if (error) return <Err dark msg={error} />;
  const k = d.kpi,
    t = d.target,
    o = d.operational;
  const saveT = async () => {
    try {
      await api("/admin/settings", {
        method: "PUT",
        body: { target_cancel_rate: +tr },
      });
      setMsg("저장되었습니다.");
      reload();
    } catch (e) {
      setMsg(e.message);
    }
  };
  const pct = Math.min(100, (t.current / t.target_cancel_rate) * 100);
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-extrabold text-white">
            고객 현황 대시보드
          </h1>
          <p className="text-sm text-slate-400">
            고객 계약 현황과 관리 우선순위를 한눈에 확인하세요.
          </p>
        </div>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Kpi
          label="전체 고객 수"
          value={`${k.total_customers.toLocaleString()} +4`}
          sub={`계약 ${k.total_contracts.toLocaleString()}건`}
        />
        <Kpi
          label="정상 계약 고객"
          value={k.active_customers.toLocaleString()}
          sub="계약확정 1건 이상"
        />
        <Kpi
          label="누적 해약 비율"
          value={k.cancel_rate_contract.toFixed(2) + "%"}
          sub={`계약 기준 ${k.cancelled_contracts}건 · 고객 기준 ${k.cancel_rate_customer.toFixed(2)}%`}
        />
        <Kpi
          label="오늘의 해약률"
          value={o.today.rate.toFixed(3) + "%"}
          sub={`${o.today.cancelled}명 · ${o.as_of}`}
        />
        <Kpi
          label="이달의 해약률"
          value={o.month.rate.toFixed(2) + "%"}
          sub={`${o.month.cancelled}명 · 월초 고객 대비`}
        />
        <Kpi
          label="연간 누적 해약률"
          value={o.year.rate.toFixed(2) + "%"}
          sub={`${o.year.cancelled.toLocaleString()}명 · 연초 고객 대비`}
        />
        <Kpi
          tone="red"
          label="고위험 고객"
          value={d.grades.고위험.toLocaleString() + "명"}
          sub={`중위험 ${d.grades.중위험.toLocaleString()} · 저위험 ${d.grades.저위험.toLocaleString()}`}
        />
      </div>
      <div className="grid lg:grid-cols-2 gap-4">
        <Card dark className="p-5">
          <h2 className="font-bold">월별 해약률 추이</h2>
          <p className="text-xs text-slate-400 mt-1 mb-4">
            월초 정상 고객 대비 · 당월은 현재까지 집계
          </p>
          <div className="h-56">
            <ResponsiveContainer>
              <LineChart data={o.monthly}>
                <CartesianGrid stroke="#52637A" strokeDasharray="3 3" />
                <XAxis
                  dataKey="month"
                  tick={{ fill: "#CBD5E1", fontSize: 11 }}
                />
                <YAxis tick={{ fill: "#CBD5E1", fontSize: 11 }} unit="%" />
                <Tooltip
                  {...tip}
                  formatter={(v) => Number(v).toFixed(2) + "%"}
                />
                <Line
                  dataKey="rate"
                  name="해약률"
                  stroke="#60A5FA"
                  strokeWidth={3}
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card dark className="p-5">
          <h2 className="font-bold">최근 14일 해약 추이</h2>
          <p className="text-xs text-slate-400 mt-1 mb-4">일별 해약 고객 수</p>
          <div className="h-56">
            <ResponsiveContainer>
              <BarChart data={o.daily.slice(-14)}>
                <CartesianGrid stroke="#52637A" strokeDasharray="3 3" />
                <XAxis
                  dataKey="date"
                  tickFormatter={(v) => v.slice(5)}
                  tick={{ fill: "#CBD5E1", fontSize: 10 }}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fill: "#CBD5E1", fontSize: 11 }}
                />
                <Tooltip {...tip} />
                <Bar
                  dataKey="cancelled"
                  name="해약 고객"
                  fill="#60A5FA"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
      <div className="grid lg:grid-cols-[2fr_1fr] gap-4">
        <Card dark className="p-5">
          <div className="font-bold mb-3">계약일 기준 주간 신규 계약</div>
          <div className="h-60">
            <ResponsiveContainer>
              <LineChart data={d.trend}>
                <CartesianGrid stroke="#52637A" />
                <XAxis
                  dataKey="week"
                  tick={{ fill: "#CBD5E1", fontSize: 10 }}
                />
                <YAxis tick={{ fill: "#CBD5E1", fontSize: 10 }} />
                <Tooltip {...tip} />
                <Line
                  dataKey="contracts"
                  name="신규 계약"
                  stroke="#60A5FA"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card dark className="p-5">
          <div className="font-bold">관리 목표 해약률</div>
          <div className="mt-2 text-4xl font-black text-white">
            {t.target_cancel_rate.toFixed(2)}
            <span className="text-base text-slate-400"> % 이하</span>
          </div>
          <div className="mt-3 h-2 rounded bg-white/10">
            <div
              className={cls(
                "h-2 rounded",
                t.current <= t.target_cancel_rate
                  ? "bg-emerald-400"
                  : "bg-dk-red",
              )}
              style={{ width: pct + "%" }}
            />
          </div>
          <p className="mt-2 text-xs text-slate-400">
            현재 {t.current.toFixed(2)}% ({t.basis})
          </p>
          <div className="mt-3 flex gap-2">
            <input
              type="number"
              step="0.01"
              placeholder="목표(%)"
              className={inputCls(D)}
              value={tr}
              onChange={(e) => setTr(e.target.value)}
            />
            <Btn dark onClick={saveT}>
              설정
            </Btn>
          </div>
          {msg && <p className="text-xs mt-1 text-slate-400">{msg}</p>}
        </Card>
      </div>
      <div className="grid lg:grid-cols-3 gap-4">
        <Card dark className="p-5">
          <div className="font-bold mb-3">제품군별 정상 계약</div>
          <div className="h-52">
            <ResponsiveContainer>
              <BarChart data={d.by_product} layout="vertical">
                <XAxis type="number" tick={{ fill: "#CBD5E1", fontSize: 10 }} />
                <YAxis
                  dataKey="code"
                  type="category"
                  width={70}
                  tick={{ fill: "#CBD5E1", fontSize: 10 }}
                />
                <Tooltip {...tip} />
                <Bar
                  dataKey="contracts"
                  name="계약"
                  fill="#60A5FA"
                  radius={3}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card dark className="p-5">
          <div className="font-bold mb-3">판매유형별 계약 · 해약</div>
          <div className="h-52">
            <ResponsiveContainer>
              <BarChart data={d.by_sales}>
                <XAxis
                  dataKey="name"
                  tick={{ fill: "#CBD5E1", fontSize: 11 }}
                />
                <YAxis tick={{ fill: "#CBD5E1", fontSize: 10 }} />
                <Tooltip {...tip} />
                <Bar
                  dataKey="contracts"
                  name="계약"
                  fill="#60A5FA"
                  radius={3}
                />
                <Bar
                  dataKey="cancelled"
                  name="해약"
                  fill="#f26d5b"
                  radius={3}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card dark className="p-5">
          <div className="font-bold mb-3">위험등급 분포</div>
          <div className="h-52">
            <ResponsiveContainer>
              <BarChart
                data={Object.entries(d.grades).map(([name, v]) => ({
                  name,
                  v,
                }))}
              >
                <XAxis
                  dataKey="name"
                  tick={{ fill: "#CBD5E1", fontSize: 11 }}
                />
                <YAxis tick={{ fill: "#CBD5E1", fontSize: 10 }} />
                <Tooltip {...tip} />
                <Bar dataKey="v" name="고객 수" radius={3}>
                  {Object.keys(d.grades).map((g) => (
                    <Cell key={g} fill={GC[g]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
      <Card dark className="p-5">
        <div className="font-bold mb-3">해약 위험 상위 관리 대상</div>
        <div className="grid sm:grid-cols-3 gap-3">
          {d.top.map((x) => (
            <button
              key={x.pct}
              onClick={() => go(`#/a/risk?top=${x.pct}`)}
              className="rounded-xl border border-dk-line p-4 text-left hover:border-dk-blue"
            >
              <div className="text-xs text-slate-400">상위 {x.pct}%</div>
              <div className="text-2xl font-extrabold text-white">
                {x.count.toLocaleString()}명
              </div>
              <div className="text-[11px] text-slate-500">
                위험점수 {x.min_score.toFixed(1)} 이상 · 목록 보기 →
              </div>
            </button>
          ))}
        </div>
        <p className="mt-3 text-xs text-slate-500">
          {d.model.score_meaning}. 연결 모델 검증 성능(Test): AP{" "}
          {d.model.notebook_metrics.test_AP}, ROC-AUC{" "}
          {d.model.notebook_metrics.test_ROC_AUC}, Recall{" "}
          {d.model.notebook_metrics.test_recall} — 모델:{" "}
          {d.model.notebook_metrics.model}
        </p>
      </Card>
    </div>
  );
}

function RiskList({ params, go }) {
  const openDetail = (id) => {
    go("#/a/customer?id=" + encodeURIComponent(id));
  };

  const f0 = useAsync(() => api("/admin/dashboard"), []);
  const [f, setF] = useState({
      grade: "",
      sales: "",
      ctype: "",
      product: "",
      q: "",
      top: params.top || "",
    }),
    [page, setPage] = useState(1);
  const qs = new URLSearchParams(
    Object.fromEntries(
      Object.entries({ ...f, page, size: 15 }).filter(([, v]) => v !== ""),
    ),
  ).toString();
  const r = useAsync(() => api("/admin/risk-customers?" + qs), [qs]);
  const set = (k) => (e) => {
    setF({ ...f, [k]: e.target.value });
    setPage(1);
  };
  const Sel = ({ k, label, opts }) => (
    <select className={inputCls(D) + " !w-auto"} value={f[k]} onChange={set(k)}>
      <option value="">{label}</option>
      {opts?.map((o) => (
        <option key={o}>{o}</option>
      ))}
    </select>
  );
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-extrabold text-white">이탈 위험 고객</h1>
        <p className="text-sm text-slate-400">
          AI 위험점수 기준 관리 우선순위{" "}
          {r.data && <SourceBadge source={r.data.source} />}
        </p>
      </div>
      <Card dark className="p-4 flex flex-wrap gap-2 items-center">
        <input
          className={inputCls(D) + " !w-48"}
          placeholder="고객ID 검색"
          value={f.q}
          onChange={set("q")}
          onKeyDown={(e) => {
            if (e.key === "Enter" && f.q.trim()) {
              openDetail(f.q.trim());
            }
          }}
        />
        <Btn dark disabled={!f.q.trim()} onClick={() => openDetail(f.q.trim())}>
          고객 상세 조회
        </Btn>

        <Sel
          k="grade"
          label="등급 전체"
          opts={["고위험", "중위험", "저위험"]}
        />
        <Sel k="sales" label="판매유형" opts={f0.data?.filters.sales} />
        <Sel k="ctype" label="계약유형" opts={f0.data?.filters.ctype} />
        <Sel k="product" label="제품군" opts={f0.data?.filters.product} />
        <select
          className={inputCls(D) + " !w-auto"}
          value={f.top}
          onChange={set("top")}
        >
          <option value="">상위 % 전체</option>
          {[5, 10, 20].map((x) => (
            <option key={x} value={x}>
              상위 {x}%
            </option>
          ))}
        </select>
      </Card>
      <div className="grid gap-4">
        <Card dark className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs text-slate-500 text-left">
              <tr>
                {[
                  "순위",
                  "고객ID",
                  "점수",
                  "등급",
                  "대표 계약",
                  "주요 위험 관련 특성",
                ].map((h) => (
                  <th key={h} className="p-3">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {r.data?.items.map((x) => (
                <tr
                  key={x.customer_id}
                  onClick={() => openDetail(x.customer_id)}
                  className={cls(
                    "cursor-pointer border-t border-dk-line hover:bg-white/5",
                  )}
                >
                  <td className="p-3">{x.rank}</td>
                  <td className="p-3 font-semibold text-white">
                    {x.customer_id}
                  </td>
                  <td className="p-3">{x.score.toFixed(1)}</td>
                  <td className="p-3">
                    <GradeChip g={x.grade} />
                  </td>
                  <td className="p-3 text-xs text-slate-400">
                    {x.sales_type}/{x.contract_type}
                    <br />
                    {x.product} · {won(x.monthly_fee)}
                  </td>
                  <td className="p-3 text-xs text-slate-400 max-w-[220px]">
                    {x.top_reason}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {r.loading && <Spin dark />}
          <Err dark msg={r.error} />
          <div className="flex items-center justify-between p-3 text-xs text-slate-400">
            <span>총 {r.data?.total.toLocaleString()}명</span>
            <span className="flex gap-2 items-center">
              <Btn
                dark
                kind="outline"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                className="!py-1"
              >
                이전
              </Btn>
              {page}
              <Btn
                dark
                kind="outline"
                disabled={r.data && page * 15 >= r.data.total}
                onClick={() => setPage(page + 1)}
                className="!py-1"
              >
                다음
              </Btn>
            </span>
          </div>
        </Card>
      </div>
    </div>
  );
}

function Lookup() {
  const options = useAsync(() => api("/admin/predict-options"), []);
  const [form, setForm] = useState({
    contract_type: "",
    channel: "",
    term: "",
    customer_type: "",
    age_band: "",
    gender: "",
  });
  const [result, setResult] = useState(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const labels = {
    contract_type: "계약유형",
    channel: "유통경로",
    term: "계약기간",
    customer_type: "고객유형",
    age_band: "연령대",
    gender: "성별",
  };
  const analyze = async (example = false) => {
    setError("");
    setResult(null);
    if (Object.values(form).some((v) => v === "")) {
      setError("6가지 고객 조건을 모두 선택해 주세요.");
      return;
    }
    setBusy(true);
    try {
      setResult(
        await api(
          example ? "/admin/predict-example" : "/admin/predict-manual",
          { method: "POST", body: { ...form, term: Number(form.term) } },
        ),
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  const color =
    result?.grade === "높음"
      ? "#f26d5b"
      : result?.grade === "보통"
        ? "#f5b94a"
        : "#34d399";
  return (
    <div className="space-y-5 max-w-6xl">
      <div>
        <div className="text-xs tracking-widest text-dk-blue font-bold mb-2">
          AI CUSTOMER INTELLIGENCE
        </div>
        <h1 className="text-2xl font-extrabold text-white">
          AI 해약 위험도 예측
        </h1>
        <p className="text-sm text-slate-400 mt-2">
          계약 조건과 고객 특성을 입력하고, 상대 위험 수준과 관리 전략을
          확인하세요.
        </p>
      </div>
      <Card dark className="p-6">
        <h2 className="font-bold mb-4">고객 조건 입력</h2>
        {options.loading ? (
          <Spin dark />
        ) : options.error ? (
          <Err dark msg={options.error} />
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              analyze();
            }}
          >
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-x-5 gap-y-2">
              {Object.entries(labels).map(([key, label]) => (
                <Field dark key={key} label={label}>
                  <select
                    required
                    disabled={busy}
                    aria-label={label}
                    className={inputCls(true)}
                    value={form[key]}
                    onChange={(e) => {
                      setForm({ ...form, [key]: e.target.value });
                      setResult(null);
                    }}
                  >
                    <option value="">선택해 주세요</option>
                    {options.data.options[key].map((v) => (
                      <option key={v.value ?? v} value={v.value ?? v}>
                        {v.label ?? v}
                        {key === "term" ? "개월" : ""}
                      </option>
                    ))}
                  </select>
                </Field>
              ))}
            </div>
            <p className="text-xs text-slate-400 mb-5">
              연령대는 계약 당시 기준입니다. 사업자의 연령은 모델 전처리에 따라
              반영되지 않습니다.
            </p>
            <div className="flex flex-wrap gap-3 items-center">
              <Btn
                dark
                type="submit"
                disabled={busy || !options.data.model_connected}
              >
                {busy ? "분석 중…" : "AI 해약 위험도 분석"}
              </Btn>
              {!options.data.model_connected && (
                <>
                  <span className="text-xs text-dk-amber">AI 모델 연결 전</span>
                  <Btn
                    dark
                    kind="outline"
                    disabled={busy}
                    onClick={() => analyze(true)}
                  >
                    화면 예시 보기 · AI 예측 아님
                  </Btn>
                </>
              )}
            </div>
          </form>
        )}
        <Err dark msg={error} />
      </Card>
      {result && (
        <section aria-live="polite" className="space-y-4">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-bold text-white">
              AI 해약 위험도 분석 결과
            </h2>
            <span className="text-xs text-slate-300">
              {result.source === "joblib_model"
                ? "모델 분석 완료"
                : "화면 확인용 예시 · AI 예측 아님"}
            </span>
          </div>
          <div className="grid lg:grid-cols-[.8fr_1.2fr] gap-4">
            <Card dark className="p-6 text-center">
              <div className="text-sm text-slate-300">해약 위험점수</div>
              <svg
                viewBox="0 0 240 145"
                className="w-full max-w-xs mx-auto"
                role="img"
                aria-label={`해약 위험점수 ${result.score.toFixed(1)}점, ${result.grade}`}
              >
                <path
                  d="M 25 120 A 95 95 0 0 1 215 120"
                  fill="none"
                  stroke="#52637A"
                  strokeWidth="16"
                  strokeLinecap="round"
                />
                <path
                  d="M 25 120 A 95 95 0 0 1 215 120"
                  fill="none"
                  stroke={color}
                  strokeWidth="16"
                  strokeLinecap="round"
                  pathLength="100"
                  strokeDasharray={`${result.score} 100`}
                />
                <text
                  x="120"
                  y="104"
                  textAnchor="middle"
                  fill="#F8FAFC"
                  fontSize="38"
                  fontWeight="800"
                >
                  {result.score.toFixed(1)}
                </text>
                <text
                  x="120"
                  y="128"
                  textAnchor="middle"
                  fill="#CBD5E1"
                  fontSize="12"
                >
                  / 100점
                </text>
              </svg>
              <span
                className="inline-block rounded-full px-4 py-1 text-sm font-bold"
                style={{ color, background: color + "20" }}
              >
                위험등급 · {result.grade}
              </span>
              <p className="text-xs text-slate-300 mt-4">
                상대 위험점수이며 미래 해약 확률이 아닙니다.
              </p>
            </Card>
            <Card dark className="p-6">
              <h3 className="font-bold mb-4">입력한 고객 조건</h3>
              <dl className="grid grid-cols-2 gap-4">
                {Object.entries(result.conditions).map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-xs text-slate-400">{labels[k]}</dt>
                    <dd className="text-sm font-semibold mt-1">
                      {k === "gender"
                        ? { 남자: "남성", 여자: "여성" }[v] || v
                        : v}
                      {k === "term" ? "개월" : ""}
                    </dd>
                  </div>
                ))}
              </dl>
              <p className="text-sm text-slate-300 mt-5 border-t border-dk-line pt-4">
                {result.explanation}
              </p>
            </Card>
          </div>
          <div className="grid lg:grid-cols-2 gap-4">
            <Card dark className="p-6">
              <h3 className="font-bold mb-4">위험도에 영향을 준 주요 변수</h3>
              {result.factors.map((f) => (
                <div key={f.feature} className="mb-4">
                  <div className="flex justify-between text-sm">
                    <span>{f.feature}</span>
                    <span
                      style={{
                        color: f.contribution > 0 ? "#f26d5b" : "#34d399",
                      }}
                    >
                      {f.direction}
                    </span>
                  </div>
                  <div className="h-2 bg-white/10 rounded mt-2">
                    <div
                      className="h-2 rounded"
                      style={{
                        width:
                          Math.max(
                            2,
                            (Math.abs(f.contribution) /
                              Math.max(
                                ...result.factors.map((x) =>
                                  Math.abs(x.contribution),
                                ),
                              )) *
                              100,
                          ) + "%",
                        background: f.contribution > 0 ? "#f26d5b" : "#34d399",
                      }}
                    />
                  </div>
                </div>
              ))}
              {!result.factors.length && (
                <p className="text-sm text-slate-300">
                  예시 화면에서는 모델 기여도를 제공하지 않습니다.
                </p>
              )}
              <p className="text-xs text-slate-400">
                기여도의 상대 크기이며 해약 원인이나 확률 변화량이 아닙니다.
              </p>
            </Card>
            <Card dark className="p-6">
              <h3 className="font-bold mb-4">
                추천 고객 유지 및 해약 방지 전략
              </h3>
              <ol className="space-y-4">
                {result.actions.map((a, i) => (
                  <li key={a} className="flex gap-3 text-sm">
                    <span className="shrink-0 rounded-full bg-dk-blue/20 text-dk-blue w-6 h-6 text-center leading-6 font-bold">
                      {i + 1}
                    </span>
                    <span>{a}</span>
                  </li>
                ))}
              </ol>
              <p className="text-xs text-slate-400 mt-5">
                상담 결과와 고객 동의를 확인한 후 적용해 주세요.
              </p>
            </Card>
          </div>
          <Card dark className="p-5">
            <details>
              <summary className="cursor-pointer text-sm font-semibold">
                분석에 적용한 기본값 및 점수 기준
              </summary>
              <p className="text-xs text-slate-300 my-3">
                {result.score_meaning}
              </p>
              <div className="overflow-auto">
                <table className="w-full text-xs text-left">
                  <thead>
                    <tr>
                      <th className="p-2">변수</th>
                      <th className="p-2">적용값</th>
                      <th className="p-2">선정 기준</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.defaults.map((x) => (
                      <tr key={x.feature} className="border-t border-dk-line">
                        <td className="p-2">{x.feature}</td>
                        <td className="p-2">{x.value ?? "미반영"}</td>
                        <td className="p-2">{x.basis}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          </Card>
        </section>
      )}
    </div>
  );
}

function CustomerDetailPage({ id, go }) {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-white">고객 상세 정보</h1>

          <p className="mt-1 text-sm text-slate-400">고객ID: {id || "-"}</p>
        </div>

        <Btn dark kind="outline" onClick={() => go("#/a/risk")}>
          ← 이탈 위험 고객 목록
        </Btn>
      </div>

      {id ? (
        <CustomerDetail key={id} id={id} wide />
      ) : (
        <Card dark className="p-5">
          고객ID가 없습니다. 목록에서 고객을 선택해 주세요.
        </Card>
      )}
    </div>
  );
}

function CustomerDetail({ id, wide }) {
  const {
    data: d,
    error,
    loading,
  } = useAsync(() => api("/admin/customer/" + encodeURIComponent(id)), [id]);
  if (loading) return <Spin dark />;
  if (error)
    return (
      <Card dark className="p-5">
        <Err dark msg={error} />
      </Card>
    );
  if (!d.active)
    return (
      <div className="space-y-4">
        <Card dark className="p-5 text-sm">
          {d.message}
        </Card>
        <RecommendationPanel key={id} d={d} />
        <ReportPanel key={"report-" + id} id={id} />
      </div>
    );
  const r = d.risk,
    col = GC[r.grade];
  return (
    <div
      className={cls(
        "space-y-4",
        wide && "grid lg:grid-cols-2 gap-4 space-y-0",
      )}
    >
      {d.business && (
        <div className="lg:col-span-2">
          <BusinessPanel d={d} />
        </div>
      )}
      <div className="space-y-4">
        <Card dark className="p-5">
          <div className="flex justify-between">
            <div>
              <div className="text-lg font-extrabold text-white">
                고객 {d.customer_id}
              </div>
              <div className="text-xs text-slate-400">
                {d.profile.type} · {d.profile.region} ·{" "}
                {d.customer_type === "사업자"
                  ? d.business?.industry || "사업장 정보 확인 필요"
                  : `${d.profile.gender || "-"} · ${d.profile.age ? d.profile.age + "세" : "나이 미상"}`}
              </div>
            </div>
            <SourceBadge source={r.source} />
          </div>
          <div className="mt-4 flex items-end gap-3">
            <div className="text-5xl font-black" style={{ color: col }}>
              {r.score.toFixed(1)}
            </div>
            <GradeChip g={r.grade} />
            <span className="text-xs text-slate-400 pb-1">
              관리 우선순위: {d.priority}
              {r.population_rank
                ? ` · 정상 고객 기준 ${r.population_rank.toLocaleString()}위`
                : ""}
            </span>
          </div>
          <div className="mt-2 h-2 rounded bg-white/10">
            <div
              className="h-2 rounded"
              style={{ width: r.score + "%", background: col }}
            />
          </div>
          <p className="mt-2 text-[11px] text-slate-500">{r.score_meaning}</p>
        </Card>
        <Card dark className="p-5">
          <div className="font-bold mb-2">주요 위험 관련 특성</div>
          <ul className="space-y-1 text-sm text-slate-300">
            {r.reasons.map((x) => (
              <li key={x}>• {x}</li>
            ))}
            {!r.reasons.length && (
              <li className="text-slate-500">표시할 특성 없음</li>
            )}
          </ul>
          <p className="mt-2 text-[11px] text-slate-500">
            모델 예측 기여요인(통계적 연관)이며 해약의 실제 원인이 아닙니다.
          </p>
        </Card>
        <Card dark className="p-5">
          <div className="font-bold mb-2">
            추천 상담·유지 방안{" "}
            <span className="text-[11px] font-normal text-slate-500">
              가설 · 효과 미검증
            </span>
          </div>
          <ol className="list-decimal pl-5 space-y-1 text-sm text-slate-300">
            {d.actions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ol>
        </Card>
      </div>
      <div className="space-y-4">
        <Card dark className="p-5">
          <div className="font-bold mb-2">
            정상 계약 {d.contracts.length}건 · 월 {won(d.total_monthly)}
          </div>
          {d.contracts.map((c, i) => (
            <div
              key={i}
              className="border-t border-dk-line py-2 text-sm first:border-0"
            >
              <b className="text-white">{c.product_name}</b>{" "}
              <span className="text-xs text-slate-500">{c.product_code}</span>
              <div className="text-xs text-slate-400">
                {c.sales_type}/{c.contract_type} · {c.channel} ·{" "}
                {won(c.monthly_fee)} · {c.term_months}개월 · {c.start_date}
              </div>
            </div>
          ))}
          <div className="mt-2 text-xs text-slate-500">
            담당 코디: {d.coordi.name} · {d.coordi.center} · AS {d.as_count}건
          </div>
        </Card>
      </div>
      <RecommendationPanel key={d.customer_id} d={d} showBusiness={false} />
      <div className="lg:col-span-2">
        <ReportPanel key={"report-" + d.customer_id} id={d.customer_id} />
      </div>
    </div>
  );
}

function ReportPanel({ id }) {
  const [note, setNote] = useState(""),
    [rep, setRep] = useState(null),
    [err, setErr] = useState(""),
    [ok, setOk] = useState("");
  const [history, setHistory] = useState([]);
  const loadHistory = async () => {
    try {
      setHistory(
        await api(`/admin/customer/${encodeURIComponent(id)}/reports`),
      );
    } catch (e) {
      setErr(e.message);
    }
  };
  const gen = async () => {
    setErr("");
    try {
      setRep(
        await api("/admin/report", {
          method: "POST",
          body: { customer_id: id, note },
        }),
      );
    } catch (e) {
      setErr(e.message);
    }
  };
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(rep.text);
      setOk("복사되었습니다.");
    } catch {
      setOk("복사 실패: 미리보기에서 직접 선택해 복사하세요.");
    }
  };
  const handoff = async () => {
    try {
      const r = await api(`/admin/report/${rep.id}/handoff`, {
        method: "POST",
      });
      setOk(r.message);
    } catch (e) {
      setErr(e.message);
    }
  };
  const down = () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(
      new Blob([rep.text], { type: "text/plain;charset=utf-8" }),
    );
    a.download = `wow_report_${id}.txt`;
    a.click();
    URL.revokeObjectURL(a.href);
  };
  return (
    <Card dark className="p-5">
      <div className="font-bold mb-2">담당 코디 전달 보고서</div>
      <Field dark label="관리자 메모(선택)">
        <textarea
          rows={2}
          className={inputCls(D)}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </Field>
      <Btn dark onClick={gen}>
        보고서 생성 · 미리보기
      </Btn>
      <Btn dark kind="outline" onClick={loadHistory}>
        저장된 보고서 조회
      </Btn>
      {history.map((h) => (
        <button
          key={h.id}
          className="block text-sm text-blue-300 mt-2"
          onClick={async () => {
            try {
              setRep(await api("/admin/report/" + h.id));
            } catch (e) {
              setErr(e.message);
            }
          }}
        >
          보고서 #{h.id} · {h.created_at}
        </button>
      ))}
      <Err dark msg={err} />
      {rep && (
        <>
          <textarea
            readOnly
            rows={14}
            className={inputCls(D) + " mt-3 font-mono text-xs"}
            value={rep.text}
          />
          <div className="mt-2 flex flex-wrap gap-2">
            <Btn dark kind="outline" onClick={copy}>
              복사
            </Btn>
            <Btn dark kind="outline" onClick={down}>
              다운로드(.txt)
            </Btn>
            <Btn
              dark
              kind="outline"
              onClick={async () => {
                try {
                  await downloadPdf(rep.id);
                } catch (e) {
                  setErr(e.message);
                }
              }}
            >
              PDF 다운로드
            </Btn>
            <Btn dark kind="outline" onClick={handoff}>
              코디 전달 요청 저장
            </Btn>
          </div>
          {ok && <p className="text-xs text-slate-400 mt-1">{ok}</p>}
          <p className="text-[11px] text-slate-500 mt-1">
            내부 전달 요청을 저장합니다. 외부 문자·이메일 발송은 별도 연동이
            필요합니다.
          </p>
        </>
      )}
    </Card>
  );
}
