"use client";

import * as React from "react";
import { CTAButton } from "@/components/ui/CTAButton";
import { fadeUpIn, staggerIn } from "@/lib/animations";

const FEATURES = [
  {
    num: "01",
    title: "Issue intelligence",
    desc: "Scans local news and community signal to surface the issues voters in each area care about most.",
  },
  {
    num: "02",
    title: "Weather-aware scheduling",
    desc: "Plans each event for an indoor or outdoor setting based on the local forecast.",
  },
  {
    num: "03",
    title: "Strategic ranking",
    desc: "Orders every event by voter concern and turnout opportunity, so your highest-impact move always comes first.",
  },
];

const STATS = [
  { number: "5", label: "events, ranked for your district" },
  { number: "2 wks", label: "planning horizon" },
  { number: "24/7", label: "working for your campaign" },
];

export default function Home() {
  const arm1LeftRef = React.useRef<HTMLDivElement>(null);
  const arm1RightRef = React.useRef<HTMLDivElement>(null);
  const statsRef = React.useRef<HTMLDivElement>(null);
  const barRightRef = React.useRef<HTMLDivElement>(null);
  const featuresRef = React.useRef<HTMLDivElement>(null);
  const arm2RightRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (arm1LeftRef.current) fadeUpIn(arm1LeftRef.current, 0);
    if (arm1RightRef.current) fadeUpIn(arm1RightRef.current, 0.1);
    if (statsRef.current) {
      const rows = statsRef.current.querySelectorAll("[data-stat]");
      staggerIn(rows, 0.08);
    }
    if (barRightRef.current) fadeUpIn(barRightRef.current, 0.15);
    if (featuresRef.current) {
      const items = featuresRef.current.querySelectorAll("[data-feature]");
      staggerIn(items, 0.07);
    }
    if (arm2RightRef.current) fadeUpIn(arm2RightRef.current, 0.2);
  }, []);

  return (
    <main className="bg-canvas min-h-screen cursor-default">

      {/* ── Z ARM 1 ─────────────────────────────────────────────── */}
      <section className="border-b border-border pt-16 pb-14 cursor-default">
        <div className="max-w-page mx-auto px-6 flex flex-col md:flex-row md:items-center md:justify-between gap-10">

          <div ref={arm1LeftRef} className="opacity-0 select-none">
            <h1 className="text-5xl md:text-7xl font-bold text-ink leading-none tracking-tight">
              Your AI<br />field director
            </h1>
            <p className="mt-5 text-lg text-ink-muted max-w-sm leading-relaxed">
              Your next five events ranked by what voters in your district
              actually care about.
            </p>
          </div>

          <div ref={arm1RightRef} className="opacity-0 flex-1 flex flex-col items-center gap-4">
            <CTAButton label="Create slate →" size="lg" />
          </div>

        </div>
      </section>

      {/* ── Z BAR (dark) ─────────────────────────────────────────── */}
      <section className="bg-ink py-20 cursor-default">
        <div className="max-w-page mx-auto px-6 flex flex-col md:flex-row md:items-center gap-16">

          <div ref={statsRef} className="md:w-2/5 space-y-8 select-none">
            {STATS.map((s) => (
              <div key={s.label} data-stat className="opacity-0">
                <p className="text-6xl font-bold text-white leading-none">{s.number}</p>
                <p className="mt-1 text-sm text-white/70 tracking-wide">{s.label}</p>
              </div>
            ))}
          </div>

          <div ref={barRightRef} className="opacity-0 flex-1 select-none">
            <h2 className="text-3xl md:text-4xl font-bold text-white leading-snug mb-6">
              A full field operation,<br />at a fraction of the cost.
            </h2>
            <p className="text-white/80 text-base leading-relaxed max-w-prose">
              Most local campaigns cannot afford a $60k field director. Cicero
              deploys a team of AI agents that scan the news your voters are
              reading, cross-check the weather, and hand you a ranked action
              plan in seconds.
            </p>
          </div>

        </div>
      </section>

      {/* ── Z ARM 2 ─────────────────────────────────────────────── */}
      <section className="border-t border-border pt-20 pb-28 cursor-default">
        <div className="max-w-page mx-auto px-6 flex flex-col md:flex-row md:items-end md:justify-between gap-14">

          <div ref={featuresRef} className="md:w-3/5 select-none">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink-muted mb-2">
              How it works
            </p>
            <div className="divide-y divide-border">
              {FEATURES.map((f) => (
                <div key={f.num} data-feature className="opacity-0 flex items-baseline gap-6 py-6">
                  <span className="text-sm font-semibold text-accent tabular-nums shrink-0">
                    {f.num}
                  </span>
                  <div>
                    <h3 className="text-lg font-semibold text-ink leading-snug">
                      {f.title}
                    </h3>
                    <p className="mt-1.5 text-sm text-ink-muted leading-relaxed max-w-prose">
                      {f.desc}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div ref={arm2RightRef} className="opacity-0 flex-1 flex flex-col items-center gap-4 md:self-center">
            <CTAButton label="Create slate →" size="lg" />
            <p className="text-xs text-ink-muted select-none">Demo mode. No account needed.</p>
          </div>

        </div>
      </section>

    </main>
  );
}
