# -*- coding: utf-8 -*-
"""시장 지표 시세를 수집한다.

야후의 일봉 시계열은 최근 거래일이 하루 이틀 늦게 반영되는 일이 잦다
(닛케이가 이틀 빠지는 것을 확인). 그래서 세 소스를 합쳐 쓴다.

    fast_info   현재가/전일종가 — 가장 최신. 시세의 주 소스
    1시간봉     마지막 체결 시각 — 거래일과 장중 여부 판정용
    1년 일봉    52주 전고점, 그리고 fast_info가 실패했을 때의 대비책
"""

import time
import warnings
from datetime import datetime
from zoneinfo import ZoneInfo

import yfinance as yf

warnings.filterwarnings("ignore", category=FutureWarning)

# 시장별 정규 마감 시각. (시간대, 시, 분, 표기명)
MARKETS = {
    "kr": ("Asia/Seoul", 15, 30, "국내"),
    "us": ("America/New_York", 16, 0, "미국"),
    "jp": ("Asia/Tokyo", 15, 0, "일본"),
    "cn": ("Asia/Shanghai", 15, 0, "중국"),
}
CONTINUOUS = {"fx": "외환", "futures": "선물", "crypto": "코인"}


class Quote:
    def __init__(self, item):
        self.name = item["name"]
        self.ticker = item["ticker"]
        self.fmt = item.get("fmt", "num")
        self.unit = item.get("unit", "")
        self.market = item.get("market", "us")
        self.watch_drawdown = item.get("watch_drawdown", False)
        self.last = None
        self.prev = None
        self.last_ts = None        # 마지막 체결 시각 (시장 현지 시간)
        self.high_52w = None       # 52주 장중 최고가
        self.high_date = None

    @property
    def ok(self):
        return self.last is not None and self.prev is not None

    @property
    def date(self):
        return self.last_ts.date() if self.last_ts else None

    @property
    def continuous(self):
        return self.market in CONTINUOUS

    @property
    def closed(self):
        """정규장이 이미 끝났는가. 24시간 시장은 항상 False."""
        if self.continuous or self.last_ts is None or self.market not in MARKETS:
            return False
        tz, hour, minute, _ = MARKETS[self.market]
        close = datetime(
            self.last_ts.year, self.last_ts.month, self.last_ts.day,
            hour, minute, tzinfo=ZoneInfo(tz),
        )
        return datetime.now(ZoneInfo(tz)) >= close

    @property
    def change(self):
        return self.last - self.prev if self.ok else None

    @property
    def change_pct(self):
        if not self.ok or self.prev == 0:
            return None
        return (self.last - self.prev) / self.prev * 100.0

    @property
    def drawdown_pct(self):
        """52주 전고점 대비 하락률."""
        if self.last is None or not self.high_52w:
            return None
        return (self.last - self.high_52w) / self.high_52w * 100.0


def fetch_quotes(groups, retries=2):
    quotes = []
    for group in groups:
        for item in group.get("items", []):
            quotes.append(Quote(item))
    tickers = [q.ticker for q in quotes]

    _apply_daily(quotes, _download(tickers, "1y", "1d"))
    _apply_intraday(quotes, _download(tickers, "5d", "1h"))
    for q in quotes:
        _apply_fast_info(q)

    for attempt in range(retries):
        missing = [q for q in quotes if not q.ok]
        if not missing:
            break
        time.sleep(1.0 + attempt)
        for q in missing:
            _apply_daily([q], _download([q.ticker], "1y", "1d"))
            _apply_fast_info(q)

    return quotes


def _download(tickers, period, interval):
    """{ticker: DataFrame(Close/High)} 형태로 돌려준다."""
    try:
        data = yf.download(
            tickers, period=period, interval=interval,
            auto_adjust=False, progress=False, threads=False,
        )
    except Exception as e:
        print(f"[수집 오류] {period}/{interval}: {e}")
        return {}

    if data is None or data.empty or "Close" not in data:
        return {}

    close, high = data["Close"], data.get("High")
    out = {}
    for t in tickers:
        if hasattr(close, "columns"):
            if t not in close.columns:
                continue
            c = close[t]
            h = high[t] if high is not None and t in high.columns else c
        else:
            if len(tickers) != 1:
                continue
            c, h = close, (high if high is not None else close)
        out[t] = (c, h)
    return out


def _apply_daily(quotes, downloaded):
    """52주 전고점을 채우고, 시세는 일단 일봉 기준으로 채워둔다."""
    for q in quotes:
        pair = downloaded.get(q.ticker)
        if pair is None:
            continue
        close, high = pair

        c = close.dropna()
        if len(c) >= 2:
            q.last = float(c.iloc[-1])
            q.prev = float(c.iloc[-2])
            q.last_ts = _to_market_time(c.index[-1], q.market)

        h = high.dropna()
        if len(h):
            q.high_52w = float(h.max())
            q.high_date = h.idxmax().date()


def _apply_intraday(quotes, downloaded):
    """마지막 체결 시각을 시장 현지 시간으로 잡아둔다."""
    for q in quotes:
        pair = downloaded.get(q.ticker)
        if pair is None:
            continue
        c = pair[0].dropna()
        if len(c):
            q.last_ts = _to_market_time(c.index[-1], q.market)


def _apply_fast_info(q):
    """현재가·전일종가를 fast_info에서 덮어쓴다. 실패하면 일봉 값을 유지."""
    try:
        fi = yf.Ticker(q.ticker).fast_info
        last, prev = fi.get("lastPrice"), fi.get("previousClose")
    except Exception:
        return
    if last is None:
        return
    q.last = float(last)
    if prev is not None:
        q.prev = float(prev)
    if q.high_52w and q.last > q.high_52w:
        q.high_52w = q.last      # 장중 신고가


def _to_market_time(ts, market):
    """야후 타임스탬프를 시장 현지 시간으로 옮긴다."""
    tz = MARKETS.get(market, (None,))[0]
    try:
        if ts.tzinfo is None:
            return ts.to_pydatetime()
        if tz:
            return ts.tz_convert(ZoneInfo(tz)).to_pydatetime()
        return ts.tz_convert(ZoneInfo("Asia/Seoul")).to_pydatetime()
    except Exception:
        return ts.to_pydatetime()
