"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getRunStatus } from "@/lib/api";
import type { EventRecommendation } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { staggerIn, slideInFromLeft, fadeUpIn } from "@/lib/animations";

function voterPriorityLabel(salience: number): string {
  if (salience >= 0.85) return "Top issue for voters in this area";
  if (salience >= 0.70) return "Strong concern among local voters";
  if (salience >= 0.55) return "Relevant to many local voters";
  return "Emerging issue in this area";
}

const WEATHER_ICON: Record<string, string> = {
  clear: "☀️",
  partly_cloudy: "⛅",
  rain: "🌧️",
  thunderstorms: "⛈️",
  hot_humid: "🌡️",
};

function formatDate(iso: string): string {
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

function rankLabel(idx: number) {
  return `#${idx + 1}`;
}

export default function IssueDetailPage() {
  const { run_id, issue_id } = useParams<{ run_id: string; issue_id: string }>();
  const [event, setEvent] = React.useState<EventRecommendation | null>(null);
  const [rank, setRank] = React.useState(0);
  const [error, setError] = React.useState("");
  const [copied, setCopied] = React.useState(false);
  const leftRef = React.useRef<HTMLDivElement>(null);
  const rightRef = React.useRef<HTMLDivElement>(null);
  const pointsRef = React.useRef<HTMLUListElement>(null);

  React.useEffect(() => {
    getRunStatus(run_id)
      .then((data) => {
        if (!data.slate) { setError("Slate not available."); return; }
        const idx = data.slate.ranked_events.findIndex(
          (e: EventRecommendation) => e.issue.id === issue_id
        );
        if (idx === -1) { setError("Event not found."); return; }
        setEvent(data.slate.ranked_events[idx]);
        setRank(idx);
      })
      .catch(() => setError("Could not load briefing."));
  }, [run_id, issue_id]);

  React.useEffect(() => {
    if (!event) return;
    if (leftRef.current) slideInFromLeft(leftRef.current);
    if (rightRef.current) fadeUpIn(rightRef.current, 0.1);
    if (pointsRef.current) {
      const items = pointsRef.current.querySelectorAll("li");
      staggerIn(items, 0.07);
    }
  }, [event]);

  async function handleCopy() {
    if (!event?.draft_outreach) return;
    await navigator.clipboard.writeText(event.draft_outreach);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  if (error) {
    return (
      <main className="min-h-screen flex items-center justify-center px-6">
        <div className="text-center">
          <p className="text-ink-muted mb-4">{error}</p>
          <Link href={`/runs/${run_id}/slate`} className="text-sm font-medium text-accent underline">
            ← Back to slate
          </Link>
        </div>
      </main>
    );
  }

  if (!event) {
    return (
      <main className="min-h-screen px-6 py-16">
        <div className="max-w-page mx-auto animate-pulse space-y-4">
          <div className="w-32 h-4 bg-gray-100 rounded" />
          <div className="w-64 h-8 bg-gray-100 rounded" />
          <div className="w-full h-48 bg-gray-100 rounded" />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-6 py-16">
      <div className="max-w-page mx-auto">
        {/* Back link */}
        <div className="mb-10">
          <Link
            href={`/runs/${run_id}/slate`}
            className="inline-flex items-center gap-1.5 text-sm text-ink-muted hover:text-ink transition-colors duration-150 group"
          >
            <span className="transition-transform duration-150 group-hover:-translate-x-0.5">←</span>
            <span>Back to slate</span>
          </Link>
        </div>

        {/* Two-column layout */}
        <div className="flex flex-col md:flex-row gap-10">
          {/* Left: metadata sidebar */}
          <div ref={leftRef} className="opacity-0 w-full md:w-2/5 space-y-6 shrink-0">
            <div className="bg-surface rounded-lg shadow-card p-6 space-y-5">
              {/* Rank + area */}
              <div className="flex items-center gap-2 flex-wrap">
                <Badge variant="rank">{rankLabel(rank)}</Badge>
                <Badge variant="area">{event.area}</Badge>
              </div>

              {/* Date */}
              <div>
                <p className="text-xs font-medium text-ink-muted uppercase tracking-wider mb-1">
                  Date
                </p>
                <p className="text-sm text-ink font-medium">{formatDate(event.proposed_date)}</p>
              </div>

              {/* Weather */}
              <div>
                <p className="text-xs font-medium text-ink-muted uppercase tracking-wider mb-1">
                  Weather
                </p>
                <div className="text-sm text-ink space-y-0.5">
                  <p>
                    {WEATHER_ICON[event.weather.condition] ?? "🌤️"}{" "}
                    {event.weather.condition.replace(/_/g, " ")} ·{" "}
                    {Math.round(event.weather.temp_f)}°F
                  </p>
                  <p className="text-ink-muted">
                    {Math.round(event.weather.precip_chance * 100)}% chance of precip
                  </p>
                  <p className="text-ink-muted capitalize">
                    Format: {event.format}
                  </p>
                </div>
              </div>

              {/* Venue */}
              <div>
                <p className="text-xs font-medium text-ink-muted uppercase tracking-wider mb-1">
                  Venue
                </p>
                <p className="text-sm text-ink">{event.venue_suggestion}</p>
              </div>

              {/* Target voters */}
              <div>
                <p className="text-xs font-medium text-ink-muted uppercase tracking-wider mb-1">
                  Target voters
                </p>
                <p className="text-sm text-ink leading-relaxed">{event.target_voters}</p>
              </div>

              {/* Voter priority */}
              <div>
                <p className="text-xs font-medium text-ink-muted uppercase tracking-wider mb-1">
                  Voter priority
                </p>
                <p className="text-sm font-medium text-accent">
                  {voterPriorityLabel(event.issue.salience)}
                </p>
              </div>
            </div>
          </div>

          {/* Right: content */}
          <div ref={rightRef} className="opacity-0 flex-1 space-y-8">
            {/* Issue title + summary */}
            <div>
              <h1 className="text-2xl font-semibold tracking-heading text-ink mb-3 leading-snug">
                {event.issue.title}
              </h1>
              <p className="text-ink-muted leading-relaxed text-sm">
                {event.issue.summary}
              </p>
              {event.issue.source_links.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {event.issue.source_links.map((link) => (
                    <li key={link}>
                      <a
                        href={link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-accent underline hover:no-underline focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 rounded outline-none"
                      >
                        {link}
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Talking points */}
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-muted mb-3">
                Talking points
              </h2>
              <ul ref={pointsRef} className="space-y-3">
                {event.talking_points.map((point, i) => (
                  <li key={i} className="opacity-0 flex gap-3 text-sm text-ink leading-relaxed">
                    <span className="text-accent font-semibold shrink-0 w-5 text-right">
                      {i + 1}.
                    </span>
                    <span>{point}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Rationale */}
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-muted mb-3">
                Rationale
              </h2>
              <p className="text-sm text-ink leading-relaxed">{event.rationale}</p>
            </div>

            {/* Draft outreach */}
            {event.draft_outreach && (
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
                    Draft outreach
                  </h2>
                  <button
                    onClick={handleCopy}
                    className="text-xs font-medium text-accent hover:text-accent/70 transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 rounded outline-none px-1"
                  >
                    {copied ? "Copied!" : "Copy to clipboard"}
                  </button>
                </div>
                <div className="bg-canvas border border-border rounded-lg p-4">
                  <pre className="text-sm text-ink leading-relaxed whitespace-pre-wrap font-sans">
                    {event.draft_outreach}
                  </pre>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
