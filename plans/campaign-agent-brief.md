# Project Brief — Campaign Copilot

**Harness Engineering Hack · tokens& · June 12, 2026**

---

## One-line pitch

A cheap, proactive field organizer for budget-constrained local campaigns. Point it at a district; a team of coordinating agents reads what the community is talking about and proactively proposes the campaign's next moves — a ranked slate of community events, each tied to a live local issue, each with its own location, weather-aware format, target voters, and ready-to-run briefing.

## The problem (the pitch)

National campaigns hire pollsters, field directors, and comms staff. A local race for a state house seat runs on a handful of part-time volunteers and a five-figure budget. The work still has to get done — someone has to track what voters across the district care about this week, read the local news precinct by precinct, decide which events are worth running, check the weather before scheduling each one, and figure out where to spend scarce volunteer hours. Today that's a person, or it's nobody.

The wedge: a system of agents does the scan-and-propose layer for the price of API calls. It doesn't replace the candidate or the field team. It replaces the $60k field director the campaign can't afford — and crucially, it's *proactive*. It doesn't wait to be asked. It surfaces the next moves.

## What we're building (the hero deliverable)

**A proactive, multi-agent event-slate system for community outreach.**

Input: a district/region (a set of precincts or counties) + a time horizon (e.g. the next two weeks).
The agents do the rest — the user does **not** specify events. The system decides what events are worth running.

Output: a **ranked slate of proposed events**, each one generated from a real local issue, each with its own mini-briefing.

The flow:

1. The **Issue Scout** scans local signal (news + social) across the region and returns the top issues, each tagged to a precinct/county/area.
2. An **Event Architect** runs **per issue** — turning each issue into a proposed event with its own location, weather, target voters, and briefing.
3. The **Slate Strategist** ranks the events into the campaign's next moves (issue salience × turnout opportunity × feasibility).
4. The slate is presented: "here are your next 5 moves," each a card you can act on.

This is the differentiator: not one briefing for one event, but a proactive, prioritized set of recommended events — the engine for community outreach and relationship-building. Sentiment isn't a readout; it's the **generative seed**. A water-quality concern in Hillsborough and a school-funding fight in Caswell County aren't two facts on a dashboard — they're two different events, in two different places, with two different forecasts and two different audiences, each handled by its own Event Architect.

### The shared schemas (the contracts the agents pass between them)

These typed objects are the seams that let the team build in parallel. Define them first; everything else builds against them.

- **`Issue`** — what the Issue Scout emits. Fields: `title`, `area` (precinct/county), `summary`, `source_links`, `salience`.
- **`EventRecommendation`** — what each Event Architect emits. Fields:
  - `issue` — the driving issue (with source).
  - `area` — the precinct/county targeted.
  - `proposed_date` — the agent picks it.
  - `weather` — Jua forecast for that area/date, summarized.
  - `format` — indoor/outdoor, driven by the weather.
  - `venue_suggestion`.
  - `target_voters` — segment / soft precincts, from turnout data.
  - `talking_points` — 2–3, tied to the issue.
  - `rationale` — why this, why now.
  - `draft_outreach` *(stretch)* — ready-to-send text/email/social post.
- **`Slate`** — what the Slate Strategist emits. Fields: `region`, `horizon`, `ranked_events: list[EventRecommendation]`.

If the demo shows nothing else, it shows: *one region in → a ranked slate of proposed events out, each fully briefed, generated autonomously by coordinating agents.*

## The agents

| Agent | Input | Output | Tool budget |
|---|---|---|---|
| **Issue Scout** | region + signal sources | `list[Issue]`, ranked, tagged by area | News fetch / social fixture; one pass |
| **Event Architect** *(one instance per issue, run in parallel)* | one `Issue` | one `EventRecommendation` | **One** Jua call (its area) + **one** turnout query (its area). Hard timeout. No loops. |
| **Slate Strategist** | `list[EventRecommendation]` | ranked `Slate` | None (pure reasoning over the inputs) |
| **Orchestrator** | region + horizon | `Slate` | Wires Scout → fan-out Architects → Strategist; collects, handles failures, caches |

The Orchestrator is the agent story for the Guild.ai prize: it proactively decides what matters, spins up an Architect per issue, and assembles the moves. The Architects are bounded and self-contained — each owns its own tool calls so it's a clean module a teammate can build in isolation, but each is capped (one weather call, one turnout query, hard timeout) so it can't hang or loop on stage.

