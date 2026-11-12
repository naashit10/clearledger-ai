"""
ClearLedger AI — Dashboard Data Export
Aggregates pipeline outputs into the small CSV tables behind the interactive
dashboard (dashboard/clearledger_dashboard.html) and for Power BI / Tableau import.
Amounts are converted to USD at fixed, indicative rates (not market rates).
Author: Syed Naashit Hashmi
"""
import os, sys, pandas as pd, numpy as np
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import importlib.util
spec=importlib.util.spec_from_file_location('anom',os.path.join(os.path.dirname(os.path.abspath(__file__)),'04_anomaly_detection.py'));an=importlib.util.module_from_spec(spec);spec.loader.exec_module(an)
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D=ROOT+'/data/';O=ROOT+'/outputs/';B=ROOT+'/dashboard/data/'
os.makedirs(B,exist_ok=True)
FX={'INR':0.012,'SGD':0.74,'GBP':1.27,'USD':1.0}
ECUR={'AMX-IN-01':'INR','AMX-IN-02':'INR','AMX-SG-01':'SGD','AMX-UK-01':'GBP','AMX-US-01':'USD'}
r=pd.read_csv(O+'reconciliation_results.csv')
r['d']=pd.to_datetime(r.gl_date.fillna(r.bank_date)); r['month']=r.d.dt.strftime('%Y-%m')
g=r.groupby(['month','entity']).agg(items=('status','size'),
  exact=('match_tier',lambda s:(s=='TIER1_EXACT').sum()),timing=('match_tier',lambda s:(s=='TIER2_TIMING').sum()),
  fuzzy=('match_tier',lambda s:(s=='TIER3_FUZZY_AMOUNT').sum()),unmatched=('match_tier',lambda s:(s=='UNMATCHED').sum())).reset_index()
assert g['items'].sum()==5824 and g.unmatched.sum()==1019
g.to_csv(B+'monthly_by_entity.csv',index=False)
b=pd.read_csv(O+'classified_breaks.csv')
b['outcome']=np.where(b.status.str.startswith('BREAK'),'Unmatched','Matched with note')
b['val']=b.gl_amount.fillna(b.bank_amount).abs()*b.entity.map(ECUR).map(FX)
e=b.groupby(['entity','break_category','outcome']).agg(items=('val','size'),value_usd=('val','sum')).reset_index()
e['value_usd']=e.value_usd.round(0).astype(int); e.rename(columns={'break_category':'category'}).to_csv(B+'exceptions.csv',index=False)
# anomalies
gl=pd.read_csv(D+'general_ledger.csv',dtype={'gl_account':str})
gl=an.detect(an.engineer_features(gl)); gl['score']=-gl.anomaly_raw_score
fl=gl.is_anomaly==1; NF=int(fl.sum())
pd.DataFrame([[n,int(gl[c].sum()),int(gl.loc[fl,c].sum())] for n,c in [('Weekend posting','is_weekend'),('Manual journal entry','is_manual'),('Round amount','is_round_amount'),('Month-end posting','is_month_end'),('Infrequent user','user_rare')]],columns=['driver','journals','flagged']).assign(flag_rate=lambda d:(d.flagged/d.journals).round(4)).to_csv(B+'anomaly_drivers.csv',index=False)
bins=np.linspace(gl.score.min(),gl.score.max()+1e-9,31)
h,_=np.histogram(gl.score,bins);hf,_=np.histogram(gl.score[fl],bins)
pd.DataFrame({'bin_lo':bins[:-1].round(4),'bin_hi':bins[1:].round(4),'journals':h,'flagged':hf}).to_csv(B+'anomaly_scores.csv',index=False)
gl.groupby('entity').agg(journals=('journal_id','size'),flagged=('is_anomaly','sum')).reset_index().to_csv(B+'anomaly_by_entity.csv',index=False)
t=gl[fl].sort_values('score',ascending=False).head(10).copy(); t['currency']=t.entity.map(ECUR)
t['score']=t.score.round(3)
t[['journal_id','posting_date','entity','gl_account_name','amount','currency','source_system','posted_by','score']].to_csv(B+'anomaly_top.csv',index=False)
# AP
inv=pd.read_csv(D+'vendor_invoices.csv',parse_dates=['due_date'])
o=inv[inv.status.isin(['OPEN','OVERDUE'])].copy(); o['usd']=o.invoice_amount*o.currency.map(FX)
o['dpd']=(pd.Timestamp('2026-06-01')-o.due_date).dt.days
o['sort']=pd.cut(o.dpd,[-10**6,0,30,60,90,10**6],labels=[1,2,3,4,5]).astype(int)
nm={1:'Current',2:'1-30 days',3:'31-60 days',4:'61-90 days',5:'90+ days'}
ap=o.groupby('sort').agg(invoices=('usd','size'),amount_usd=('usd','sum')).reset_index(); ap['bucket']=ap['sort'].map(nm); ap['amount_usd']=ap.amount_usd.round(0).astype(int)
ap[['bucket','invoices','amount_usd','sort']].to_csv(B+'ap_aging.csv',index=False)
# IC
ic=pd.read_csv(D+'intercompany_transactions.csv'); ic['mis']=(ic.amount_sender-ic.amount_receiver).abs()>0.01
ic.groupby('nature').agg(transactions=('ic_id','size'),mismatches=('mis','sum'),pending=('settlement_status',lambda s:(s=='PENDING').sum())).reset_index().to_csv(B+'intercompany.csv',index=False)
pd.DataFrame([['General ledger journals',len(gl)],['Bank statement lines',len(pd.read_csv(D+'bank_statements.csv'))],['Vendor invoices',len(inv)],['Intercompany transactions',len(ic)]],columns=['source','records']).to_csv(B+'record_sources.csv',index=False)
pd.DataFrame([[k,v] for k,v in FX.items()],columns=['currency','usd_rate']).to_csv(B+'fx.csv',index=False)

print(f'Dashboard data written to {B}')
