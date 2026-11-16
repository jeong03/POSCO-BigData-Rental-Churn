import { JSDOM } from 'jsdom'
import { test, afterEach } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const dom=new JSDOM('<!doctype html><html><body></body></html>',{url:'http://localhost/'})
for(const k of ['window','document','HTMLElement','Node','MutationObserver'])globalThis[k]=dom.window[k]
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
globalThis.getComputedStyle=dom.window.getComputedStyle
const { render, screen, fireEvent, waitFor, cleanup }=await import('@testing-library/react')
const React=await import('react')
const { RecommendationPanel }=await import('../src/recommendations.jsx')
const fixture=(name)=>JSON.parse(readFileSync(new URL(`./fixtures/${name}.json`,import.meta.url),'utf8'))
afterEach(cleanup)

test('사업장 탭, TOP 3, 이미지, 적합도, 상품 상세 표시',()=>{
 const d=fixture('business');render(<RecommendationPanel d={d}/> )
 assert.equal(screen.getAllByRole('article').length,3)
 assert.equal(screen.getAllByRole('progressbar').length,3)
 assert.equal(screen.getAllByRole('img').length,3)
 assert.ok(screen.getByText(d.business.name));assert.ok(screen.getByText(/계약 확률 아님/))
 fireEvent.click(screen.getByRole('tab',{name:'클레임 · AS'}));assert.ok(screen.getByText('앱 AS 접수 · 실제'))
 fireEvent.click(screen.getByRole('tab',{name:'방문 · 사업 활동'}));assert.ok(screen.getByText('고객사 활동상'))
 fireEvent.click(screen.getAllByText('상품 상세보기 · 산정 근거')[0]);assert.ok(screen.getAllByText(/설치 환경·실제 용량/).length)
})
test('상담 등록 → 담당자/상태/결과 저장, 고객별 경로 및 상품 검증',async()=>{
 const d=fixture('business');let stored=[],requests=[]
 globalThis.fetch=async(url,opts={})=>{
  requests.push({url,opts});let data
  if(opts.method==='POST'){const b=JSON.parse(opts.body);stored=[{id:91,...b,customer_id:d.customer_id,status:'접수',result:'',recommendation:JSON.stringify(d.recommendations[0])}];data=stored[0]}
  else if(opts.method==='PATCH'){stored=[{...stored[0],...JSON.parse(opts.body)}];data=stored[0]}
  else data=stored
  return {ok:true,json:async()=>data}
 }
 render(<RecommendationPanel d={d}/> )
 fireEvent.click(screen.getAllByText('추가 계약 상담 등록')[0])
 fireEvent.change(screen.getByLabelText('담당 코디 또는 영업 담당자'),{target:{value:'영업 담당자'}})
 fireEvent.change(screen.getByLabelText('상담 내용'),{target:{value:'공간 확인 후 견적'}})
 fireEvent.click(screen.getByText('상담 등록 저장'))
 await waitFor(()=>assert.ok(screen.getByText(/추가 계약 상담을 저장했습니다/)))
 assert.equal(stored.length,1);assert.equal(stored[0].product_id,d.recommendations[0].id)
 fireEvent.click(screen.getByText(/#91/))
 fireEvent.change(screen.getByLabelText('상담 상태'),{target:{value:'계약완료'}})
 fireEvent.change(screen.getByLabelText('상담 결과'),{target:{value:'견적 동의 완료'}})
 fireEvent.click(screen.getByText('상태 · 결과 저장'))
 await waitFor(()=>assert.equal(stored[0].status,'계약완료'))
 assert.equal(stored[0].result,'견적 동의 완료')
 assert.ok(requests.every(r=>r.url.includes('/customer/'+d.customer_id+'/consultations')))
})
test('개인 전환 시 사업장/상담 입력 상태 제거, 개인 순위 유지',()=>{
 const b=fixture('business'),p=fixture('personal');const {rerender}=render(<RecommendationPanel key={b.customer_id} d={b}/> )
 fireEvent.click(screen.getAllByText('추가 계약 상담 등록')[0])
 rerender(<RecommendationPanel key={p.customer_id} d={p}/> )
 assert.equal(screen.queryAllByRole('tab').length,0);assert.equal(screen.queryByLabelText('상담 내용'),null)
 assert.ok(screen.getByText('개인 맞춤형 추천 TOP 3'))
 const cards=screen.getAllByRole('article');p.recommendations.forEach((r,i)=>assert.ok(cards[i].textContent.includes(r.name)))
})
test('상담 저장 실패 메시지와 재시도 입력 유지',async()=>{
 const d=fixture('business');globalThis.fetch=async()=>({ok:false,json:async()=>({detail:'관리자 권한이 필요합니다.'})})
 render(<RecommendationPanel d={d}/> )
 fireEvent.click(screen.getAllByText('추가 계약 상담 등록')[0]);fireEvent.change(screen.getByLabelText('상담 내용'),{target:{value:'실패 후 보존'}})
 fireEvent.click(screen.getByText('상담 등록 저장'))
 await waitFor(()=>assert.ok(screen.getByText('관리자 권한이 필요합니다.')))
 assert.equal(screen.getByLabelText('상담 내용').value,'실패 후 보존')
})
