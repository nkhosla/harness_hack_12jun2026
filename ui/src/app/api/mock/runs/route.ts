import { NextResponse } from "next/server";

export async function POST() {
  return NextResponse.json({ run_id: "mock-run-001" });
}
