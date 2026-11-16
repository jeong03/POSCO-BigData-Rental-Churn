"""Create missing synthetic profiles; never overwrite existing profiles or the CSV."""
import main

def seed():
    created = 0
    for cid, idx in main.ALL_IDX.items():
        rows = main.df.iloc[idx]
        if set(rows['고객유형'].dropna().astype(str).str.strip()) != {'사업자'}:
            continue
        if main.run('SELECT 1 FROM business_profiles WHERE customer_id=?',(cid,),True):
            continue
        contracts = [main.contract_view(r) for _,r in rows.iterrows()]
        main.RECOMMENDATIONS.profile(cid, contracts)
        created += 1
    print(f'Created {created} business profiles; existing profiles retained.')

if __name__ == '__main__': seed()
