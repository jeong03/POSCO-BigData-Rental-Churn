import { useEffect, useState } from 'react'
import { api, setToken } from './api'
import { Art, Btn, Field, inputCls, Logo, useAsync, Err, cls } from './ui'
import { CustomerApp, NewCustomer } from './customer'
import { AdminApp } from './admin'

function useHash() {
  const [h, setH] = useState(location.hash || '#/')
  useEffect(() => { const f = () => setH(location.hash || '#/'); addEventListener('hashchange', f); return () => removeEventListener('hashchange', f) }, [])
  const [path, qs] = h.slice(1).split('?')
  return { path, params: Object.fromEntries(new URLSearchParams(qs || '')) }
}

export default function App() {
  const { path, params } = useHash()
  const [session, setSession] = useState(null) // 메모리에만 보관 (새로고침 시 재로그인)
  const go = (h, logout) => {
    if (logout) { api('/auth/logout', { method: 'POST' }).catch(() => {}); setToken(null); setSession(null) }
    location.hash = h
  }
  const login = s => { setToken(s.token); setSession(s); location.hash = s.role === 'admin' ? '#/a/dashboard' : '#/c/home' }
  const [, area, tab = ''] = path.split('/')
  if (area === 'n') return <NewCustomer go={go} />
  if (area === 'c' && session?.role === 'customer') return <CustomerApp tab={tab === 'rental-as' ? 'rental' : tab || 'home'} autoAS={tab === 'rental-as'} go={go} session={session} />
  if (area === 'a' && session?.role === 'admin') return <AdminApp tab={tab || 'dashboard'} params={params} go={go} session={session} />
  return <Landing onLogin={login} go={go} />
}

