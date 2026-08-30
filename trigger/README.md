# 브리핑 주 트리거 (Cloudflare Worker)

매일 **23:00 UTC = 08:00 KST**에 `hajaboss/market-briefing`의 `daily-briefing.yml`을
`workflow_dispatch`로 발화시키는 워커.

## 왜 이게 필요한가

GitHub Actions의 `schedule` cron은 정시 실행을 **보장하지 않는다**. 이 저장소의 실측:

| 목표 (KST) | 실제 발송 | 지연 |
|---|---|---|
| 8/20~8/26 08:00 | 08:26 ~ 08:30 | +26~30분 |
| 8/27 08:00 | 13:26 | +5시간 26분 |
| 8/28 08:00 | 15:49 | +7시간 49분 |

실행 자체는 30초면 끝난다. 밀린 건 **워크플로우가 큐에 등록된 시각**이다. 즉 스크립트가
느린 게 아니라 GitHub의 스케줄러가 이벤트를 늦게 쏜 것이다. 원인 둘:

1. cron이 정각(`0 23`)이라 전 세계에서 가장 혼잡한 슬롯에 걸린다.
2. 무료 공개 저장소의 schedule 이벤트는 우선순위가 가장 낮아, 혼잡하면 몇 시간까지
   밀리고 최악의 경우 그날을 통째로 건너뛴다.

반면 `workflow_dispatch`는 호출 즉시 큐에 들어가 1분 안에 실행된다. 그래서 정시성이
보장되는 Cloudflare Cron Trigger를 시계로 쓰고, 실행은 그대로 Actions에 맡긴다.
덤으로 **60일 무커밋 시 schedule이 자동 비활성화되는 문제**도 사라진다
(`workflow_dispatch`는 그 규칙의 대상이 아니다).

## 구성

- 주 경로: 이 워커 → `workflow_dispatch` → 08:00 KST 발송
- 백업 경로: 저장소의 `schedule` cron `30 23 * * 0-4` → 주 경로가 실패했을 때만 발송
  (워크플로우 첫 스텝의 **중복 발송 가드**가 오늘 성공/진행 중인 실행을 조회해 스스로 건너뛴다)

## 최초 설정 (1회)

### 1. GitHub 토큰 발급

<https://github.com/settings/personal-access-tokens/new> 에서 **fine-grained** 토큰:

- Resource owner: `hajaboss`
- Repository access: **Only select repositories** → `market-briefing`
- Permissions → Repository permissions → **Actions: Read and write**
- 만료일: 1년 (만료되면 트리거가 조용히 멈추니 캘린더에 적어 둘 것)

### 2. 배포

```bash
cd trigger
npx wrangler login          # 브라우저에서 Cloudflare 계정 인증
npx wrangler secret put GH_TOKEN   # 1에서 발급한 토큰을 붙여넣기
npx wrangler deploy
```

`secret put`은 배포된 워커가 있어야 하므로, 처음이라면 `deploy` → `secret put` →
`deploy` 순서로 한 번 더 돌려도 된다.

### 3. 확인

```bash
npx wrangler dev --test-scheduled
# 다른 터미널에서
curl "http://localhost:8787/__scheduled?cron=0+23+*+*+0-4"
```

`gh run list --workflow daily-briefing.yml --limit 3` 에 `workflow_dispatch` 실행이
새로 잡히면 성공이다. 배포 후 실제 발화 로그는 `npx wrangler tail`로 본다.

워커의 공개 URL(`GET /`)은 설정 상태만 보여 주고 **발화하지 않는다**. 공개 URL이 곧
발송 버튼이 되면 누구나 브리핑을 난사할 수 있기 때문이다.

## 고장났을 때

- 브리핑이 08:00이 아니라 **09:00 근처**에 온다 → 주 트리거가 죽고 백업 cron이 받은 것이다.
  `npx wrangler tail`로 워커 로그를, 토큰 만료 여부를 먼저 확인한다.
- 브리핑이 아예 안 온다 → 주·백업이 모두 실패. Actions 탭에서 실행 이력과 Secrets
  (`TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`)를 확인한다.
- 하루에 두 번 온다 → 중복 발송 가드가 동작하지 않은 것이다. 백업 실행 로그의
  "중복 발송 가드" 스텝 출력을 본다.
