"""러너에서 어떤 호출이 온전한 1년 시계열을 돌려주는지 시험한다."""
import time
from datetime import date, timedelta
import yfinance as yf

TICKERS = ["^KS200", "^TNX", "^KS11"]
today = date.today()
start = today - timedelta(days=400)


def show(label, fn, tries=3):
    for t in TICKERS:
        results = []
        for _ in range(tries):
            try:
                h = fn(t)
                if h is None or len(h) == 0:
                    results.append("빈응답")
                else:
                    results.append(f"{len(h)}건/{float(h.max()):.2f}")
            except Exception as e:
                results.append(f"오류:{type(e).__name__}")
            time.sleep(0.4)
        print(f"  {label:<28} {t:<8} {results}")


def _high(d):
    if d is None or getattr(d, "empty", True) or "High" not in d:
        return None
    h = d["High"].dropna()
    if hasattr(h, "columns"):
        h = h.iloc[:, 0]
    return h


print("=== 호출 방식별 (각 3회) ===")
show("download period=1y",
     lambda t: _high(yf.download(t, period="1y", interval="1d",
                                 auto_adjust=False, progress=False, threads=False)))
show("download start/end 400일",
     lambda t: _high(yf.download(t, start=start, end=today + timedelta(days=1),
                                 interval="1d", auto_adjust=False,
                                 progress=False, threads=False)))
show("download period=2y",
     lambda t: _high(yf.download(t, period="2y", interval="1d",
                                 auto_adjust=False, progress=False, threads=False)))
show("download period=1y 주봉",
     lambda t: _high(yf.download(t, period="1y", interval="1wk",
                                 auto_adjust=False, progress=False, threads=False)))
show("Ticker.history period=1y",
     lambda t: _high(yf.Ticker(t).history(period="1y", interval="1d",
                                          auto_adjust=False)))

print("\n=== info / metadata 의 52주 고점 ===")
for t in TICKERS:
    try:
        md = yf.Ticker(t).history_metadata
        print(f"  {t} history_metadata:",
              {k: md.get(k) for k in ("fiftyTwoWeekHigh", "regularMarketDayHigh")})
    except Exception as e:
        print(f"  {t} history_metadata 오류: {type(e).__name__} {e}")
    try:
        info = yf.Ticker(t).info
        print(f"  {t} info fiftyTwoWeekHigh:", info.get("fiftyTwoWeekHigh"))
    except Exception as e:
        print(f"  {t} info 오류: {type(e).__name__} {e}")

print("\nyfinance", yf.__version__)
