"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useParams } from "next/navigation";
import { getRunStatus, getRunEvents } from "@/lib/api";
import type { ProgressEvent } from "@/lib/types";

const POLL_MS = 2000;

const STATUS_ICON: Record<ProgressEvent["status"], string> = {
  started: "○",
  tool_call: "→",
  done: "●",
  failed: "✕",
};

function agentLabel(agent: string): string {
  if (agent.startsWith("architect:")) return "Event Architect";
  if (agent === "scout") return "Scout";
  if (agent === "strategist") return "Strategist";
  return agent;
}

export default function RunPage() {
  const router = useRouter();
  const { run_id } = useParams<{ run_id: string }>();

  const [events, setEvents] = React.useState<ProgressEvent[]>([]);
  const [phase, setPhase] = React.useState<"running" | "done" | "failed">("running");

  React.useEffect(() => {
    let cancelled = false;
    let lastSeq = -1;

    async function poll() {
      try {
        const [status, newEvents] = await Promise.all([
          getRunStatus(run_id),
          getRunEvents(run_id, lastSeq),
        ]);
        if (cancelled) return;

        if (newEvents.length > 0) {
          lastSeq = newEvents[newEvents.length - 1].seq;
          setEvents((prev) => [...prev, ...newEvents]);
        }

        if (status.status === "done") {
          setPhase("done");
          return;
        }
        if (status.status === "failed") {
          setPhase("failed");
          return;
        }
      } catch {
        if (cancelled) return;
        setPhase("failed");
        return;
      }
      setTimeout(poll, POLL_MS);
    }

    poll();
    return () => {
      cancelled = true;
    };
  }, [run_id]);

  React.useEffect(() => {
    if (phase !== "done") return;
    const t = setTimeout(() => router.push(`/runs/${run_id}/slate`), 1200);
    return () => clearTimeout(t);
  }, [phase, run_id, router]);

  const pageTitle = phase === "done" ? "Slate ready" : "Creating slate…";

  return (
    <main className="min-h-screen px-6 py-16">
      <div className="max-w-page mx-auto">
        {/* Header */}
        <div className="mb-12">
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-2xl font-semibold text-ink tracking-heading">
              {pageTitle}
            </h1>
            {phase === "running" && (
              <span
                className="inline-block w-2 h-2 rounded-full bg-accent animate-pulse-dot"
                aria-hidden="true"
              />
            )}
          </div>
          <p className="text-ink-muted text-sm">
            {phase === "running"
              ? "Agents are scanning issues, checking weather, and ranking your best moves while creating your slate."
              : phase === "done"
              ? "Your slate is ready. Taking you there now…"
              : "Something went wrong."}
          </p>
        </div>

        {/* Live agent progress timeline */}
        {events.length > 0 && (
          <ol className="mb-12 space-y-3">
            {events.map((e) => (
              <li key={e.seq} className="flex items-baseline gap-3 text-sm">
                <span
                  className={e.status === "failed" ? "text-danger" : "text-accent"}
                  aria-hidden="true"
                >
                  {STATUS_ICON[e.status]}
                </span>
                <span className="font-medium text-ink shrink-0">
                  {agentLabel(e.agent)}
                </span>
                <span className="text-ink-muted">{e.detail}</span>
              </li>
            ))}
          </ol>
        )}

        {/* Failure state */}
        {phase === "failed" && (
          <div className="mt-8">
            <p className="text-danger text-sm mb-4">
              The agents encountered an error. Please try again.
            </p>
            <Link
              href="/"
              className="text-sm font-medium text-accent underline hover:no-underline focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas rounded outline-none"
            >
              ← Try again
            </Link>
          </div>
        )}
      </div>
    </main>
  );
}
