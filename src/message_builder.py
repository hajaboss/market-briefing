# -*- coding: utf-8 -*-
"""수집한 시세를 텔레그램 메시지로 렌더링한다.

config의 options.layout으로 두 형태를 고른다.

    detailed  지표당 두 줄. 단위와 52주 전고점까지 다 보여준다 (기본)
              코스피     6,869.83 pt   -1.55%
                   -108.11  고점 9,385.59 (-26.8%)

    compact   지표당 한 줄. 폭 31칸으로 줄이고 전고점은 특이사항에만
              코스피    6,870   -108  -1.55%
"""

import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

from market_data import CONTINUOUS, MARKETS

KST = ZoneInfo("Asia/Seoul")
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

# detailed 레이아웃 칸 너비
NAME_W = 9
VALUE_W = 10
UNIT_W = 3
PCT_W = 8

# compact 레이아웃 칸 너비
C_NAME_W = 9
C_VALUE_W = 7
C_CHANGE_W = 7
C_PCT_W = 8


def build_message(quotes, groups, alerts, layout="detailed"):
    compact = layout == "compact"
    now = datetime.now(KST)
    parts = [
        f"<b>📊 {now.month}월 {now.day}일 "
        f"({WEEKDAYS[now.weekday()]}) 시장 브리핑</b>"
    ]

    by_ticker = {q.ticker: q for q in quotes}
    name_w = max((_width(q.name) for q in quotes), default=NAME_W) + 1

    for group in groups:
        rows = [by_ticker[i["ticker"]] for i in group.get("items", [])
                if i["ticker"] in by_ticker]
        if not rows:
            continue

        regular = [r for r in rows if not r.continuous and r.date]
        base = max((r.date for r in regular), default=None)

        title = group["title"]
        if base:
            label = "장중" if any(not r.closed for r in regular) else "종가"
            title += f" · {base.month}/{base.day} {label}"

        render = _render_compact if compact else _render_detailed
        body = "\n".join(render(q, base) for q in rows)
        parts.append(f"\n\n<b>{title}</b>\n<pre>{body}</pre>")

    comments = _build_comments(quotes, alerts, compact)
    if comments:
        parts.append("\n\n<b>💬 특이사항</b>\n" + "\n".join(comments))

    failed = [q.name for q in quotes if not q.ok]
    if failed:
        parts.append(f"\n\n<i>⚠️ 수집 실패: {', '.join(failed)}</i>")

    note = _timing_compact if compact else _timing_detailed
    parts.append("\n\n" + note(quotes, now))
    return "".join(parts)


# ------------------------------------------------------------- detailed

def _render_detailed(q, base_date, name_w=NAME_W):
    """값·단위·등락률을 윗줄에, 변화량과 전고점을 아랫줄에."""
    if not q.ok:
        return _pad(q.name, name_w) + _rjust("수집 실패", VALUE_W)

    head = (
        _pad(q.name, name_w)
        + _rjust(_fmt_value(q.last, q.fmt), VALUE_W)
        + " " + _pad(q.unit, UNIT_W)
        + _rjust(f"{q.change_pct:+.2f}%", PCT_W)
    )
    if base_date and q.date and q.date != base_date and not q.continuous:
        head += f" {q.date.month}/{q.date.day}"

    tail = "   " + _rjust(_fmt_change(q), 9)
    if q.high_52w and q.drawdown_pct is not None:
        gap = (f"{(q.last - q.high_52w) * 100:+.0f}bp" if q.fmt == "rate"
               else f"{q.drawdown_pct:+.1f}%")
        tail += f"  고점 {_fmt_value(q.high_52w, q.fmt)} ({gap})"
    return head + "\n" + tail


def _timing_detailed(quotes, now):
    """시장별로 한 줄씩 풀어서 적는다."""
    lines = ["<i>🕘 기준 시각 (한국시간)</i>"]
    seen = {}
    for q in quotes:
        if q.ok and q.last_ts and q.market in MARKETS:
            seen.setdefault(q.market, q)

    for key, (tz, hour, minute, label) in MARKETS.items():
        q = seen.get(key)
        if q is None:
            continue
        local = q.last_ts
        if q.closed:
            kst = datetime(
                local.year, local.month, local.day, hour, minute, tzinfo=ZoneInfo(tz)
            ).astimezone(KST)
            note = f"· {label} {kst.strftime('%m/%d %H:%M')} 마감"
            if kst.date() != local.date():
                note += f" (현지 {local.month}/{local.day} 종가)"
        else:
            kst = local.astimezone(KST)
            note = (
                f"· {label} {kst.strftime('%m/%d %H:%M')} 현재가 "
                f"— 장중 (현지 {local.month}/{local.day})"
            )
        lines.append(f"<i>{note}</i>")

    live = sorted({CONTINUOUS[q.market] for q in quotes if q.market in CONTINUOUS})
    if live:
        lines.append(
            f"<i>· {'·'.join(live)}은 24시간 거래 — "
            f"{now.strftime('%m/%d %H:%M')} 조회 기준</i>"
        )
    lines.append("<i>· 고점은 52주 장중 최고가</i>")
    return "\n".join(lines)


# -------------------------------------------------------------- compact

