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

# 1년 일봉이 이보다 적게 오면 52주 고점을 믿지 않는다.
# 야후가 특정 티커에 대해 시계열을 한두 건만 돌려주는 일이 실제로 있다
# (GitHub 러너 IP에서 ^KS200이 당일 1건만 와서 "당일 장중가 = 52주 고점"이 됨).
MIN_HIGH_BARS = 150


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
        self.high_bars = 0         # 고점 산출에 쓴 일봉 건수

    @property
    def ok(self):
        return self.last is not None and self.prev is not None

    @property
    def high_ok(self):
        """52주 고점을 믿을 만한가. 일봉이 너무 적으면 고점이 아니라 최근값이다."""
        return self.high_52w is not None and self.high_bars >= MIN_HIGH_BARS

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

    _repair_highs(quotes, retries)
    return quotes


def _repair_highs(quotes, retries=2):
    """일봉이 잘려 온 티커의 52주 고점을 개별 재조회로 되살린다.

    배치 다운로드에서만 잘리고 개별 조회로는 멀쩡히 오는 경우가 있다.
    끝내 못 채우면 틀린 고점을 보여주느니 아예 비운다 —
    `fast_info`의 yearHigh도 같은 잘린 응답에서 나오므로 대안이 못 된다.
    """
    for attempt in range(retries):
        short = [q for q in quotes if not q.high_ok]
        if not short:
            break
        for q in short:
            time.sleep(0.3)
            _apply_daily([q], _download([q.ticker], "1y", "1d"), high_only=True)

    for q in quotes:
        if not q.high_ok:
            print(f"[고점] {q.name}: 일봉 {q.high_bars}건뿐 — 52주 고점 생략")
            q.high_52w = None
            q.high_date = None
        elif q.last is not None and q.last > q.high_52w:
            q.high_52w = q.last      # 장중 신고가


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


def _apply_daily(quotes, downloaded, high_only=False):
    """52주 전고점을 채우고, 시세는 일단 일봉 기준으로 채워둔다.

    high_only=True면 고점만 손본다. 고점 재조회 때 이미 fast_info로 채워둔
    현재가를 며칠 지난 일봉 종가로 되돌리지 않기 위한 것.
    """
    for q in quotes:
        pair = downloaded.get(q.ticker)
        if pair is None:
            continue
        close, high = pair

        if not high_only:
            c = close.dropna()
            if len(c) >= 2:
                q.last = float(c.iloc[-1])
                q.prev = float(c.iloc[-2])
                q.last_ts = _to_market_time(c.index[-1], q.market)

        h = high.dropna()
        # 재조회분이 더 긴 시계열일 때만 갱신한다. 잘린 응답이 멀쩡한 고점을
        # 덮어쓰지 않도록 건수와 값을 모두 비교한다.
        if len(h) and (len(h) > q.high_bars or q.high_52w is None
                       or float(h.max()) > q.high_52w):
            if float(h.max()) > (q.high_52w or 0):
                q.high_52w = float(h.max())
                q.high_date = h.idxmax().date()
            q.high_bars = max(q.high_bars, len(h))


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
