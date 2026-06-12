"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useParams } from "next/navigation";
import { Renderer } from "@openuidev/react-lang";
import { streamRunUI } from "@/lib/api";
import { progressLibrary } from "@/lib/openui-library";

export default function RunPage() {
  const router = useRouter();
  const { run_id } = useParams<{ run_id: string }>();

  const [response, setResponse] = React.useState<string | null>(null);
  const [phase, setPhase] = React.useState<"running" | "done" | "failed">("running");

  React.useEffect(() => {
    const abort = new AbortController();

    streamRunUI(run_id, setResponse, abort.signal)
      .then(() => setPhase("done"))
      .catch((err) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setPhase("failed");
      });

    return () => abort.abort();
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

        {/* Agent-generated UI, streamed as OpenUI Lang and rendered progressively */}
        {response && (
          <div className="mb-12">
            <Renderer
              response={response}
              library={progressLibrary}
              isStreaming={phase === "running"}
            />
          </div>
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