def _render_compact(q, base_date, name_w=C_NAME_W):
    if not q.ok:
        return _pad(q.name, name_w) + _rjust("수집 실패", C_VALUE_W + C_CHANGE_W)

    line = (
        _pad(q.name, name_w)
        + _rjust(_fmt_value(q.last, q.fmt, compact=True), C_VALUE_W)
        + _rjust(_fmt_change(q), C_CHANGE_W)
        + _rjust(f"{q.change_pct:+.2f}%", C_PCT_W)
    )
    if base_date and q.date and q.date != base_date and not q.continuous:
        line += f" {q.date.month}/{q.date.day}"
    return line


def _timing_compact(quotes, now):
    """마감한 시장은 한 줄로 묶어 세 줄 안쪽으로."""
    seen = {}
    for q in quotes:
        if q.ok and q.last_ts and q.market in MARKETS:
            seen.setdefault(q.market, q)

    closed, live = [], []
    for key, (tz, hour, minute, label) in MARKETS.items():
        q = seen.get(key)
        if q is None:
            continue
        local = q.last_ts
        if q.closed:
            kst = datetime(
                local.year, local.month, local.day, hour, minute, tzinfo=ZoneInfo(tz)
            ).astimezone(KST)
            closed.append(f"{label} {_stamp(kst)}")
        else:
            live.append(
                f"{label} {_stamp(local.astimezone(KST))} 장중 "
                f"(현지 {local.month}/{local.day})"
            )

    lines = ["<i>🕘 기준 시각 (한국시간)</i>"]
    if closed:
        lines.append(f"<i>· {' · '.join(closed)} 마감</i>")
    for text in live:
        lines.append(f"<i>· {text}</i>")

    tail = []
    if any(q.market in CONTINUOUS for q in quotes):
        tail.append(f"24시간 시장은 {_stamp(now)} 조회")
    tail.append("지수 pt · 환율 원 · 원자재·코인 USD")
    lines.append(f"<i>· {' · '.join(tail)}</i>")
    return "\n".join(lines)


# ----------------------------------------------------------------- 공통

def _fmt_value(value, fmt, compact=False):
    if fmt == "rate":
        return f"{value:.2f}%"
    if compact and abs(value) >= 500:
        return f"{value:,.0f}"
    if abs(value) >= 10000:
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def _fmt_change(q):
    """변화량은 자릿수에 맞춰 정밀도를 줄인다. 금리는 bp."""
    if q.fmt == "rate":
        return f"{q.change * 100:+.1f}bp"
    delta = q.change
    if abs(delta) >= 100:
        return f"{delta:+,.0f}"
    if abs(delta) >= 10:
        return f"{delta:+,.1f}"
    return f"{delta:+,.2f}"


def _build_comments(quotes, alerts, compact=False):
    """임계값을 넘긴 지표만 한 줄로 짚어준다."""
    out = []
    big = alerts.get("big_move_pct", 2.0)
    rate_bp = alerts.get("rate_move_bp", 10.0)
    dd_warn = alerts.get("drawdown_warn_pct", -15.0)
    by_ticker = {q.ticker: q for q in quotes}

    movers = []
    for q in quotes:
        if not q.ok or q.change_pct is None:
            continue
        if q.fmt == "rate":
            if abs(q.change * 100) >= rate_bp:
                movers.append(q)
        elif abs(q.change_pct) >= big:
            movers.append(q)

    movers.sort(key=lambda q: abs(q.change_pct), reverse=True)
    moved = set()
    for q in movers:
        moved.add(q.ticker)
        arrow = "급등" if q.change_pct > 0 else "급락"
        # 한 줄 형태에서는 표에 전고점이 없으니 여기에 덧붙인다
        tail = ""
        if compact and q.watch_drawdown and q.drawdown_pct is not None:
            tail = f" (고점대비 {q.drawdown_pct:.1f}%)"
        out.append(
            f"• {q.name} {arrow} {_fmt_change(q)} ({q.change_pct:+.2f}%){tail}"
        )

    for q in quotes:
        if (not q.ok or q.drawdown_pct is None
                or not q.watch_drawdown or q.ticker in moved):
            continue
        if q.drawdown_pct >= -0.5:
            out.append(f"• {q.name} 52주 신고가 부근")
        elif q.drawdown_pct <= dd_warn:
            out.append(f"• {q.name} 고점 대비 {q.drawdown_pct:.1f}% — 조정 구간")

    vix = by_ticker.get("^VIX")
    vix_warn = alerts.get("vix_warn")
    if vix is not None and vix.ok and vix_warn and vix.last >= vix_warn:
        out.append(f"• VIX {vix.last:.1f} — 변동성 확대 구간")

    fx = by_ticker.get("USDKRW=X")
    fx_warn = alerts.get("usdkrw_warn")
    if fx is not None and fx.ok and fx_warn and fx.last >= fx_warn:
        out.append(f"• 원/달러 {fx.last:,.0f}원 — 고환율 구간")

    return out


def _stamp(dt):
    """8/19 05:00 — 앞자리 0을 떼되 플랫폼에 의존하지 않게 직접 만든다."""
    return f"{dt.month}/{dt.day} {dt.hour:02d}:{dt.minute:02d}"


# ----------------------------------------------------------------- 폭 계산

def _width(text):
    """한글·전각 문자는 2칸으로 세어 모노스페이스 표시폭을 구한다."""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in text)


def _pad(text, width):
    return text + " " * max(0, width - _width(text))


def _rjust(text, width):
    return " " * max(0, width - _width(text)) + text
