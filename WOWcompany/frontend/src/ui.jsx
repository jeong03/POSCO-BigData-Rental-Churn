import { useEffect, useState, useCallback } from 'react'

export const won = n => (n == null ? '-' : Number(n).toLocaleString('ko-KR') + '원')
export const cls = (...a) => a.filter(Boolean).join(' ')
export const dday = iso => { const d = Math.ceil((new Date(iso) - new Date(new Date().toDateString())) / 864e5); return d === 0 ? 'D-Day' : d > 0 ? `D-${d}` : `D+${-d}` }

export function useAsync(fn, deps = []) {
  const [s, set] = useState({ data: null, error: null, loading: true })
  const load = useCallback(() => { set(x => ({ ...x, loading: true })); fn().then(data => set({ data, error: null, loading: false })).catch(e => set({ data: null, error: e.message, loading: false })) }, deps) // eslint-disable-line
  useEffect(load, [load])
  return { ...s, reload: load }
}

export function Logo({ dark, sub = 'COMPANY' }) {
  return <div className="flex items-end gap-2"><span className={cls('text-2xl font-black tracking-tight', dark ? 'text-white' : 'text-wow-green')}>WOW</span><span className="text-[9px] tracking-[.2em] text-slate-400 mb-1">{sub}</span></div>
}

// 제품군별 기본 이미지
const PRODUCT_IMAGES = {
  purifier: '/images/products/CP-7211.png',
  air: '/images/products/air.png',
  bidet: '/images/products/bidet.png',
  softener: '/images/products/softener.png',
  mattress: '/images/products/mattress.png',
  chair: '/images/products/chair.png',
}

// 정수기 모델별 이미지
const MODEL_IMAGES = {
  'CPI-7400': '/images/products/CPI-7400.png',
  'CHP-5610': '/images/products/CHP-5610.png',
  'CP-7211': '/images/products/CP-7211.png',
}

const PRODUCT_NAMES = {
  purifier: '정수기',
  air: '공기청정기',
  bidet: '비데',
  softener: '연수기',
  mattress: '매트리스',
  chair: '안마의자',
}

export function Art({
  kind = 'purifier',
  productCode,
  className = 'w-full h-full',
}) {
  const src =
    MODEL_IMAGES[productCode] || PRODUCT_IMAGES[kind]

  if (!src) {
    return (
      <div
        className={`${className} flex items-center justify-center text-sm text-slate-400`}
      >
        제품 이미지 준비 중
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={
        productCode
          ? `${PRODUCT_NAMES[kind] || '렌탈 제품'} ${productCode}`
          : PRODUCT_NAMES[kind] || '렌탈 제품'
      }
      className={`${className} object-contain`}
      loading="lazy"
    />
  )
}

export const Card = ({ className = '', dark, children, ...p }) => <div {...p} className={cls('rounded-2xl border', dark ? 'bg-dk-panel border-dk-line text-slate-200' : 'bg-white border-slate-200', className)}>{children}</div>

export function Btn({ children, onClick, kind = 'primary', dark, disabled, className = '', type = 'button', title }) {
  const k = kind === 'primary' ? (dark ? 'bg-dk-blue text-white hover:brightness-110' : 'bg-wow-accent text-white hover:brightness-110')
    : dark ? 'border border-dk-line text-slate-300 hover:bg-white/5' : 'border border-slate-300 text-slate-700 hover:bg-slate-50'
  return <button type={type} title={title} disabled={disabled} onClick={onClick} className={cls('rounded-lg px-4 py-2.5 text-sm font-semibold transition disabled:opacity-40 disabled:cursor-not-allowed', k, className)}>{children}</button>
}

export const Field = ({ label, dark, children }) => <label className="block text-xs font-semibold mb-3"><span className={dark ? 'text-slate-400' : 'text-slate-500'}>{label}</span><div className="mt-1">{children}</div></label>
export const inputCls = dark => cls('w-full rounded-lg border px-3 py-2.5 text-sm', dark ? 'bg-[#30343B] border-dk-line text-white placeholder-slate-500 focus:border-dk-blue' : 'bg-white border-slate-300 focus:border-wow-accent')

export function SourceBadge({ source, dark }) {
  const real = source === 'joblib_model'
  return <span className={cls('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-bold', real ? 'bg-emerald-500/15 text-emerald-400' : 'bg-amber-400/15 text-amber-400')}>
    <i className={cls('h-1.5 w-1.5 rounded-full', real ? 'bg-emerald-400' : 'bg-amber-400')} />{real ? '실제 AI 모델' : '임시 점수'}</span>
}
export const DemoTag = ({ children = '데이터' }) => <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-700 align-middle">{children}</span>
export const Err = ({ msg, dark }) => msg ? <p className={cls('text-sm my-2', dark ? 'text-dk-red' : 'text-red-600')}>{msg}</p> : null
export const Spin = ({ dark }) => <p className={cls('p-6 text-sm', dark ? 'text-slate-400' : 'text-slate-500')}>불러오는 중…</p>

export const GRADE = { 고위험: 'bg-dk-red/15 text-dk-red', 중위험: 'bg-dk-amber/15 text-dk-amber', 저위험: 'bg-emerald-400/15 text-emerald-400' }
export const GradeChip = ({ g }) => <span className={cls('rounded-md px-2 py-0.5 text-xs font-bold', GRADE[g])}>{g}</span>
