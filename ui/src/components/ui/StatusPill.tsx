import * as React from "react";
import { Badge } from "./Badge";
import type { ProgressEvent } from "@/lib/types";

const statusLabel: Record<ProgressEvent["status"], string> = {
  started: "started",
  tool_call: "tool call",
  done: "done",
  failed: "failed",
};

const statusVariant = {
  started: "status-started",
  tool_call: "status-tool",
  done: "status-done",
  failed: "status-failed",
} as const;

interface StatusPillProps {
  status: ProgressEvent["status"];
}

export function StatusPill({ status }: StatusPillProps) {
  return (
    <Badge variant={statusVariant[status]}>{statusLabel[status]}</Badge>
  );
}