## Why multiple agents is the right hackathon architecture

This is a deliberate choice, and the reason is team velocity, not engineering elegance. At a one-day hack the bottleneck is human coordination across the team in ~6 hours, not token cost. Agent-as-module buys:

- **Parallel ownership.** Each agent has a typed contract. One person owns the Issue Scout, one (or two) owns the Event Architect, one owns the Slate Strategist + Orchestrator, one owns the UI. Everyone builds against **mocks** of the others — the Event Architect can be built against a fake `Issue` before the Scout exists. Nobody is blocked; nobody is editing the same prompt.
- **Clean failure isolation.** A bad weather call kills one event card, not the slate.
- **A stronger agents story.** Visibly coordinating agents reads as more agentic to judges than a lean pipeline — and the Guild.ai prize ($2,800) is literally "Most Innovative Use of Agents."

The honest tradeoff: this costs a few extra LLM calls and some latency versus a 2–3 call pipeline. On a build that runs once on stage, that's cents. We pay it for the parallelism and the prize fit.

## Scope discipline

**In scope (build today):**
- The four-agent flow end-to-end for ONE real region.
- Real Jua weather (per Event Architect / area), real precinct-level turnout, real local-news sentiment.
- Issue detection → per-issue event generation (parallel) → ranking.
- A dashboard that renders the ranked slate of event cards, clickable into each briefing.
- Region in, slate out — no manual data wrangling between agents during the demo.

**Out of scope (roadmap slide only):**
- Fundraising comms automation.
- Stakeholder influence-mapping (the "corner-store owner of 40 years" graph) — great vision beat, do not build.
- Multi-region / national scaling.
- Live social-media scraping at volume (see time-traps).

## Autonomy is 20% of the score — and the multi-agent flow is built for it

The rubric weights **Autonomy** at 20%: "How well does the agent act on real-time data without manual intervention?" After a single region input, the agents independently scan signal, detect issues, spin up an Architect per issue, pull live weather per location, query turnout per area, and rank the slate — no human stitching steps together. Make it *visible*: show the agents coordinating (Scout found 5 issues → Architect 1 pulling weather for Hillsborough → Architect 3 querying Caswell turnout → Strategist ranking), then the finished slate. This is the beat that wins this rubric.

## Data sources + realism notes

| Source | What we use it for | Reality check |
|---|---|---|
| **Voter file (CSV)** — turnout history, precinct, contact info | Per-event target voters, soft-precinct detection | **Do not display real PII on stage.** Aggregate to precinct level. Query it in-process (DuckDB/pandas) — no separate datastore. |
| **Weather (Jua)** | Per-event indoor/outdoor + scheduling | Core, and central — one call per Event Architect. Different places, different forecasts, different formats. Strong visible use of the API. |
| **Local sentiment** — local papers, social | Issue detection → the events themselves | The generative seed. See the trap below. |

### The social-media trap — read this before assigning it

Live TikTok / Facebook / Instagram scraping with geolocation filtering is a fragile, multi-hour fight against locked-down APIs. It will eat the day and may not work for the demo. **Recommended instead:**
- **Primary signal: local news.** Pull the region's local paper(s) / a news API via RSS or simple fetch. Reliable, has a location, easy for the Issue Scout to read and cluster by area.
- **Social: use a curated/seeded sample** for the demo, and architect ingestion so a live connector *could* drop in. Be honest in the pitch: social is a connector, not the magic.

This keeps issue detection real without betting the demo on a scraper.

## Architecture (high level — the coding plan turns this into tasks)

```
INPUT:  region (precincts/counties) + time horizon
   │
   ▼
ORCHESTRATOR  (Guild.ai)
   │
   ├─► ISSUE SCOUT ──────────────► list[Issue]   (news + social → issues by area)
   │
   ├─► fan out, one per issue, in parallel:
   │       EVENT ARCHITECT ──────► EventRecommendation
   │           ├─ Jua call (this area's weather)        [bounded: 1 call, timeout]
   │           ├─ turnout query (this area, in-process) [bounded: 1 query]
   │           └─ Claude: ideate event + write briefing
   │
   └─► SLATE STRATEGIST ─────────► Slate (ranked EventRecommendations)
                                       │
                                       ▼
                          RENDER  (OpenUI)  → ranked event cards → click into each briefing
                                       │
                                       ▼
                          DEPLOY  (Render)  → live URL
```

