import { useState, useRef, useEffect } from 'react'
import { api } from './api'
import { Art, Card, Btn, Field, inputCls, won, dday, useAsync, DemoTag, Err, Spin, Logo, cls } from './ui'

/* ───── 공용: 상품 카드 / 상담 폼 / 챗봇 ───── */
export function ProductCard({ p, onConsult }) {
  return <Card className="overflow-hidden flex flex-col">
    <div className="relative h-64 bg-wow-soft p-2">{p.badge && <span className="absolute left-3 top-3 rounded bg-wow-accent px-2 py-0.5 text-[11px] font-bold text-white">{p.badge}</span>}
      <Art
        kind={p.kind}
        productCode={p.product_code}
      /></div>
    <div className="p-4 flex-1 flex flex-col"><div className="font-bold">{p.name}</div><div className="text-xs text-slate-500">{p.cat}</div>
      {p.reason && <p className="mt-2 text-sm text-slate-600 flex-1">{p.reason}</p>}
      <div className="mt-3 flex items-end justify-between"><div className="font-extrabold text-wow-green">월 {p.price.toLocaleString()}원</div>
        {onConsult && <button onClick={() => onConsult(p)} className="text-sm font-semibold text-wow-accent">상담 신청 ↗</button>}</div></div>
  </Card>
}

export function ConsultForm({ authed, presetInterest = '', onDone }) {
  const [f, setF] = useState({ name: '', phone: '', topic: '렌탈 계약 상담', interest: presetInterest, memo: '', consent: false })
  const [res, setRes] = useState(null), [err, setErr] = useState(''), [busy, setBusy] = useState(false)
  useEffect(() => setF(x => ({ ...x, interest: presetInterest })), [presetInterest])
  const set = k => e => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  const submit = async () => { setBusy(true); setErr(''); try { const r = await api('/public/consult', { method: 'POST', body: f }); setRes(r); onDone?.(r) } catch (e) { setErr(e.message) } setBusy(false) }
  if (res) return <div className="rounded-xl bg-wow-mint p-5 text-sm"><b className="text-wow-green">접수 완료</b><p className="mt-1">접수번호 <b>{res.receipt_no}</b></p><p className="text-slate-600">{res.message}</p></div>
  return <div>
    {!authed && <div className="grid sm:grid-cols-2 gap-x-3"><Field label="이름"><input className={inputCls()} value={f.name} onChange={set('name')} /></Field><Field label="연락처"><input className={inputCls()} placeholder="010-0000-0000" value={f.phone} onChange={set('phone')} /></Field></div>}
    <div className="grid sm:grid-cols-2 gap-x-3"><Field label="상담 주제"><select className={inputCls()} value={f.topic} onChange={set('topic')}>{['렌탈 계약 상담', '요금·약정 문의', '제품 추천', '프로모션 문의', '기타'].map(x => <option key={x}>{x}</option>)}</select></Field>
      <Field label="관심 제품"><select className={inputCls()} value={f.interest} onChange={set('interest')}><option value="">선택 안 함</option>{['정수기', '공기청정기', '비데', '연수기', '매트리스', '안마의자'].map(x => <option key={x}>{x}</option>)}</select></Field></div>
    <Field label="문의 내용"><textarea rows={3} className={inputCls()} value={f.memo} onChange={set('memo')} /></Field>
    <label className="flex items-start gap-2 text-xs text-slate-600 mb-3"><input type="checkbox" checked={f.consent} onChange={set('consent')} className="mt-0.5" />상담을 위한 개인정보 수집·이용에 동의합니다. (신청은 상담 요청이며 계약이 확정되지 않습니다)</label>
    <Err msg={err} /><Btn onClick={submit} disabled={busy}>{busy ? '접수 중…' : '상담 신청하기'}</Btn></div>
}

