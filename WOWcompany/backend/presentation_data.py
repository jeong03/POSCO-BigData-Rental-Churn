"""Presentation-only operational timeline. Never used for ML training or scoring."""
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import pandas as pd


def operational_timeline(customer_count, today=None):
    today=today or datetime.now(ZoneInfo('Asia/Seoul')).date()
    opening=max(1000,int(customer_count));remaining=opening;daily=[]
    for dt in pd.date_range(f'{today.year}-01-01',today):
        # Fixed date seed means revisiting the dashboard does not change history.
        seed=int(hashlib.sha256(dt.date().isoformat().encode()).hexdigest()[:8],16)
        count=min(remaining,2+seed%6)
        daily.append(dict(date=dt.date().isoformat(),opening=remaining,cancelled=count,rate=count/remaining*100))
        remaining-=count
    months=[]
    for month in range(1,today.month+1):
        rows=[r for r in daily if int(r['date'][5:7])==month]
        n=sum(r['cancelled'] for r in rows)
        months.append(dict(month=f'{month}월',opening=rows[0]['opening'],cancelled=n,rate=n/rows[0]['opening']*100))
    return dict(source='presentation_synthetic',basis='기간 시작 정상 고객 대비 기간 내 해약 고객',as_of=today.isoformat(),
                today=daily[-1],month=months[-1],year=dict(opening=opening,cancelled=opening-remaining,rate=(opening-remaining)/opening*100),
                monthly=months,daily=daily)
