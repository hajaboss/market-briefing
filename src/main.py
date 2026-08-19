# -*- coding: utf-8 -*-
"""매일 아침 시장 지표를 모아 텔레그램으로 보낸다.

사용법:
    python src/main.py            평일에만 발송
    python src/main.py --force    주말에도 발송
    python src/main.py --dry-run  발송하지 않고 콘솔에만 출력

텔레그램 자격증명은 환경변수 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID를 우선
사용하고, 없으면 config.local.json, 그다음 config.json에서 찾는다.
"""

import io
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from market_data import fetch_quotes
from message_builder import build_message
from telegram_notifier import TelegramNotifier, strip_tags

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.json")
LOCAL_CONFIG_PATH = os.path.join(ROOT, "config.local.json")
KST = ZoneInfo("Asia/Seoul")


def _read_json(path):
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"[오류] 설정 파일이 없습니다: {CONFIG_PATH}")
        sys.exit(1)
    config = _read_json(CONFIG_PATH)

    # 로컬 전용 값(토큰 등)을 덮어쓴다. 이 파일은 저장소에 올리지 않는다.
    if os.path.exists(LOCAL_CONFIG_PATH):
        for key, value in _read_json(LOCAL_CONFIG_PATH).items():
            if isinstance(value, dict) and isinstance(config.get(key), dict):
                config[key].update(value)
            else:
                config[key] = value

    # 환경변수가 최우선. GitHub Actions의 Secrets가 이 경로로 들어온다.
    tg = config.setdefault("telegram", {})
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        tg["bot_token"] = os.environ["TELEGRAM_BOT_TOKEN"]
    if os.environ.get("TELEGRAM_CHAT_ID"):
        tg["chat_id"] = os.environ["TELEGRAM_CHAT_ID"]

    return config


def main():
    force = "--force" in sys.argv
    dry_run = "--dry-run" in sys.argv

    config = load_config()
    options = config.get("options", {})

    # 실행 환경의 시간대와 무관하게 한국 날짜로 판정한다.
    # (GitHub Actions 러너는 UTC라 월요일 08:00 KST가 일요일로 잡힌다)
    if options.get("skip_weekend", True) and not force:
        if datetime.now(KST).weekday() >= 5:
            print("[건너뜀] 주말에는 발송하지 않습니다. (--force로 강제 발송)")
            return

    groups = config.get("groups", [])
    print(f"[수집] 지표 {sum(len(g.get('items', [])) for g in groups)}건 조회 중…")
    quotes = fetch_quotes(groups)

    ok = sum(1 for q in quotes if q.ok)
    print(f"[수집] 성공 {ok}건 / 전체 {len(quotes)}건")
    if ok == 0:
        print("[중단] 수집된 지표가 없어 발송하지 않습니다.")
        sys.exit(1)

    message = build_message(quotes, groups, config.get("alerts", {}),
                            layout=options.get("layout", "detailed"))

    if dry_run:
        print("\n" + strip_tags(message))
        return

    if not TelegramNotifier(config).send_message(message):
        sys.exit(1)


if __name__ == "__main__":
    main()
