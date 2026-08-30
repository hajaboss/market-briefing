// 시장지표 브리핑의 주 트리거.
//
// GitHub Actions의 schedule cron은 정시 실행을 보장하지 않는다. 실측으로 상시 26~30분,
// 혼잡할 땐 5~8시간까지 밀렸다. 반면 workflow_dispatch는 호출 즉시 큐에 들어간다.
// 그래서 정시성이 보장되는 Cloudflare Cron Trigger가 매일 23:00 UTC(08:00 KST)에
// 이 워커를 깨워 workflow_dispatch를 직접 호출한다.
//
// 저장소의 schedule cron은 이 경로가 실패했을 때만 발송하는 백업으로 남겨 두었다.

const RETRIES = 3;

async function dispatch(env) {
  if (!env.GH_TOKEN) throw new Error("GH_TOKEN 시크릿이 설정되지 않았다.");

  const url = `https://api.github.com/repos/${env.REPO}/actions/workflows/${env.WORKFLOW}/dispatches`;
  let lastError;

  for (let attempt = 1; attempt <= RETRIES; attempt++) {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.GH_TOKEN}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "User-Agent": "market-briefing-trigger",
          "Content-Type": "application/json",
        },
        // force / dry_run 은 기본값(false)을 쓴다. 주말 skip 판정은 스크립트가 KST로 직접 한다.
        body: JSON.stringify({ ref: env.REF, inputs: {} }),
      });

      if (res.status === 204) {
        console.log(`[trigger] ${env.REPO} / ${env.WORKFLOW} 발화 성공 (시도 ${attempt})`);
        return;
      }

      lastError = new Error(
        `GitHub 응답 ${res.status}: ${(await res.text()).slice(0, 300)}`
      );
      // 4xx는 재시도해도 결과가 같다 — 토큰 만료·권한 부족·워크플로우 파일명 오류 등.
      if (res.status >= 400 && res.status < 500 && res.status !== 429) break;
    } catch (err) {
      lastError = err;
    }

    if (attempt < RETRIES) {
      await new Promise((resolve) => setTimeout(resolve, attempt * 2000));
    }
  }

  console.error(`[trigger] 발화 실패: ${lastError?.message}`);
  throw lastError;
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(dispatch(env));
  },

  // 상태 확인용. 여기서는 절대 발화하지 않는다 — 공개 URL이 곧 발송 버튼이 되면 안 된다.
  // 실제 발화를 시험하려면 `npx wrangler dev --test-scheduled` 후 /__scheduled 를 친다.
  async fetch(request, env) {
    return Response.json({
      역할: "시장지표 브리핑 주 트리거",
      대상: `${env.REPO} / ${env.WORKFLOW} @ ${env.REF}`,
      스케줄: "0 23 * * 0-4 (UTC) = 08:00 KST 월~금",
      토큰설정됨: Boolean(env.GH_TOKEN),
      안내: "이 엔드포인트는 발화하지 않는다. 발화는 Cron Trigger로만 일어난다.",
    });
  },
};
