"""Admin-only consultation and persisted report retrieval endpoints."""
import io
import json
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator

class ConsultationCreate(BaseModel):
    product_id: str
    content: str = Field(min_length=1,max_length=4000)
    assignee: str = Field(min_length=1,max_length=80)
    @field_validator('content','assignee')
    @classmethod
    def not_blank(cls,v):
        if not v.strip(): raise ValueError('공백만 입력할 수 없습니다.')
        return v.strip()

class ConsultationUpdate(BaseModel):
    content: str = Field(min_length=1,max_length=4000)
    assignee: str = Field(min_length=1,max_length=80)
    status: Literal['접수','상담중','견적제안','계약완료','보류','종료']
    result: str = Field(default='',max_length=4000)
    @field_validator('content','assignee')
    @classmethod
    def not_blank(cls,v):
        if not v.strip(): raise ValueError('공백만 입력할 수 없습니다.')
        return v.strip()


def install(app, run, need_admin, detail, now, base):
    router=APIRouter(prefix='/api/admin',dependencies=[Depends(need_admin)])
    @router.get('/customer/{cid}/consultations')
    def listing(cid: str):
        detail(cid)
        return run('SELECT * FROM rental_consultations WHERE customer_id=? ORDER BY id DESC',(cid,),True)
    @router.post('/customer/{cid}/consultations',status_code=201)
    def create(cid: str,b: ConsultationCreate,s=Depends(need_admin)):
        d=detail(cid); p=next((p for p in d['recommendations'] if p['id']==b.product_id),None)
        if not p: raise HTTPException(422,'현재 추천 목록에 있는 상품을 선택하세요.')
        t=now()
        rid=run('INSERT INTO rental_consultations(customer_id,product_id,content,assignee,status,result,recommendation,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (cid,b.product_id,b.content,b.assignee,'접수','',json.dumps(p,ensure_ascii=False),s['id'],t,t))
        return run('SELECT * FROM rental_consultations WHERE id=?',(rid,),True)[0]
    @router.patch('/customer/{cid}/consultations/{consultation_id}')
    def update(cid: str,consultation_id: int,b: ConsultationUpdate):
        if not run('SELECT id FROM rental_consultations WHERE id=? AND customer_id=?',(consultation_id,cid),True):
            raise HTTPException(404,'해당 고객의 상담을 찾을 수 없습니다.')
        if b.status in ('계약완료','종료') and not b.result.strip(): raise HTTPException(422,'완료·종료 시 상담 결과를 입력하세요.')
        run('UPDATE rental_consultations SET content=?,assignee=?,status=?,result=?,updated_at=? WHERE id=? AND customer_id=?',
            (b.content,b.assignee,b.status,b.result,now(),consultation_id,cid))
        return run('SELECT * FROM rental_consultations WHERE id=?',(consultation_id,),True)[0]
    @router.get('/customer/{cid}/reports')
    def reports(cid: str):
        detail(cid)
        return run('SELECT id,customer_id,created_by,created_at FROM reports WHERE customer_id=? ORDER BY id DESC',(cid,),True)
    def get_report(report_id):
        rows=run('SELECT * FROM reports WHERE id=?',(report_id,),True)
        if not rows: raise HTTPException(404,'보고서를 찾을 수 없습니다.')
        return rows[0]
    @router.get('/report/{report_id}')
    def report(report_id: int): return get_report(report_id)
    @router.get('/report/{report_id}/pdf')
    def pdf(report_id: int):
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib import colors
        from xml.sax.saxutils import escape
        r=get_report(report_id)
        if 'WOWKorean' not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont('WOWKorean',str(base/'fonts'/'NanumGothic.ttf')))
        out=io.BytesIO(); style=ParagraphStyle('body',fontName='WOWKorean',fontSize=9,leading=15,wordWrap='CJK',spaceAfter=5)
        title=ParagraphStyle('title',parent=style,fontSize=16,leading=23,textColor=colors.HexColor('#263449'),spaceAfter=14)
        def footer(canvas,doc):
            canvas.setFont('WOWKorean',8);canvas.drawString(42,25,'WOW Company | 내부 고객 관리 보고서');canvas.drawRightString(553,25,str(doc.page))
        story=[]
        for i,line in enumerate(r['text'].splitlines()):
            story.append(Paragraph(escape(line.replace("㎡", "제곱미터")),title if i==0 else style) if line else Spacer(1,8))
        SimpleDocTemplate(out,rightMargin=42,leftMargin=42,topMargin=40,bottomMargin=45,title='WOW 고객 관리 보고서').build(story,onFirstPage=footer,onLaterPages=footer)
        return Response(out.getvalue(),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="wow_report_{report_id}.pdf"','Cache-Control':'no-store'})
    app.include_router(router)
