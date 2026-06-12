import { NextResponse } from "next/server";
import slateFixture from "@/lib/fixtures/slate.sample.json";

export function GET(
  _req: Request,
  { params }: { params: Promise<{ run_id: string }> }
) {
  return params.then(({ run_id }) => {
    if (run_id !== "mock-run-001") {
      return NextResponse.json(
        { status: "failed", error: "Run not found" },
        { status: 404 }
      );
    }
    return NextResponse.json({ status: "done", slate: slateFixture });
  });
}
