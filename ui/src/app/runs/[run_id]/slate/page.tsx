"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getRunStatus } from "@/lib/api";
import type { Slate } from "@/lib/types";
import { AnimatedCard } from "@/components/ui/AnimatedCard";
import { Badge } from "@/components/ui/Badge";
import { staggerIn } from "@/lib/animations";

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
  return d.toLocaleDateString("en-US", { month: "long", day: "numeric" });
}

function truncate(str: string, max: number): string {
  return str.length <= max ? str : str.slice(0, max).trimEnd() + "…";
}

function SkeletonCard() {
  return (
    <div className="bg-surface rounded-lg shadow-card p-6 animate-pulse">
      <div className="flex gap-3 mb-4">
        <div className="w-8 h-6 bg-gray-100 rounded-full" />
        <div className="w-48 h-6 bg-gray-100 rounded" />
      </div>
      <div className="w-24 h-4 bg-gray-100 rounded mb-4" />
      <div className="w-full h-2 bg-gray-100 rounded mb-6" />
      <div className="w-full h-4 bg-gray-100 rounded" />
    </div>
  );
}

export default function SlatePage() {
  const { run_id } = useParams<{ run_id: string }>();
  const [slate, setSlate] = React.useState<Slate | null>(null);
  const [error, setError] = React.useState("");
  const cardsRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    getRunStatus(run_id)
      .then((data) => {
        if (data.slate) setSlate(data.slate);
        else setError("Slate not ready yet.");
      })
      .catch(() => setError("Could not load slate."));
  }, [run_id]);

  React.useEffect(() => {
    if (!slate || !cardsRef.current) return;
    const cards = cardsRef.current.querySelectorAll("[data-card]");
    staggerIn(cards, 0.08);
  }, [slate]);

  return (
    <main className="min-h-screen px-6 py-16">
      <div className="max-w-page mx-auto">
        {/* Header */}
        <div className="mb-12">
          <h1 className="text-3xl font-semibold tracking-heading text-ink">
            {slate?.region ?? "Your slate"}
          </h1>
          {slate?.horizon && (
            <p className="text-ink-muted text-sm mt-1">{slate.horizon}</p>
          )}
        </div>

        {/* Error */}
        {error && (
          <p className="text-danger text-sm mb-8">{error}</p>
        )}

        {/* Cards */}
        <div ref={cardsRef} className="space-y-4">
          {!slate && !error
            ? Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)
            : slate?.ranked_events.map((event, i) => (
                <AnimatedCard
                  key={event.issue.id}
                  data-card
                  className="group opacity-0 p-6 cursor-pointer"
                  tabIndex={0}
                  onClick={() => {
                    window.location.href = `/runs/${run_id}/slate/${event.issue.id}`;
                  }}
                  onKeyDown={(e: React.KeyboardEvent<HTMLDivElement>) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      window.location.href = `/runs/${run_id}/slate/${event.issue.id}`;
                    }
                  }}
                  role="button"
                  aria-label={`View briefing for ${event.issue.title}`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-start gap-4">
                    {/* Rank + title */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2.5 mb-3 flex-wrap">
                        <Badge variant="rank">#{i + 1}</Badge>
                        <Badge variant="area">{event.area}</Badge>
                      </div>
                      <h2 className="text-lg font-semibold text-ink mb-2 leading-snug">
                        {event.issue.title}
                      </h2>

                      {/* Date + weather */}
                      <div className="flex items-center gap-2 text-sm text-ink-muted mb-4 flex-wrap">
                        <span>{formatDate(event.proposed_date)}</span>
                        <span className="text-border">·</span>
                        <span>
                          {WEATHER_ICON[event.weather.condition] ?? "🌤️"}{" "}
                          {event.weather.condition.replace("_", " ")} ·{" "}
                          {Math.round(event.weather.temp_f)}°F
                        </span>
                      </div>

                      {/* Voter priority */}
                      <div className="mb-4">
                        <span className="text-xs font-medium text-accent">
                          {voterPriorityLabel(event.issue.salience)}
                        </span>
                      </div>

                      {/* Talking point preview */}
                      <p className="text-sm text-ink-muted leading-relaxed">
                        {truncate(event.talking_points[0], 80)}
                      </p>
                    </div>

                    {/* Link */}
                    <div className="shrink-0 self-start sm:self-center">
                      <span className="text-sm font-medium text-accent whitespace-nowrap transition-colors duration-150 group-hover:text-ink group-focus:text-ink">
                        View full briefing →
                      </span>
                    </div>
                  </div>
                </AnimatedCard>
              ))}
        </div>

        {/* Footer link */}
        <div className="mt-16 pt-8 border-t border-border">
          <Link
            href="/"
            className="text-sm text-ink-muted hover:text-ink transition-colors duration-150"
          >
            ← Create another slate
          </Link>
        </div>
      </div>
    </main>
  );
}
