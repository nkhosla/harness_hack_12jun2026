import { MOCK_PROGRESS_EVENTS } from "@/lib/fixtures/progress-events";

export const dynamic = "force-dynamic";

// Builds the OpenUI Lang program the agents would generate:
//   root = Timeline([e0, e1, ..., summary])
//   e0 = AgentEvent("Scout", "started", "...")
//   ...
//   summary = RunSummary("Slate finalized ...")
function buildLangLines(): string[] {
  const ids = MOCK_PROGRESS_EVENTS.map((e) => `e${e.seq}`);
  const lines = [`root = Timeline([${[...ids, "summary"].join(", ")}])`];
  for (const e of MOCK_PROGRESS_EVENTS) {
    const detail = e.detail.replace(/"/g, '\\"');
    lines.push(`e${e.seq} = AgentEvent("${e.agent}", "${e.status}", "${detail}")`);
  }
  lines.push(
    `summary = RunSummary("Slate finalized — 5 ranked events ready for Florida HD-21.")`
  );
  return lines;
}

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ run_id: string }> }
) {
  const { run_id } = await params;
  if (run_id !== "mock-run-001") {
    return new Response("Run not found", { status: 404 });
  }

  const lines = buildLangLines();
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      for (const line of lines) {
        controller.enqueue(encoder.encode(line + "\n"));
        await new Promise((r) => setTimeout(r, 280));
      }
      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
    },
  });
}
