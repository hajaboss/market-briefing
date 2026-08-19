# 시장지표 알리미 — GitHub Actions 이전 작업 인계

작성: 2026-08-19 (새벽)
상태: **로컬 준비 완료 / GitHub 업로드 전** — 아직 아무것도 외부로 나가지 않음

---

## 왜 옮기나

작업 스케줄러는 Windows가 켜져 있어야만 돈다. 이 PC(삼성 노트북) 실측 결과:

| 상황 | 08:00 발송 |
|---|---|
| 충전기 연결 + 절전 | 깨어나서 발송 (단 `WakeToRun` 켠 경우에만) |
| **배터리 + 절전** | **안 됨** — 전원 설정 `RTCWAKE`의 DC 값이 `사용 안 함`(0) |
| **완전 종료** | **안 됨** — 빠른 시작 활성 상태라 S5에선 어떤 타이머도 못 깨움 |

안 되는 경우 `StartWhenAvailable=True` 덕분에 나중에 PC를 켤 때 뒤늦게 실행된다.
→ 오후 3시에 "아침 브리핑"이 오는 셈이라 시의성이 깨진다.

노트북인 이상 `WakeToRun`은 "매일 밤 충전기를 꽂아둔다"는 사람의 습관에 의존하므로
반쪽짜리 해결책. 이 스크립트는 외부 API 조회 + 텔레그램 발송이 전부라
GitHub Actions로 옮기면 PC 상태와 완전히 무관해진다.

참고: 현재 등록된 작업 `시장지표알리미`는 아직 한 번도 실행된 적 없음
(`LastResult 267011` = 0x41303 "아직 실행 안 됨", 첫 예정이 8/19 08:00이었음).

---

## 오늘 끝낸 것 (전부 로컬)

### 1. 치명적 버그 수정 — 주말 판정 시간대

`src/main.py`가 `datetime.now()`(시간대 없음)로 요일을 봤다.
Actions 러너는 UTC이므로 그대로 옮기면:

- 월요일 08:00 KST = **일요일 23:00 UTC** → `weekday()=6` → **월요일 브리핑 영구 누락**
- 토요일 08:00 KST = 금요일 23:00 UTC → `weekday()=4` → **토요일에 발송됨**

즉 주말 판정이 정확히 하루씩 밀린다. `datetime.now(KST)`로 변경.
(`market_data.py` / `message_builder.py`는 원래 zoneinfo를 제대로 쓰고 있어 손대지 않음)

### 2. 자격증명 분리

`config.json`에 봇 토큰이 평문으로 박혀 있었다. 저장소에 올리면 안 되므로 분리.

우선순위: **환경변수 → `config.local.json` → `config.json`**

| 파일 | 내용 | 저장소 |
|---|---|---|
| `config.json` | 지표 구성 15개, telegram 값은 빈 문자열 | 커밋됨 |
| `config.local.json` | 실제 봇 토큰 + chat_id | **.gitignore** |
| GitHub Secrets | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Actions에서 환경변수로 주입 |

`config.local.json`은 최상위 키 단위로 얕은 병합(shallow merge)된다.

### 3. `setup_bot.py` 경로 변경

봇을 갈아끼울 때 토큰을 다시 `config.json`에 써넣어 비밀이 되살아나는 문제.
→ `config.local.json`에 쓰도록 변경 + "Secrets도 같이 갱신하라"는 안내 출력 추가.

### 4. 신규 파일

- `.gitignore` — `config.local.json`, `.env`, `__pycache__/` 등
- `.github/workflows/daily-briefing.yml`

### 5. 발송 실패 시 종료 코드

`main.py` 끝에서 텔레그램 발송 실패 시 `sys.exit(1)`.
Actions에서 빨간 X로 보여야 실패를 알아챌 수 있다.

---

## 워크플로우 요약

```yaml
on:
  schedule:
    - cron: '0 23 * * 0-4'   # UTC 일~목 23:00 = KST 월~금 08:00
  workflow_dispatch:          # 수동 실행 (force / dry_run 입력 지원)
```

- ubuntu-latest / Python 3.12 / pip 캐시
- `concurrency` 그룹으로 중복 실행 방지
- timeout 10분

**cron은 이중 방어 구조다.** 워크플로우가 월~금만 돌고,
스크립트도 KST 기준으로 주말을 한 번 더 거른다.

---

## 검증 결과

```
python src/main.py --dry-run --force
→ exit 0, 지표 15건 정상 수집·조립
```

커밋 대상 파일 전체를 봇 토큰 패턴(`[0-9]{8,12}:AA[\w-]{30,}`)과
chat_id 문자열로 훑어 **잔존 비밀 0건** 확인.

---

## 내일 할 일

### 결정해야 하는 것

1. **저장소 공개 범위**
   - 비공개(권장) — Actions 무료 한도 월 2,000분, 이 작업은 월 30분 수준이라 충분
   - 공개 — Actions 무제한이지만 코드와 지표 구성이 전부 노출
2. **`gh` CLI 설치 여부** — 현재 미설치 (`git`은 있음)
   - 설치하면 저장소 생성·푸시·Secrets 등록까지 자동
   - 안 하면 웹에서 빈 저장소를 만들고 URL을 주면 푸시만 진행, Secrets는 수동 등록

### 실행 순서

```bash
# 1) git 초기화 (아직 저장소 아님)
git init && git add -A && git commit -m "초기 커밋"
#    ※ git global user.name / user.email 미설정 상태 — 먼저 설정 필요

# 2) 저장소 생성 + 푸시
gh repo create <이름> --private --source=. --push

# 3) Secrets 등록  ← 이거 빠뜨리면 발송 실패
gh secret set TELEGRAM_BOT_TOKEN
gh secret set TELEGRAM_CHAT_ID
#    값은 config.local.json 에 있음

# 4) 수동 실행으로 검증
gh workflow run daily-briefing.yml -f dry_run=true    # 먼저 dry-run
gh workflow run daily-briefing.yml -f force=true      # 실제 발송
gh run watch
```

### 5) 로컬 작업 스케줄러 정리 ← **잊지 말 것**

Actions가 정상 동작하는 걸 확인한 뒤 로컬 작업을 꺼야 한다.
안 그러면 PC 켜져 있는 날에 **브리핑이 두 번 온다.**

```powershell
Disable-ScheduledTask -TaskName "시장지표알리미"
```

바로 지우지 말고 며칠 비활성만 해두고 지켜볼 것.

---

## 주의사항

- **GitHub cron은 정시 보장이 안 된다.** 혼잡 시간대엔 5~30분 지연이 흔하다.
  분 단위 정확도가 필요하면 Actions는 맞지 않는다. (아침 브리핑엔 무방)
- **무료 한도는 비공개 저장소에만 적용**되고 매달 초기화된다.
- 봇 토큰이 실수로 커밋되면 되돌리기 어렵다. BotFather에서 `/revoke`로
  즉시 폐기하고 새로 발급받는 게 유일하게 확실한 대처다.
- yfinance 일봉 지연 문제(메모리에 기록된 함정)는 이번 변경과 무관하며
  `fast_info` 기반 로직은 그대로 유지됨.

---

## 되돌리려면

아직 git 저장소가 아니라 커밋 이력이 없다. 원상복구하려면:

1. `config.local.json`의 telegram 값을 `config.json`에 다시 넣기
2. `.github/`, `.gitignore`, `config.local.json`, 이 문서 삭제
3. `src/main.py`의 `datetime.now(KST)` → `datetime.now()` (권장하지 않음, 로컬에선 무해)
