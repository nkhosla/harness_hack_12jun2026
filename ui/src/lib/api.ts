const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";
const MOCK_PREFIX = "/api/mock";

export async function postSlate(region: string, horizon: string): Promise<{ run_id: string }> {
  const url = BASE ? `${BASE}/slate` : `${MOCK_PREFIX}/runs`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ region, horizon }),
  });
  if (!res.ok) throw new Error(`Failed to start run: ${res.status}`);
  return res.json();
}

export async function getRunStatus(run_id: string) {
  const url = BASE
    ? `${BASE}/runs/${run_id}`
    : `${MOCK_PREFIX}/runs/${run_id}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Run not found: ${run_id}`);
  return res.json();
}

/**
 * Streams the run's progress UI as OpenUI Lang text. Calls onChunk with the
 * accumulated program text as each chunk arrives. Resolves when the stream ends.
 */
export async function streamRunUI(
  run_id: string,
  onChunk: (accumulated: string) => void,
  signal?: AbortSignal
): Promise<void> {
  const url = BASE
    ? `${BASE}/runs/${run_id}/ui-stream`
    : `${MOCK_PREFIX}/runs/${run_id}/stream`;
  const res = await fetch(url, { signal });
  if (!res.ok || !res.body) throw new Error(`Stream failed: ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let accumulated = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    accumulated += decoder.decode(value, { stream: true });
    onChunk(accumulated);
  }
}

export async function getRunEvents(run_id: string, since: number) {
  const url = BASE
    ? `${BASE}/runs/${run_id}/events?since=${since}`
    : `${MOCK_PREFIX}/runs/${run_id}/events?since=${since}`;
  const res = await fetch(url);
  if (!res.ok) return [];
  return res.json();
}