export function Chat({ authed, onAction, compact }) {
  const [msgs, setMsgs] = useState([{ role: 'bot', text: '안녕하세요, WOW AI예요. 렌탈 상품, 계약, 관리 방법, AS를 물어보세요.' }])
  const [v, setV] = useState(''), [busy, setBusy] = useState(false), end = useRef()
  useEffect(() => end.current?.scrollIntoView({ block: 'nearest' }), [msgs])
  const send = async text => {
    text = (text ?? v).trim(); if (!text || busy) return
    setV(''); setBusy(true); setMsgs(m => [...m, { role: 'user', text }])
    try { const r = await api('/chat', { method: 'POST', body: { message: text } }); setMsgs(m => [...m, { role: 'bot', text: r.reply, action: r.action, src: r.source }]) }
    catch (e) { setMsgs(m => [...m, { role: 'bot', text: e.message }]) }
    setBusy(false)
  }
  return <div className="flex flex-col">
    <div className={cls('overflow-y-auto space-y-3 p-4', compact ? 'h-72' : 'h-[26rem]')}>
      {msgs.map((m, i) => <div key={i} className={m.role === 'user' ? 'text-right' : ''}>
        <div className={cls('inline-block max-w-[85%] rounded-2xl px-4 py-2.5 text-sm text-left', m.role === 'user' ? 'bg-wow-accent text-white' : 'bg-slate-100 text-slate-800')}>{m.text}</div>
        {m.action && <div className="mt-2"><Btn kind="outline" onClick={() => onAction(m.action.type)} className="!py-1.5">{m.action.label} →</Btn></div>}
        {m.src && <div className="text-[10px] text-slate-400 mt-1">{m.src === 'llm' ? 'LLM 응답' : '규칙 기반 응답(LLM 키 미설정)'}</div>}</div>)}<div ref={end} /></div>
    <div className="flex flex-wrap gap-2 px-4 pb-2">{['정수기 필터 교체 주기', '물이 새요', '월 렌탈료·약정 알려줘', '추천 상품 알려줘'].map(q => <button key={q} onClick={() => send(q)} className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600 hover:bg-slate-50">{q}</button>)}</div>
    <div className="flex gap-2 border-t p-3"><input className={inputCls()} placeholder="궁금한 내용을 입력하세요" value={v} onChange={e => setV(e.target.value)} onKeyDown={e => e.key === 'Enter' && send()} /><Btn onClick={() => send()} disabled={busy}>전송</Btn></div></div>
}

const Modal = ({ title, onClose, children }) => <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" onClick={onClose}>
  <div className="w-full max-w-lg rounded-2xl bg-white p-6 max-h-[90vh] overflow-auto" onClick={e => e.stopPropagation()}><div className="flex justify-between mb-4"><h3 className="font-bold text-lg">{title}</h3><button onClick={onClose} className="text-slate-400 text-xl">×</button></div>{children}</div></div>

/* ───── 고객: 맞춤 홈 / 나의 렌탈 / AI 상담 ───── */
export function CustomerApp({ tab, go, session, autoAS }) {
  const me = useAsync(() => api('/me'), [])
  const [modal, setModal] = useState(autoAS ? 'as' : null)
  const act = t => t === 'as' ? setModal('as') : setModal('consult')
  const d = me.data
  return <div className="min-h-screen bg-wow-soft text-slate-800">
    <header className="sticky top-0 z-40 border-b bg-white/90 backdrop-blur"><div className="mx-auto flex max-w-6xl items-center justify-between px-4 h-16">
      <Logo /><nav className="flex gap-1 sm:gap-6 text-sm font-semibold">{[['home', '맞춤 홈'], ['rental', '나의 렌탈'], ['chat', 'AI 상담']].map(([k, l]) => <button key={k} onClick={() => go('#/c/' + k)} className={cls('px-2 py-5 border-b-2', tab === k ? 'border-wow-accent text-wow-accent' : 'border-transparent text-slate-500')}>{l}</button>)}</nav>
      <div className="text-xs text-slate-500">고객 {session.id} <button className="ml-2 underline" onClick={() => go('#/', true)}>로그아웃</button></div></div></header>
    <main className="mx-auto max-w-6xl px-4 py-8">
      {me.loading ? <Spin /> : me.error ? <Err msg={me.error} /> : <>
        {tab === 'home' && <Home d={d} go={go} setModal={setModal} />}
        {tab === 'rental' && <Rental d={d} reload={me.reload} setModal={setModal} />}
        {tab === 'chat' && <div className="grid lg:grid-cols-[1fr_280px] gap-5"><Card><div className="border-b p-4 font-bold">WOW AI <span className="text-xs font-normal text-slate-400">무엇이든 물어보세요</span></div><Chat authed onAction={act} /></Card>
          <Card className="p-4 h-fit text-sm"><div className="font-bold mb-2">상담 중인 제품</div>{d.contracts.map((c, i) => <div key={i} className="flex items-center gap-3 mb-2"><div className="h-12 w-12 rounded-lg bg-wow-soft p-1">
            <Art
              kind={c.kind}
              productCode={c.product_code}
            /></div><div><div className="font-semibold">{c.product_name}</div><div className="text-xs text-slate-500">{c.product_code}</div></div></div>)}
            <p className="mt-3 text-xs text-slate-400">챗봇은 계약 변경·신청을 확정하지 않습니다.</p></Card></div>}
        {modal === 'as' && <ASModal d={d} onClose={() => setModal(null)} onSaved={me.reload} />}
        {modal === 'consult' && <Modal title="상담 신청" onClose={() => setModal(null)}><ConsultForm authed /></Modal>}</>}
    </main></div>
}

function Home({ d, go, setModal }) {
  const nv = d.next_visit
  return <div className="space-y-8">
    <div><h1 className="text-2xl font-extrabold">오늘도 좋은 일상이에요.</h1><p className="text-sm text-slate-500">고객님께 맞는 추천과 케어 일정을 한눈에 확인하세요.</p></div>
    <div className="grid md:grid-cols-[2fr_1fr] gap-5">
      <div className="rounded-2xl bg-wow-mint p-6">{d.promotions.slice(0, 1).map(p => <div key={p.id}><span className="rounded bg-white px-2 py-0.5 text-[11px] font-bold text-wow-green">고객님 전용 혜택</span>
        <h2 className="mt-3 text-xl font-extrabold text-wow-green">{p.title}</h2><p className="mt-1 text-sm text-slate-600">{p.desc}</p><Btn className="mt-4" onClick={() => setModal('consult')}>혜택 상담하기</Btn></div>)}</div>
      <Card className="p-5"><div className="text-xs text-slate-500">다음 케어 방문 </div><div className="mt-1 text-3xl font-black text-wow-green">{dday(nv.date)}</div><div className="font-bold">{nv.date} {nv.slot}</div><div className="text-xs text-slate-500">{nv.product} · 담당 {d.coordi.name} 코디</div></Card></div>
    <section><div className="flex items-end justify-between mb-3"><h2 className="font-bold text-lg">내 일상에 어울리는 추천</h2><span className="text-xs text-slate-400">나이·성별·이용 제품군 기반 · 이용 중인 제품군 제외</span></div>
      <div className="grid sm:grid-cols-3 gap-4">{d.recommendations.map(p => <ProductCard key={p.id} p={p} onConsult={() => setModal('consult')} />)}</div></section>
    <div className="grid sm:grid-cols-[1fr_1fr] gap-5"><Card className="p-5"><div className="text-xs text-slate-500">나의 렌탈 한눈에</div><div className="mt-2 flex gap-10"><div><div className="text-xs text-slate-400">이용 중 상품</div><b className="text-2xl">{d.contracts.length}개</b></div><div><div className="text-xs text-slate-400">월 렌탈료 합계</div><b className="text-2xl">{won(d.total_monthly)}</b></div></div><button className="mt-3 text-sm font-semibold text-wow-accent" onClick={() => go('#/c/rental')}>나의 렌탈 자세히 →</button></Card>
      <div className="rounded-2xl bg-wow-green p-5 text-white"><div className="font-bold">궁금한 순간, WOW AI</div><p className="text-sm text-white/70 mt-1">사용법부터 AS 접수까지 바로 도와드려요.</p><button className="mt-4 text-sm font-semibold" onClick={() => go('#/c/chat')}>지금 상담하기 ↗</button></div></div></div>
}

function Rental({ d, reload, setModal }) {
  const [open, setOpen] = useState(null), [rate, setRate] = useState(5), [cm, setCm] = useState(''), [msg, setMsg] = useState('')
  const rev = async () => { try { await api('/me/review', { method: 'POST', body: { rating: rate, comment: cm } }); setMsg('평가가 저장되었습니다.'); setCm(''); reload() } catch (e) { setMsg(e.message) } }
  return <div className="space-y-6">
    <div className="flex items-end justify-between"><div><h1 className="text-2xl font-extrabold">나의 렌탈 현황</h1><p className="text-sm text-slate-500">계약·관리 일정을 확인하세요. 계약 정보는 실제 CSV 데이터입니다.</p></div><Btn onClick={() => setModal('as')}>AS 신청</Btn></div>
    <div className="grid grid-cols-3 rounded-2xl bg-wow-green p-5 text-white text-center"><div><div className="text-xs text-white/60">이용 중</div><b className="text-xl">{d.contracts.length}개</b></div><div><div className="text-xs text-white/60">월 렌탈료</div><b className="text-xl">{won(d.total_monthly)}</b></div><div><div className="text-xs text-white/60">다음 방문</div><b className="text-xl">{d.next_visit.date.slice(5).replace('-', '.')}</b></div></div>
    <div className="grid lg:grid-cols-[2fr_1fr] gap-5"><div className="space-y-4">
      {d.contracts.map((c, i) => <Card key={i} className="p-5"><div className="flex gap-5"><div className="h-32 w-28 rounded-xl bg-wow-soft p-2 shrink-0">
        <Art
          kind={c.kind}
          productCode={c.product_code}
        /></div>
        <div className="flex-1 text-sm"><div className="text-xs text-wow-accent font-bold">{c.sales_type} · {c.contract_type}</div><div className="text-lg font-extrabold">{c.product_name}</div><div className="text-xs text-slate-400 mb-2">모델 {c.product_code}</div>
          <dl className="grid grid-cols-2 gap-y-1"><dt className="text-slate-400">계약 기간</dt><dd>{c.start_date} ~ {c.end_date} ({c.term_months}개월)</dd><dt className="text-slate-400">월 렌탈료</dt><dd className="font-bold">{won(c.monthly_fee)}</dd><dt className="text-slate-400">납부</dt><dd>{c.pay_type}</dd>
            <dt className="text-slate-400">다음 방문</dt><dd>{c.next_visit} ({dday(c.next_visit)})</dd><dt className="text-slate-400">필터 교체 예정</dt><dd>{c.next_filter} ({dday(c.next_filter)})</dd></dl>
          <button className="mt-2 text-xs font-semibold text-wow-accent" onClick={() => setOpen(open === i ? null : i)}>{open === i ? '관리 방법 닫기' : '제품 관리 방법 보기'}</button>
          {open === i && <ul className="mt-2 list-disc pl-5 text-slate-600">{c.care_tips.map(t => <li key={t}>{t}</li>)}</ul>}</div></div></Card>)}
      <Card className="p-5"><h3 className="font-bold mb-2">AS · 상담 내역</h3>{[...d.as_requests.map(a => ({ k: a.id, t: `AS 신청 · ${a.symptom}`, s: a.status, dt: a.created_at.slice(0, 10) })), ...d.as_history_demo.map(a => ({ k: a.id, t: a.title, s: a.status, dt: a.date })), ...d.consults.map(c => ({ k: c.receipt_no, t: `상담 · ${c.topic}`, s: '접수', dt: c.created_at.slice(0, 10) }))].map(r => <div key={r.k} className="flex justify-between border-b py-2 text-sm last:border-0"><span>{r.t}</span><span className="text-slate-400">{r.dt} · {r.s}</span></div>)}
        {!d.as_requests.length && !d.as_history_demo.length && !d.consults.length && <p className="text-sm text-slate-400">내역이 없습니다.</p>}</Card></div>
      <div className="space-y-4"><Card className="p-5"><div className="text-xs text-slate-500">나의 전담 케어 전문가</div><div className="text-xl font-extrabold mt-1">{d.coordi.name} 코디</div><div className="text-xs text-slate-500">{d.coordi.center} · ★ {d.coordi.rating} ({d.coordi.review_count})</div>
        <div className="mt-4 border-t pt-3"><div className="text-xs font-semibold mb-1">서비스 평가</div><div className="flex gap-1 mb-2">{[1, 2, 3, 4, 5].map(n => <button key={n} onClick={() => setRate(n)} className={cls('text-2xl', n <= rate ? 'text-amber-400' : 'text-slate-300')}>★</button>)}</div>
          <textarea rows={2} className={inputCls()} placeholder="코멘트(선택)" value={cm} onChange={e => setCm(e.target.value)} /><Btn className="mt-2 w-full" kind="outline" onClick={rev}>평가 저장</Btn>{msg && <p className="text-xs text-wow-accent mt-1">{msg}</p>}</div></Card>
        <Card className="p-5"><div className="font-bold mb-2">맞춤 케어 알림</div>{d.contracts.slice(0, 3).map((c, i) => <p key={i} className="text-sm text-slate-600 mb-1">• {c.product_name}: {c.care_tips[0]}</p>)}</Card></div></div></div>
}

function ASModal({ d, onClose, onSaved }) {
  const [f, setF] = useState({ product_code: d.contracts[0].product_code, symptom: '출수/작동 이상', preferred_date: '', memo: '' }), [err, setErr] = useState(''), [ok, setOk] = useState('')
  const set = k => e => setF({ ...f, [k]: e.target.value })
  const save = async () => { try { const r = await api('/me/as', { method: 'POST', body: f }); setOk(r.message); onSaved() } catch (e) { setErr(e.message) } }
  return <Modal title="AS 신청" onClose={onClose}>{ok ? <><p className="text-wow-green font-bold">{ok}</p><Btn className="mt-4" onClick={onClose}>닫기</Btn></> : <>
    <Field label="제품"><select className={inputCls()} value={f.product_code} onChange={set('product_code')}>{[...new Map(d.contracts.map(c => [c.product_code, c])).values()].map(c => <option key={c.product_code} value={c.product_code}>{c.product_name} ({c.product_code})</option>)}</select></Field>
    <Field label="증상"><select className={inputCls()} value={f.symptom} onChange={set('symptom')}>{['출수/작동 이상', '누수', '소음', '냄새/수질', '필터 교체 문의', '기타'].map(x => <option key={x}>{x}</option>)}</select></Field>
    <Field label="희망 방문일"><input type="date" className={inputCls()} value={f.preferred_date} onChange={set('preferred_date')} /></Field>
    <Field label="추가 내용"><textarea rows={3} className={inputCls()} value={f.memo} onChange={set('memo')} /></Field><Err msg={err} /><Btn onClick={save}>신청 확정</Btn></>}</Modal>
}

/* ───── 신규 고객 ───── */
export function NewCustomer({ go }) {
  const prods = useAsync(() => api('/products'), []), promos = useAsync(() => api('/promotions?audience=new'), [])
  const [r, setR] = useState({ age: '', gender: '', interest: '' }), [rec, setRec] = useState(null), [interest, setInterest] = useState(''), [co, setCo] = useState(false)
  const sec = id => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
  const recommend = async () => setRec(await api('/public/recommend', { method: 'POST', body: { age: r.age ? +r.age : null, gender: r.gender || null, interest: r.interest || null } }))
  const toConsult = p => { setInterest(p.cat); sec('consult') }
  return <div className="min-h-screen bg-wow-soft text-slate-800">
    <header className="sticky top-0 z-40 border-b bg-white/90 backdrop-blur"><div className="mx-auto flex max-w-6xl items-center justify-between px-4 h-16"><Logo />
      <nav className="hidden sm:flex gap-6 text-sm font-semibold text-slate-600">{[['products', '인기 상품'], ['recommend', '맞춤 추천'], ['chat', 'AI 상담'], ['consult', '상담 신청']].map(([k, l]) => <button key={k} onClick={() => sec(k)}>{l}</button>)}</nav>
      <Btn kind="outline" onClick={() => go('#/')}>로그인 화면</Btn></div></header>
    <main className="mx-auto max-w-6xl px-4 py-8 space-y-10">
      <section className="grid md:grid-cols-2 gap-6 items-center rounded-3xl bg-wow-mint p-8"><div><div className="text-xs font-bold text-wow-accent">WELCOME TO WOW</div><h1 className="mt-2 text-3xl font-extrabold text-wow-green leading-snug">빌리는 건 제품,<br />누리는 건 더 나은 일상.</h1><p className="mt-3 text-sm text-slate-600">정수기·공기청정기·비데까지, 나에게 맞는 렌탈을 만나보세요.</p><Btn className="mt-5" onClick={() => sec('consult')}>상담 신청하기</Btn></div>
        <div className="relative mx-auto h-64 w-56 rounded-3xl bg-white p-4 shadow-sm"><Art kind="purifier" /></div></section>
      <section id="promos" className="grid sm:grid-cols-2 gap-4">{promos.data?.map(p => <Card key={p.id} className="p-5"><b className="text-wow-green">{p.title}</b><p className="text-sm text-slate-600 mt-1">{p.desc}</p></Card>)}</section>
      <section id="products"><h2 className="font-bold text-lg mb-3">인기 렌탈 상품</h2>{prods.loading ? <Spin /> : <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">{prods.data?.map(p => <ProductCard key={p.id} p={{ ...p, reason: p.cat }} onConsult={toConsult} />)}</div>}</section>
      <section id="recommend"><Card className="p-6"><h2 className="font-bold text-lg mb-1">나에게 맞는 상품 추천</h2><p className="text-xs text-slate-400 mb-4"></p>
        <div className="grid sm:grid-cols-4 gap-3 items-end"><Field label="나이"><input type="number" className={inputCls()} value={r.age} onChange={e => setR({ ...r, age: e.target.value })} /></Field><Field label="성별"><select className={inputCls()} value={r.gender} onChange={e => setR({ ...r, gender: e.target.value })}><option value="">선택 안 함</option><option>여자</option><option>남자</option></select></Field>
          <Field label="관심 제품"><select className={inputCls()} value={r.interest} onChange={e => setR({ ...r, interest: e.target.value })}><option value="">선택 안 함</option>{['정수기', '공기청정기', '비데', '연수기', '매트리스', '안마의자'].map(x => <option key={x}>{x}</option>)}</select></Field><div className="mb-3"><Btn onClick={recommend} className="w-full">추천 받기</Btn></div></div>
        {rec && <div className="grid sm:grid-cols-3 gap-4 mt-2">{rec.items.map(p => <ProductCard key={p.id} p={p} onConsult={toConsult} />)}</div>}</Card></section>
      <section id="chat"><Card><div className="border-b p-4 font-bold">WOW AI 상담</div><Chat authed={false} compact onAction={() => sec('consult')} /></Card></section>
      <section id="consult"><Card className="p-6 max-w-2xl"><h2 className="font-bold text-lg mb-4">렌탈 계약 상담 신청</h2><ConsultForm presetInterest={interest} onDone={() => setCo(true)} />{co && <p className="mt-3 text-xs text-slate-400">신청 내역은 서버 DB(consultations)에 저장되었습니다.</p>}</Card></section>
    </main></div>
}
