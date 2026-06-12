import { NextResponse } from "next/server";
import slateFixture from "@/lib/fixtures/slate.sample.json";

export function GET() {
  return NextResponse.json(slateFixture);
}