function Landing({ onLogin, go }) {
  const [role, setRole] = useState('customer'), [v, setV] = useState(''), [pw, setPw] = useState(''), [err, setErr] = useState(''), [busy, setBusy] = useState(false)
  const st = useAsync(() => api('/status'), []), samples = useAsync(() => api('/demo/sample-customers'), [])
  const dark = role === 'admin'
  const submit = async () => {
    setBusy(true); setErr('')
    try { onLogin(role === 'admin' ? await api('/auth/admin', { method: 'POST', body: { admin_id: v.trim(), password: pw } }) : await api('/auth/customer', { method: 'POST', body: { customer_id: v.trim() } })) }
    catch (e) { setErr(e.message) }
    setBusy(false)
  }
  return <div className={cls('min-h-screen', dark ? 'admin-theme bg-dk-bg text-slate-200' : 'bg-white text-slate-800')}>
    
    {/* 상단 헤더 */}
    <header className={cls('border-b h-16 flex items-center justify-between px-6', dark ? 'border-dk-line' : 'border-slate-200')}><Logo dark={dark} sub={dark ? 'BUSINESS CONSOLE' : 'COMPANY'} />
      <span className="hidden sm:block text-xs text-slate-400">일상에 더하는 놀라움, WOW · 고객센터 1588-9000</span>
      </header>
    
    <div className="mx-auto grid max-w-[1600px] gap-10 p-6 lg:grid-cols-[1.5fr_1fr] lg:p-10">
      
      {/* 왼쪽 카드 영역 */}
      <div className={cls(
        'flex min-h-[720px] flex-col overflow-hidden rounded-3xl',
        dark ? 'bg-[#222E40]' : 'bg-[#E4EBE2]'
      )}>
        {/* 상단 문구 영역 */}
        <div className="px-8 py-10 lg:px-10 lg:py-12">
          <p className={cls(
            'text-xs font-bold tracking-wide',
            dark ? 'text-blue-300' : 'text-[#008575]'
          )}>
            LIVE WELL, WITH WOW
          </p>

          <h1 className={cls(
            'mt-7 text-3xl font-extrabold leading-relaxed tracking-tight lg:text-4xl',
            dark ? 'text-white' : 'text-[#183036]'
          )}>
            빌리는 건 제품,
            <br />
            누리는 건 더 나은 일상.
          </h1>

          <p className={cls(
            'mt-5 text-sm leading-relaxed lg:text-base',
            dark ? 'text-slate-300' : 'text-[#526B65]'
          )}>
            나를 이해하는 렌탈, 끝까지 함께하는 케어
          </p>
        </div>

        {/* 하단 사진 영역 */}
        <div className="relative min-h-[380px] flex-1">
  <img
    src="/images/login-bg.png"
    alt="정수기와 공기청정기가 놓인 따뜻한 거실"
    className={cls(
      'absolute inset-0 h-full w-full object-cover',
      dark ? 'brightness-75' : ''
    )}
  />

          
        </div>
      </div>
      
      {/* 오른쪽 로그인 */}
      <div className="self-center max-w-md w-full">
        <div className={cls('text-[11px] font-bold tracking-wider', dark ? 'text-blue-300' : 'text-wow-accent')}>WELCOME TO WOW</div>
        <h2 className="mt-1 text-2xl font-extrabold">{dark ? '고객의 내일을 지키는 시작' : '나에게 맞는 일상의 시작'}</h2>
        <div className={cls('mt-5 grid grid-cols-2 rounded-lg p-1 text-sm font-semibold', dark ? 'bg-white/5' : 'bg-slate-100')}>{[['customer', '고객'], ['admin', '관리자']].map(([k, l]) => <button key={k} onClick={() => { setRole(k); setV(''); setErr('') }} className={cls('rounded-md py-2', role === k ? (dark ? 'bg-dk-blue/30 text-white' : 'bg-white shadow') : 'text-slate-400')}>{l}</button>)}</div>
        <div className="mt-5"><Field dark={dark} label={dark ? '관리자 ID' : '고객 ID'}><input className={inputCls(dark)} value={v} onChange={e => setV(e.target.value)} placeholder={dark ? 'WOW-A0001' : '예: 66758234'} onKeyDown={e => e.key === 'Enter' && submit()} /></Field>
          {dark && <Field dark label="비밀번호"><input type="password" className={inputCls(true)} value={pw} onChange={e => setPw(e.target.value)} onKeyDown={e => e.key === 'Enter' && submit()} /></Field>}
          <Err dark={dark} msg={err} /><Btn dark={dark} className="w-full" onClick={submit} disabled={busy}>{dark ? '관리자로 시작하기 →' : '고객으로 시작하기 →'}</Btn></div>
        <div className={cls('mt-6 border-t pt-4 text-xs', dark ? 'border-dk-line' : 'border-slate-200')}><div className="font-bold mb-2"></div>
          {dark ? <p className="text-slate-400">시연 계정: <b className="text-slate-200">WOW-A0001</b> / <b className="text-slate-200">wow1234!</b> · 운영 환경에서는 안전한 인증으로 교체하세요.</p>
            : <div className="flex flex-wrap gap-2">{samples.data?.map(s => <button key={s.customer_id} onClick={() => setV(s.customer_id)} className="rounded-full border border-slate-200 px-3 py-1 hover:bg-slate-50">{s.customer_id} <span className="text-slate-400">{s.label}</span></button>)}</div>}
          {!dark && <p className="mt-2 text-slate-400">실제 운영에서는 고객ID 외 추가 인증(본인확인)이 필요합니다.</p>}</div>
        <div className="mt-5 flex items-center justify-between text-sm"><button className="font-semibold underline" onClick={() => go('#/n/home')}>신규 고객이신가요? 상품 탐색·상담 신청 →</button></div>
        {st.data && <p className="mt-4 text-[11px] text-slate-400">AI 모델: {st.data.model.connected ? `연결됨 (${st.data.model.candidate})` : '연결 ... '} · 챗봇: {st.data.llm.enabled ? 'LLM' : '규칙 기반'}</p>}</div></div></div>
}
