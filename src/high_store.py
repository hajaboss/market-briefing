"""52주 고점을 위한 일봉 고가 누적 저장소.

야후는 요청하는 IP에 따라 같은 티커의 시계열을 1건만 돌려주기도 한다.
GitHub 러너에서 `^KS200`이 당일 1건만 와서 "52주 고점 = 당일 장중가"가
됐던 사고가 그 예다. 재시도·다른 호출 방식·`info` 전부 같은 값을 주므로
그 순간의 응답만으로는 방어가 안 된다.

그래서 한 번이라도 온전히 받아본 일봉 고가를 저장소에 쌓아두고,
매 실행마다 새로 받은 것을 합쳐 52주 창으로 잘라 최고가를 구한다.
잘린 응답이 와도 그날치 한 건이 더해질 뿐, 과거는 남아 있다.
"""

import json
import os
from datetime import date, timedelta

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "highs.json")

WINDOW_DAYS = 371        # 52주 + 여유 한 주


def load(path=PATH):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save(store, path=PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=0, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def merge(store, ticker, series):
    """새로 받은 {날짜: 고가}를 합친다. 값이 다르면 큰 쪽을 남긴다."""
    bucket = store.setdefault(ticker, {})
    for day, value in series.items():
        key = day.isoformat() if hasattr(day, "isoformat") else str(day)[:10]
        old = bucket.get(key)
        if old is None or value > old:
            bucket[key] = round(float(value), 4)


def prune(store, today=None):
    """52주 창 밖으로 나간 날짜를 버린다. 안 버리면 고점이 영영 안 내려온다."""
    cutoff = ((today or date.today()) - timedelta(days=WINDOW_DAYS)).isoformat()
    for ticker, bucket in store.items():
        for key in [k for k in bucket if k < cutoff]:
            del bucket[key]


def peak(store, ticker):
    """(고가, 날짜, 건수). 저장된 게 없으면 (None, None, 0)."""
    bucket = store.get(ticker) or {}
    if not bucket:
        return None, None, 0
    key = max(bucket, key=bucket.get)
    return bucket[key], date.fromisoformat(key), len(bucket)
