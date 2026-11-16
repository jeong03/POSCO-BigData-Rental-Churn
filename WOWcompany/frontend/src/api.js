// 토큰은 메모리에만 보관합니다(브라우저 저장소 미사용). 새로고침하면 재로그인.
let token = null
export const setToken = t => { token = t }
export async function api(path, { method = 'GET', body } = {}) {
  const r = await fetch('/api' + path, {
    method, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: 'Bearer ' + token } : {}) },
    body: body ? JSON.stringify(body) : undefined })
  const j = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : (j.detail?.message || '요청에 실패했습니다.'))
  return j
}

export async function downloadPdf(id) {
  const r = await fetch(`/api/admin/report/${id}/pdf`, { headers: token ? { Authorization: 'Bearer ' + token } : {} })
  if (!r.ok) throw new Error('PDF 다운로드 실패: 관리자 로그인과 서버 상태를 확인하세요.')
  const url = URL.createObjectURL(await r.blob())
  const a = document.createElement('a'); a.href = url; a.download = `wow_report_${id}.pdf`; a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