All agents speak the typed schemas (Pydantic); Claude fills `EventRecommendation` via structured output. (Plays directly to the team's PydanticAI background.) Cache Scout output and per-area weather/turnout so the on-stage run is fast and reproducible.

## Sponsor mapping — go deep on a core set, not wide

Tool Use is 20%, but quality of integration beats quantity. Nail the core; add optional ones only if ahead of schedule. (ClickHouse dropped for scope — turnout queries run in-process.)

**Core (the spine of the build):**

| Component | Sponsor | Why / prize |
|---|---|---|
| The agents — issue detection, event ideation, briefings, ranking | **Anthropic (Claude)** | The reasoning across all four agents; credibility |
| Per-event weather | **Jua** | Central — one call per Event Architect; drives format and scheduling |
| Multi-agent orchestration — Scout → fan-out Architects → Strategist | **Guild.ai** | The agents story; targets *Most Innovative Use of Agents* — $2,800 |
| Event-slate dashboard | **OpenUI** | The UI — $2,000 |
| Deploy | **Render** | Easy points — $2,000 credits |

**Optional (add if ahead of schedule):**

| Component | Sponsor | Note |
|---|---|---|
| Data ingestion pipelines | **Airbyte** | Fits voter CSV + news ingestion — $1,750 — only if setup is fast; else direct loaders |
| Push events out — draft outreach, add to calendar | **Composio** | Strong fit: each recommended event → calendar invite / outreach send — $200 |
| Inference credits | **Pioneer** | $500 + credits; low-effort to claim |

Realistic target: deep on 5 core sponsors → competitive for the general prize plus 2–3 sponsor tracks.

## Demo case — use a real region

Use a region you actually have data for. **NC HD-50 (Caswell + Orange counties, Cedar Grove/Hillsborough)** is the pick — official precinct-level turnout from the NC State Board of Elections (already in `data/turnout/`), multiple distinct areas (small-town Orange County + rural Caswell County, so the per-event weather/precinct variation is real, not contrived), and no connection to anyone's actual campaign work. All data is aggregate public election results — no voter file, no PII.

## The 3-minute demo script

1. **(0:00) The problem, in one breath.** "Local campaigns can't afford a field director. This proactively does that job for the cost of API calls."
2. **(0:20) One input.** Enter the region (Caswell + Orange) and a two-week horizon. Then step back — *you don't tell it what events to run.*
3. **(0:35) Watch the agents work.** Coordination scrolls: Scout finds the issues by area → an Architect spins up per issue, each pulling its own Jua weather and turnout → Strategist ranks. *This is the autonomy beat.*
4. **(1:20) The slate lands.** A ranked board of proposed events. Read two off it: "Hillsborough, water quality, rain forecast → indoor listening session at [venue], target these soft precincts. Caswell County, school funding, clear skies → outdoor rally at [park], target these voters." Same system, different place, different weather, different audience.
5. **(2:10) Click into one.** The full briefing — talking points, target segment, and the draft outreach it wrote. "A volunteer could send this in thirty seconds."
6. **(2:40) Roadmap in one line.** "These are next week's moves, ranked. The same agents will power fundraising, stakeholder mapping, and social — this is the first system."

## Risks / time-traps (assign owners)

- **Social scraping** — capped to news + seeded sample. Do not let anyone disappear into the TikTok API.
- **Agent loops / hangs on stage** — every Event Architect is bounded: one weather call, one turnout query, hard timeout, no retry loops. The Orchestrator must degrade gracefully (drop a failed event, keep the slate).
- **Demo determinism** — pin the news/social fixtures and cache Scout + per-area data so the slate is reproducible; keep the Jua calls live (reliable, the hero), but cache them after the first run so re-runs don't hang on N live calls.
- **PII on stage** — aggregate to precinct before anything renders. Decide this now, not at 4pm.
- **Mock-first or you'll block each other** — define the three schemas (`Issue`, `EventRecommendation`, `Slate`) in the first 30 minutes so every agent can be built against mocks in parallel. This is the whole reason to go multi-agent; don't waste it by building serially.
- **Over-scoping** — one region, one slate, built well. Resist adding the other three products.

---

### Next step

Turn this into a coding plan: per-agent task breakdown, owner assignments, the finalized schema definitions, mock fixtures to unblock parallel work, and a 90-minute checkpoint schedule for the day.
