# 시장지표 알리미 — GitHub Actions 이전 작업 인계

작성: 2026-08-19 (새벽) / 완료: 2026-08-20
상태: **이전 완료.** GitHub Actions에서 매일 08:00 KST 발송 중

| 항목 | 값 |
|---|---|
| 저장소 | https://github.com/hajaboss/market-briefing (공개) |
| 계정 | `hajaboss` |
| Secrets | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 등록됨 |
| 검증 | dry-run 성공 → 실제 발송 성공 (지표 18/18 수집) |
| 로컬 작업 스케줄러 | **비활성화됨** (중복 발송 방지) |

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

## 이전 실행 기록 (2026-08-20 완료)

| 단계 | 결과 |
|---|---|
| 저장소 공개 범위 | **공개** 선택 (Actions 시간 무제한) |
| gh CLI | winget으로 2.97.0 설치, `repo`+`workflow` 스코프로 인증 |
| git 초기화·커밋 | `c4f1eb6` 초기 커밋, 12개 파일 |
| 저장소 생성·푸시 | `gh repo create market-briefing --public --source=. --push` |
| Secrets 등록 | `config.local.json`에서 값을 읽어 stdin으로 주입 |
| dry-run 검증 | 성공 |
| 실제 발송 | 성공 — 지표 18/18, 텔레그램 도착 확인 |
| 로컬 작업 비활성화 | `Disable-ScheduledTask` 완료 (삭제는 안 함) |

### 함정 — `gh secret set --body -` ★

stdin에서 값을 읽히려고 `--body -`를 썼는데, gh는 이걸 **stdin 표시가 아니라
리터럴 문자열 `-`** 로 받아 Secret 값이 `-` 한 글자가 됐다.

발송을 안 하는 dry-run이라 **성공으로 통과했고**, 로그의 모든 하이픈이 `***`로
마스킹된 것(`setup***python`, `***6.41%`)만이 유일한 단서였다.
GitHub이 Secret 값을 로그에서 가리기 때문에 벌어진 현상.

올바른 방법은 `--body`를 아예 빼는 것:

```bash
python -c "..." | gh secret set TELEGRAM_BOT_TOKEN
```

교훈 두 가지:
- **dry-run 성공은 자격증명이 맞다는 증거가 아니다.** 실제 발송까지 해봐야 안다.
- 로그에 `***`가 예상 밖의 위치에 나오면 Secret 값이 잘못 들어갔다는 신호다.

## 주의사항

- **GitHub cron은 정시 보장이 안 된다.** 혼잡 시간대엔 5~30분 지연이 흔하다.
  분 단위 정확도가 필요하면 Actions는 맞지 않는다. (아침 브리핑엔 무방)
- **무료 한도는 비공개 저장소에만 적용**되고 매달 초기화된다. 이 저장소는 공개라 무제한.
- **공개 저장소도 60일간 커밋이 없으면 스케줄 cron이 자동 비활성화된다.**
  GitHub이 메일로 알려주며, Actions 탭에서 "Enable workflow"를 누르면 되살아난다.
  지표를 가끔 손보면 자연히 갱신되지만, 두 달 넘게 안 건드리면 조용히 멈출 수 있다.
- 봇 토큰이 실수로 커밋되면 되돌리기 어렵다. BotFather에서 `/revoke`로
  즉시 폐기하고 새로 발급받는 게 유일하게 확실한 대처다.
- yfinance 일봉 지연 문제(메모리에 기록된 함정)는 이번 변경과 무관하며
  `fast_info` 기반 로직은 그대로 유지됨.

---

## 되돌리려면

Actions를 멈추고 로컬로 돌아가려면:

```bash
gh workflow disable daily-briefing.yml          # Actions 스케줄 중지
```
```powershell
Enable-ScheduledTask -TaskName "시장지표알리미"   # 로컬 작업 재개
```

로컬 작업은 지우지 않고 비활성화만 해뒀으므로 바로 되살릴 수 있다.
단 로컬은 PC가 켜져 있어야만 도는 원래의 한계가 그대로다.
