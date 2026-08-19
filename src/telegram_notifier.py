# -*- coding: utf-8 -*-
"""텔레그램 봇으로 브리핑을 발송한다."""

import re

import requests

API_URL = "https://api.telegram.org/bot{token}/{method}"
MAX_LEN = 3800   # 텔레그램 상한 4096. 여유를 둔다


class TelegramNotifier:
    def __init__(self, config):
        tg = config.get("telegram", {})
        self.bot_token = tg.get("bot_token", "")
        self.chat_id = tg.get("chat_id", "")

    def is_configured(self):
        return bool(self.bot_token and self.chat_id and "여기에" not in self.bot_token)

    def send_message(self, text):
        if not self.is_configured():
            print("[텔레그램 미설정] 콘솔 출력:")
            print(strip_tags(text))
            return False

        if len(text) > MAX_LEN:
            text = text[:MAX_LEN] + "\n<i>…(생략)</i>"

        url = API_URL.format(token=self.bot_token, method="sendMessage")
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            resp = requests.post(url, json=payload, timeout=15)
            result = resp.json()
            if result.get("ok"):
                print("[텔레그램] 발송 성공")
                return True
            print(f"[텔레그램 오류] {result.get('description', '알 수 없는 오류')}")
            return False
        except requests.RequestException as e:
            print(f"[텔레그램 네트워크 오류] {e}")
            return False
        except ValueError:
            print("[텔레그램 오류] 응답을 해석할 수 없습니다.")
            return False


def strip_tags(text):
    return re.sub(r"<[^>]+>", "", text)
