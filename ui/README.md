# Cicero — UI

A Next.js frontend for the Cicero hackathon project. Gives budget-constrained local campaigns a ranked slate of their next five community events, each tied to a real local issue.

## Stack

| Layer | Library |
|---|---|
| Framework | Next.js 15 (App Router) |
| Components | Base UI (`@base-ui/react`) — headless, accessible |
| Generative UI | OpenUI (`@openuidev/react-lang`) — streaming AI-rendered progress view |
| Styles | Tailwind CSS 3 |
| Animations | GSAP 3 |
| Language | TypeScript (strict) |

## Running locally

```bash
cd ui
npm install
npm run dev       # http://localhost:3000
```

No backend required — all routes fall back to mock mode automatically.

## Mock mode

When `NEXT_PUBLIC_API_URL` is unset, every API call hits a local Next.js route under `/api/mock`:

| Real endpoint | Mock route | Returns |
|---|---|---|
| `POST /slate` | `POST /api/mock/runs` | `{ run_id: "mock-run-001" }` |
| `GET /runs/{id}/ui-stream` | `GET /api/mock/runs/{id}/stream` | Chunked OpenUI Lang text |
| `GET /runs/{id}/events` | `GET /api/mock/runs/{id}/events` | Fixture `ProgressEvent[]` |
| `GET /runs/{id}` | `GET /api/mock/runs/{id}` | Slate from `slate.sample.json` |

To point at a live backend:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## OpenUI streaming (how the progress view works)

The agents don't just emit JSON — they generate their own progress UI as **OpenUI Lang**, a streaming-first language designed for AI output. The frontend renders it progressively as chunks arrive:

```
root = Timeline([e0, e1, ..., summary])
e0 = AgentEvent("Scout", "started", "Scanning local news and social signal for Florida HD-21")
e1 = AgentEvent("Scout", "tool_call", "Fetching RSS: gainesville.com, ocala.com")
...
summary = RunSummary("Slate finalized — 5 ranked events ready for Florida HD-21.")
```

The component vocabulary is defined in `src/lib/openui-library.tsx`. When the real backend is wired, Claude will generate this format directly from its `ProgressEvent` output using the library's system prompt.

## Project structure

```
src/
  app/
    page.tsx                          # / — generate slate form
    runs/[run_id]/
      page.tsx                        # /runs/[id] — streaming progress view (OpenUI)
      slate/
        page.tsx                      # /runs/[id]/slate — ranked event cards
        [issue_id]/page.tsx           # /runs/[id]/slate/[issue_id] — full briefing
    api/mock/                         # mock endpoints (no backend needed)
  components/ui/
    AnimatedCard.tsx                  # GSAP hover/focus animations
    Badge.tsx                         # rank, area, status pill variants
    FocusRing.tsx                     # GSAP focus ring wrapper
    StatusPill.tsx                    # ProgressEvent status → colored badge
  lib/
    animations.ts                     # GSAP presets (fadeUpIn, staggerIn, etc.)
    api.ts                            # fetch helpers + streamRunUI()
    openui-library.tsx                # OpenUI component vocabulary
    types.ts                          # Slate, EventRecommendation, ProgressEvent
    fixtures/
      slate.sample.json               # 5 realistic Florida HD-21 events
      progress-events.ts              # 24 mock ProgressEvents
```

## Design tokens

Defined in `tailwind.config.ts`:

| Token | Value | Use |
|---|---|---|
| `canvas` | `#F8F7F4` | Page background |
| `surface` | `#FFFFFF` | Cards |
| `ink` | `#1A1A2E` | Primary text |
| `ink-muted` | `#6B7280` | Secondary text |
| `accent` | `#2D6A4F` | Forest green — links, badges, bars |
| `accent-light` | `#D8F3DC` | Light green — area badges, success bg |
| `danger` | `#DC2626` | Error states |

## Build

```bash
npm run build        # production build
npm run type-check   # TypeScript check only
```
