"""Download the full Newsweb announcement list (titles, all categories) 2019- for event studies.
The list API caps a query at ~600 messages, so capped 5-day windows are re-queried day by day. ~1 request/s.
Run: python -m signaltool.backtest._newsweb_all_list  -> data/cache/newsweb_all_list.pkl"""
import time, logging, pandas as pd
from datetime import date, timedelta
from signaltool import http
from signaltool.config import CACHE


def main():
    API = "https://api3.oslo.oslobors.no/v1/newsreader/list"
    rows, s, end = [], date(2019, 1, 1), date.today()
    while s <= end:
        e = min(s + timedelta(days=4), end)
        try:
            j = http.get_json(API, params={"category": "", "issuer": "", "fromDate": s.isoformat(), "toDate": e.isoformat(), "market": "", "messageTitle": ""}, cache_hours=24 * 60)
            ms = j["data"]["messages"]
            if len(ms) >= 590:  # capped -> re-query day by day
                ms = []
                d = s
                while d <= e:
                    time.sleep(1.0)
                    jj = http.get_json(API, params={"category": "", "issuer": "", "fromDate": d.isoformat(), "toDate": d.isoformat(), "market": "", "messageTitle": ""}, cache_hours=24 * 60)
                    ms += jj["data"]["messages"]
                    if len(jj["data"]["messages"]) >= 590: print("day cap", d, flush=True)
                    d += timedelta(days=1)
            for m in ms:
                rows.append({"id": m["messageId"], "published": m["publishedTime"], "issuer": m.get("issuerSign"), "issuer_name": m.get("issuerName"),
                             "title": m.get("title"), "category": (m.get("category") or [{}])[0].get("category_en", "")})
        except Exception as ex:
            print("fail", s, ex, flush=True)
        s = e + timedelta(days=1)
        time.sleep(1.0)
    df = pd.DataFrame(rows).drop_duplicates("id")
    df["published"] = pd.to_datetime(df["published"], utc=True)
    df.to_pickle(CACHE / "newsweb_all_list.pkl")
    print("done", len(df), flush=True)


if __name__ == "__main__":
    main()
