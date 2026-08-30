# 시장지표 알리미

매일 아침 8시, 국내외 증시·금리·원자재·코인 지표를 모아 텔레그램으로 보냅니다.

## 실행

```
run.bat                   평일에만 발송 (스케줄러가 이걸 호출)
run.bat --force           주말에도 강제 발송
run.bat --dry-run         발송 없이 콘솔로 미리보기
python setup_bot.py <토큰>  새 봇 연결
```

## 구성

| 파일 | 역할 |
|---|---|
| `config.json` | 봇 토큰, 지표 목록, 알림 임계값 |
| `src/market_data.py` | 시세 수집. fast_info·1시간봉·1년 일봉 3중 소스 |
| `src/message_builder.py` | 지표당 1줄 표(폭 31칸)·특이사항 렌더링 |
| `src/telegram_notifier.py` | 텔레그램 발송 |
| `setup_bot.py` | 새 봇 토큰/chat_id를 config.json에 연결 |

## 지표 추가·삭제

`config.json`의 `groups`를 고치면 됩니다. `ticker`는 야후 파이낸스 심볼입니다.

```json
{ "name": "테슬라", "ticker": "TSLA", "fmt": "num",
  "unit": "$", "market": "us", "watch_drawdown": true }
```

| 필드 | 뜻 |
|---|---|
| `fmt` | `num`(일반) 또는 `rate`(금리 — 등락을 bp로 표시) |
| `unit` | 값 뒤에 붙는 단위 (`pt`, `원`, `$`) |
| `market` | `kr`/`us`/`jp`/`cn`(정규장) 또는 `fx`/`futures`/`crypto`(24시간) |
| `watch_drawdown` | 전고점 대비 하락을 특이사항에 띄울지 |

## 데이터 소스 주의

야후의 **일봉 시계열은 최근 거래일이 하루 이틀 늦게 들어옵니다** (닛케이가 이틀
빠진 것을 확인). 그래서 시세는 `fast_info`(현재가·전일종가)를 주로 쓰고,
1시간봉으로 실제 체결 시각과 장중 여부를 판정하며, 1년 일봉은 52주 전고점
계산에만 씁니다. 일봉만 믿으면 며칠 지난 값이 발송됩니다.

## 표시 형태 바꾸기

`config.json`의 `options.layout`을 고칩니다.

- `detailed` — 지표당 두 줄. 단위와 52주 전고점까지 표에 표시 (기본)
- `compact` — 지표당 한 줄, 폭 31칸. 전고점은 특이사항에만

## 알림 임계값

`config.json`의 `alerts`에서 조정합니다.

- `big_move_pct` — 이 이상 움직이면 특이사항에 표시 (기본 2%)
- `rate_move_bp` — 금리가 이 이상 움직이면 표시 (기본 10bp)
- `vix_warn` — VIX가 이 값 이상이면 경고 (기본 20)
- `usdkrw_warn` — 원/달러가 이 값 이상이면 경고 (기본 1450원)
- `drawdown_warn_pct` — 전고점 대비 이만큼 밀리면 조정 구간 표시 (기본 -15%)

## 스케줄

**매일 08:00 KST(월~금) 발송.** 실행은 GitHub Actions
(`.github/workflows/daily-briefing.yml`)에서 이뤄지고, 시계는 두 겹입니다.

| | 트리거 | 시각 (UTC) | 역할 |
|---|---|---|---|
| 주 | Cloudflare Worker cron → `workflow_dispatch` | `0 23 * * 0-4` | 정시 발송 |
| 백업 | 저장소 `schedule` cron | `30 23 * * 0-4` | 주 트리거 실패 시에만 |

GitHub의 `schedule` cron은 정시 실행을 보장하지 않아 실측 26분~7시간까지 밀렸습니다.
그래서 정시성이 보장되는 Cloudflare Cron Trigger를 주 시계로 쓰고, 저장소 cron은
30분 뒤·비정각으로 물려 백업으로만 남겼습니다. 워크플로우 첫 스텝의 **중복 발송 가드**가
그날 이미 성공했거나 진행 중인 실행을 조회해, 백업이 겹쳐 돌면 스스로 건너뜁니다.

주 트리거의 설정·배포·점검은 [`trigger/README.md`](trigger/README.md)를 보세요.

수동 발송·시험은 Actions 탭의 **Run workflow**(`force` / `dry_run` 입력 지원) 또는:

```bash
gh workflow run daily-briefing.yml -f dry_run=true
```

로컬 Windows 작업 스케줄러 `시장지표알리미`는 **비활성화** 상태입니다(삭제하지 않음).
노트북 절전 상태에서 타이머가 깨우지 못해 오후에 "아침 브리핑"이 오던 문제 때문입니다.
되살리려면 `Enable-ScheduledTask -TaskName "시장지표알리미"`.
