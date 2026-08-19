# -*- coding: utf-8 -*-
"""새 텔레그램 봇을 config.local.json에 연결한다.

사용법:
    python setup_bot.py <봇토큰>

BotFather에서 받은 토큰을 넣으면 봇 이름을 확인하고, 최근 대화에서
chat_id를 찾아 config.local.json에 저장한 뒤 테스트 메시지를 보낸다.
자격증명 전용 파일이라 저장소에는 올라가지 않는다.
"""

import io
import json
import os
import sys

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(ROOT, "config.local.json")
API = "https://api.telegram.org/bot{token}/{method}"


def call(token, method):
    try:
        resp = requests.get(API.format(token=token, method=method), timeout=15)
        return resp.json()
    except requests.RequestException as e:
        print(f"[네트워크 오류] {e}")
        sys.exit(1)
    except ValueError:
        print("[오류] 텔레그램 응답을 해석할 수 없습니다.")
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    token = sys.argv[1].strip()

    info = call(token, "getMe")
    if not info.get("ok"):
        print(f"[오류] 토큰이 올바르지 않습니다: {info.get('description')}")
        sys.exit(1)
    bot = info["result"]
    print(f"[확인] 봇 이름: {bot.get('first_name')} (@{bot.get('username')})")

    updates = call(token, "getUpdates")
    chat_ids = []
    for u in updates.get("result", []):
        chat = (u.get("message") or u.get("channel_post") or {}).get("chat", {})
        if chat.get("id") and chat["id"] not in chat_ids:
            chat_ids.append(chat["id"])
            print(f"[발견] chat_id={chat['id']} ({chat.get('first_name') or chat.get('title', '')})")

    if not chat_ids:
        print()
        print("[대기] 아직 대화 기록이 없습니다.")
        print(f"  텔레그램에서 @{bot.get('username')} 을 찾아 /start 를 누른 뒤")
        print("  이 명령을 다시 실행하세요.")
        sys.exit(1)

    chat_id = str(chat_ids[0])

    config = {}
    if os.path.exists(CONFIG_PATH):
        with io.open(CONFIG_PATH, encoding="utf-8") as f:
            config = json.load(f)
    config["telegram"] = {"bot_token": token, "chat_id": chat_id}
    with io.open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(json.dumps(config, ensure_ascii=False, indent=4))
    print(f"[저장] config.local.json에 봇 토큰과 chat_id({chat_id})를 기록했습니다.")
    print("      GitHub Actions로도 보내려면 저장소 Secrets의")
    print("      TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 도 함께 갱신하세요.")

    resp = requests.post(
        API.format(token=token, method="sendMessage"),
        json={
            "chat_id": chat_id,
            "text": "✅ <b>시장지표 알리미</b> 연결 완료\n매일 아침 8시에 브리핑을 보내드립니다.",
            "parse_mode": "HTML",
        },
        timeout=15,
    ).json()
    print("[테스트] 발송 성공" if resp.get("ok") else f"[테스트] 실패: {resp.get('description')}")


if __name__ == "__main__":
    main()
