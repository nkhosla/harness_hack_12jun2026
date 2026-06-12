import { NextRequest, NextResponse } from "next/server";
import { MOCK_PROGRESS_EVENTS } from "@/lib/fixtures/progress-events";

export function GET(
  req: NextRequest,
  { params }: { params: Promise<{ run_id: string }> }
) {
  const since = Number(req.nextUrl.searchParams.get("since") ?? "-1");
  return params.then(({ run_id }) => {
    if (run_id !== "mock-run-001") {
      return NextResponse.json([], { status: 200 });
    }
    const events = MOCK_PROGRESS_EVENTS.filter((e) => e.seq > since);
    return NextResponse.json(events);
  });
}
