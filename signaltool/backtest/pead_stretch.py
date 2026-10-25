import numpy as np, pandas as pd
from signaltool.backtest import universe
from signaltool.backtest.price_rules import hac_t
E=pd.read_pickle(universe.DIR/"pead_events.pkl")
data,members=universe.us()
C=pd.DataFrame({t:data[t]["Close"] for t in set(E.ticker)|{"SPY"} if t in data}).sort_index()
idx=C.index
r5=C/C.shift(5)-1; r20=C/C.shift(20)-1; ma=C/C.rolling(50).mean()-1
rows=[]
for r in E.itertuples():
    p=idx.get_loc(r.date); e=p+1
    rows.append((r5[r.ticker].iloc[e],r20[r.ticker].iloc[e],ma[r.ticker].iloc[e]))
E[["r5","r20","ma"]]=rows
E["str"]=(E.r5>=.10)|(E.r20>=.25)|(E.ma>=.25)
tt=(E["sq"]>=.8)&(E["eq"]>=.8)
out=[]
for per,m in (("IS 2006–15",E.date<"2016-01-01"),("OOS 2016–26",E.date>="2016-01-01")):
  base=E[m]
  for g,gm in (("topp/topp strukket",tt&E["str"]),("topp/topp ikke strukket",tt&~E["str"]),("topp/topp alle",tt)):
    S=E[m&gm]
    for h in (20,60):
      q=(S.groupby("qtr")[f"x{h}"].mean()-0.002)
      sp=(S.groupby("qtr")[f"x{h}"].mean()-base.groupby("qtr")[f"x{h}"].mean()).dropna()
      out.append([per,g,h,len(S),round(S[f"x{h}"].mean()*100-0.2,2),round(S[f"x{h}"].median()*100,2),round(hac_t(q,1),1),round(sp.mean()*100,2),round(hac_t(sp,1),1),round((S[f"x{h}"]>0).mean()*100)])
  # diff strukket vs ikke
  for h in (20,60):
    a=E[m&tt&E["str"]].groupby("qtr")[f"x{h}"].mean(); b=E[m&tt&~E["str"]].groupby("qtr")[f"x{h}"].mean()
    d=(a-b).dropna(); out.append([per,"DIFF strukket−ikke",h,len(d),round(d.mean()*100,2),None,round(hac_t(d,1),1),None,None,None])
R=pd.DataFrame(out,columns=["periode","gruppe","h","n","netto_vs_SPY%","median%","t","spread_vs_alle_pp","t_spread","andel>0%"])
pd.set_option("display.width",200); print(R.to_string(index=False))
print("andel strukket i topp/topp:", round(E[tt]["str"].mean()*100,1))
