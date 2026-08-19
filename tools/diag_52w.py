"""러너와 로컬이 받는 야후 데이터가 왜 다른지 비교하는 일회성 진단."""
import json, sys
import yfinance as yf

TICKERS = ["^KS200", "^KS11", "^KQ11"]

print("=== 1) 배치 다운로드 (본 코드와 동일한 호출) ===")
data = yf.download(TICKERS, period="1y", interval="1d",
                   auto_adjust=False, progress=False, threads=False)
print("frame shape:", None if data is None else data.shape)
if data is not None and not data.empty and "High" in data:
    high = data["High"]
    for t in TICKERS:
        if t not in high.columns:
            print(f"  {t}: 컬럼 없음"); continue
        h = high[t].dropna()
        print(f"  {t}: 행 {len(h)}건, 기간 {h.index[0].date()}~{h.index[-1].date()}, "
              f"max {float(h.max()):.2f} @ {h.idxmax().date()}")

print("\n=== 2) 개별 다운로드 ===")
for t in TICKERS:
    d = yf.download(t, period="1y", interval="1d",
                    auto_adjust=False, progress=False, threads=False)
    if d is None or d.empty:
        print(f"  {t}: 비어 있음"); continue
    h = d["High"].dropna()
    if hasattr(h, "columns"):
        h = h.iloc[:, 0]
    print(f"  {t}: 행 {len(h)}건, 기간 {h.index[0].date()}~{h.index[-1].date()}, "
          f"max {float(h.max()):.2f} @ {h.idxmax().date()}")

print("\n=== 3) Ticker.history ===")
for t in TICKERS:
    try:
        d = yf.Ticker(t).history(period="1y", interval="1d", auto_adjust=False)
        h = d["High"].dropna()
        print(f"  {t}: 행 {len(h)}건, max {float(h.max()):.2f} @ {h.idxmax().date()}")
    except Exception as e:
        print(f"  {t}: 오류 {e}")

print("\n=== 4) fast_info ===")
for t in TICKERS:
    try:
        fi = yf.Ticker(t).fast_info
        print(f"  {t}: yearHigh={fi.get('yearHigh')} yearLow={fi.get('yearLow')} "
              f"last={fi.get('lastPrice')} prev={fi.get('previousClose')}")
    except Exception as e:
        print(f"  {t}: 오류 {e}")

print("\nyfinance", yf.__version__)
