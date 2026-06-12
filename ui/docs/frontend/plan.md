# Frontend Plan: Campaign Copilot UI

**Stack:** Next.js 15 (App Router) · TypeScript · Tailwind CSS · OpenUI · Base UI · GSAP  
**Builds against:** `mocks/slate.sample.json` + REST contract below  
**Vibe:** Sophisticated, calmly-capable. Generous whitespace. Appeals to a budget-constrained local campaign — civic confidence without corporate gloss.  
**Animation rule:** Every hover and keyboard focus state has a noticeable GSAP or CSS animation. No silent state changes.

---

## REST Contract (build against this)

```
POST   /slate                            body: { region: string, horizon: string }
                                         → { run_id: string }

GET    /runs/{run_id}                    → { status: "pending"|"done"|"failed", slate?: Slate }

GET    /runs/{run_id}/events?since={n}   → ProgressEvent[]
```

**ProgressEvent shape:**
```ts
{ run_id: string, seq: number, agent: string,
  status: "started"|"tool_call"|"done"|"failed", detail: string }
```

**Slate shape (from `schemas/models.py`):**
```ts
Slate {
  region: string
  horizon: string
  ranked_events: EventRecommendation[]
}

EventRecommendation {
  issue: { id, title, area, summary, source_links, salience: 0-1 }
  area: string
  proposed_date: string          // ISO date
  weather: { summary, condition, temp_f, precip_chance, recommended_format }
  format: "indoor"|"outdoor"
  venue_suggestion: string
  target_voters: string
  talking_points: string[]
  rationale: string
  draft_outreach?: string
}
```

---

## Design System

**Palette:**
- Background: `#F8F7F4` (warm off-white)
- Surface: `#FFFFFF`
- Primary text: `#1A1A2E` (deep navy)
- Secondary text: `#6B7280`
- Accent: `#2D6A4F` (muted forest green — civic without being flag-wavy)
- Accent light: `#D8F3DC`
- Border: `#E5E7EB`
- Danger/failed: `#DC2626`

**Type:** Inter (Google Fonts). Headings tracked slightly wide. Body at 16px/1.6.

**Spacing:** 8px base unit. Cards and sections use 32-48px padding. Page max-width 1120px.

**Animation defaults (define as GSAP defaults and Tailwind utilities):**
- Card hover: `y: -4, boxShadow: elevated` over 200ms ease-out
- Focus ring: GSAP scale 1→1.02 + accent color outline, 150ms
- Entrance stagger: 60ms between siblings, y: +16→0, opacity 0→1

---

## Library Responsibilities

**OpenUI** (`@openuidev/react-lang`, from openui.com / thesysdev): the **generative UI streaming layer**. Agents emit OpenUI Lang text (a compact, streaming-first UI language); the frontend renders it progressively via `<Renderer>` as chunks arrive. Used for the progress view ("agents working") — the agents literally generate their own progress UI. The component vocabulary the agents may use is defined in `src/lib/openui-library.tsx` (`Timeline`, `AgentEvent`, `RunSummary`), each styled with Tailwind and animated with GSAP.

**Base UI** (`@base-ui/react`, renamed from `@base-ui-components/react`): the component library for everything the user interacts with directly — `Field`, `Input`, focus management. Chosen for its first-class accessibility guarantees. Styled with Tailwind.

**OpenUI Lang syntax note:** positional args only, mapped to props by Zod key order. Example:
```
root = Timeline([e0, e1, summary])
e0 = AgentEvent("Scout", "started", "Scanning local news")
summary = RunSummary("Slate finalized.")
```

**Streaming contract addition:** real backend exposes `GET /runs/{run_id}/ui-stream` returning chunked `text/plain` OpenUI Lang; mock mode serves `/api/mock/runs/[run_id]/stream`. The JSON `events` endpoint remains in the contract for non-UI consumers.

---

## Tasks

---

### Task 1 — Project Scaffold

**Context:** The `ui/` directory is empty (just `.gitkeep`). This task creates the runnable base. All subsequent tasks depend on it.

**Acceptance Criteria:**
- `npx next dev` starts without error on port 3000
- TypeScript strict mode is on
- Tailwind CSS is configured with the design token colors, fonts, and spacing above
- GSAP (gsap package) is installed
- `@openuidev/react-lang` + `zod` are installed (OpenUI generative UI runtime)
- `@base-ui/react` is installed (package was renamed from `@base-ui-components/react`)
- Path alias `@/` resolves to `src/`
- A mock API route `GET /api/mock/slate` returns `mocks/slate.sample.json` verbatim (copy the JSON into `src/lib/fixtures/slate.sample.json`)
- A mock API route `POST /api/mock/runs` returns `{ run_id: "mock-run-001" }` immediately
- A mock API route `GET /api/mock/runs/[run_id]/events` returns the full `mock_progress_events` sequence from the fixtures file as a JSON array
- `npm run build` passes with no type errors

**Verify:**
```bash
cd ui
npm run dev &
curl http://localhost:3000/api/mock/slate | jq '.ranked_events | length'
# expected: 5
curl -X POST http://localhost:3000/api/mock/runs | jq '.run_id'
# expected: "mock-run-001"
curl http://localhost:3000/api/mock/runs/mock-run-001/events | jq 'length'
# expected: >= 5
npm run build
```

---

### Task 2 — Design System & Animation Foundation

**Context:** Builds on Task 1. Establishes the shared visual language and GSAP utilities consumed by every subsequent component. No product functionality yet.

**Acceptance Criteria:**
- `src/lib/animations.ts` exports reusable GSAP tween presets: `fadeUpIn(el, delay?)`, `cardHoverIn(el)`, `cardHoverOut(el)`, `focusRingIn(el)`, `focusRingOut(el)`, `staggerIn(els, staggerDelay?)`
- `src/components/ui/FocusRing.tsx` wraps any child with a Base UI `FocusRing` that triggers `focusRingIn/Out` via GSAP on focus/blur
- `src/components/ui/AnimatedCard.tsx` composes an OpenUI card primitive, attaches `cardHoverIn/Out` on mouseenter/mouseleave and `focusRingIn/Out` via the Base UI `FocusRing`; receives `tabIndex` and forwards all other props
- `src/components/ui/Badge.tsx` wraps the OpenUI badge/pill primitive with Tailwind accent variants (`rank`, `area`, `status`)
- `src/components/ui/StatusPill.tsx` wraps the OpenUI badge primitive for ProgressEvent status values (`started`, `tool_call`, `done`, `failed`) with appropriate color mapping
- A Storybook or standalone `/design` route is NOT required — visual inspection via the living app is sufficient
- All animation functions are SSR-safe (GSAP is only initialized client-side via `useEffect` or `"use client"` guards)

**Verify:**
- Open `http://localhost:3000` and inspect that no GSAP-related console errors appear on load (SSR guard works)
- `npm run build` passes (TypeScript + no GSAP SSR crash)

---

### Task 3 — Generate Slate Form (Input View)

**Context:** This is the first screen the user sees. It collects `region` and `horizon`, submits to `POST /slate` (or mock), and navigates to the progress view with the returned `run_id`.

**Acceptance Criteria:**
- Route: `/` (root page)
- Layout: centered column, max-width 560px, generous vertical padding (min 120px top)
- Headline: "Campaign Copilot" in large tracked heading; sub-headline: "Your next five moves, ranked by what voters care about."
- Two inputs using Base UI `Field` + `Input` components (Base UI owns form fields — accessibility contract):
  - `region`: label "Region", placeholder "e.g. Florida HD-21", required
  - `horizon`: label "Planning horizon", placeholder "e.g. next two weeks", required
- Submit button labeled "Generate slate →"; accent background; hover triggers `cardHoverIn`; keyboard focus triggers `focusRingIn`
- On submit: calls `POST /slate` (real API URL from env var `NEXT_PUBLIC_API_URL`, fallback to `/api/mock` when unset); on success navigates to `/runs/[run_id]`
- Inline error state if the POST fails: a single sentence below the button, styled in danger color
- Both inputs show a focus animation (accent border color transitions over 150ms) on focus/blur
- Form entrance: `staggerIn` applied to headline, subhead, region field, horizon field, button — staggered on mount

**Verify:**
```bash
# With NEXT_PUBLIC_API_URL unset (mock mode):
# 1. Visit http://localhost:3000
# 2. Fill "Florida HD-21" and "next two weeks", click submit
# 3. Browser navigates to /runs/mock-run-001
# 4. Tab through all fields — each shows visible focus animation
# 5. Hover the button — visible lift animation
```

---

### Task 4 — Progress View ("Agents Working")

**Context:** Route `/runs/[run_id]`. Consumes `GET /runs/{run_id}/ui-stream` (mock: `/api/mock/runs/[run_id]/stream`) — a chunked stream of OpenUI Lang text generated by the agents — and renders it progressively via OpenUI's `<Renderer>`. This view is the "autonomy beat": the agents generate their own progress UI. It must feel alive without being frenetic.

**Acceptance Criteria:**
- Streams the endpoint via `streamRunUI()` in `src/lib/api.ts`, accumulating text and re-rendering `<Renderer response={text} library={progressLibrary} isStreaming>` on each chunk
- On stream end: phase becomes done; auto-navigates to `/runs/[run_id]/slate` after a 1.2s pause
- On stream error (network failure or 404): shows an error message with a "Try again" link back to `/`
- Component vocabulary (`src/lib/openui-library.tsx`): `Timeline` (root, `aria-live="polite"`), `AgentEvent` (agent, status, detail), `RunSummary` (completion banner)
- Each `AgentEvent` animates in via `fadeUpIn` on mount; rows show agent name (bold), `StatusPill`, and detail text
- Agent name groupings are visually distinct: Scout in blue, Architect instances in amber, Strategist in accent
- A pulsing "working" indicator (CSS animation, not GSAP) is shown while streaming; it disappears on done/failed
- The page title is "Generating slate…" while in progress, "Slate ready" on done

**Verify:**
```bash
# 1. Submit form → lands on /runs/mock-run-001
# 2. Watch events appear one by one with staggered entrance
# 3. After final Strategist "done" event, page waits ~1.2s then navigates to /runs/mock-run-001/slate
# 4. Simulate failure: visit /runs/unknown-id — page shows error + Try again link
```

---

### Task 5 — Slate Board (Ranked Event Cards)

**Context:** Route `/runs/[run_id]/slate`. Fetches `GET /runs/{run_id}` and renders the `ranked_events` array as a ranked board. This is the hero view.

**Acceptance Criteria:**
- Fetches the slate on mount; shows a minimal skeleton loader while fetching
- Page header: region name + horizon, left-aligned; right-aligned: subtle "Generated by Campaign Copilot" attribution
- Cards render in rank order using `AnimatedCard` (Task 2), which composes the OpenUI card primitive
- Each card shows:
  - `Badge` rank (`#1`–`#5`, accent variant) + Issue title (large, primary text)
  - `Badge` area tag (area variant, secondary text)
  - Proposed date (formatted: "June 17")
  - Weather line: temp + condition + format icon (indoor/outdoor)
  - Salience bar: a thin horizontal bar, width = salience %, accent fill, labeled "Issue salience"
  - First talking point as a preview line (truncated at 80 chars with ellipsis)
  - "View full briefing →" text link
- Card hover: `cardHoverIn` (lift + shadow)
- Card keyboard focus: `focusRingIn` (scale + outline)
- Card entrance: staggered `fadeUpIn` with 80ms delay between cards, triggered on mount
- Clicking a card or the "View full briefing →" link navigates to `/runs/[run_id]/slate/[issue_id]`
- "← Generate another slate" link at bottom navigates to `/`

**Verify:**
```bash
# 1. Navigate to /runs/mock-run-001/slate
# 2. 5 cards appear with staggered entrance animation
# 3. Hover each card — visible lift
# 4. Tab through cards — each shows visible focus ring animation
# 5. Salience bars differ in width across the 5 cards (values vary from 0.68 to 0.92)
# 6. Click card #1 — navigates to /runs/mock-run-001/slate/alachua-water-01 (or equivalent issue id)
```

---

### Task 6 — Event Detail View (Full Briefing)

**Context:** Route `/runs/[run_id]/slate/[issue_id]`. Full briefing panel for a single `EventRecommendation`. User arrives here from the slate board.

**Acceptance Criteria:**
- Fetches the parent slate, finds the matching event by `issue.id`
- If issue_id not found: 404-style message with link back to slate
- Layout: two-column on desktop (≥768px), single-column on mobile; each column is an OpenUI card surface
  - Left col (40%): metadata sidebar — `Badge` rank, `Badge` area, date, weather block, venue, target voters, salience bar
  - Right col (60%): issue summary, talking points list, rationale, draft outreach
- Weather block: shows temp, precip chance (as %), condition, and recommended format with an icon
- Talking points: numbered list, each item animates in via `fadeUpIn` stagger on mount
- Draft outreach: displayed in a styled `<pre>`-like box with a "Copy to clipboard" button; clicking it shows "Copied!" for 1.5s then reverts
- Source links: rendered as a compact list of external links (open in new tab) under the issue summary
- All interactive elements (copy button, source links) have hover + focus animations
- "← Back to slate" link at top-left; hover underline animates in via GSAP width transition
- Page entrance: left col slides in from left (x: -20→0), right col fades up — both on mount, 300ms

**Verify:**
```bash
# 1. From slate board, click any card
# 2. Two-column layout appears with entrance animation
# 3. Talking points stagger in
# 4. Click "Copy to clipboard" — shows "Copied!" confirmation, then reverts
# 5. Resize to mobile (<768px) — layout collapses to single column
# 6. Tab through all interactive elements — each has visible focus animation
# 7. Click "← Back to slate" — returns to slate board
```

---

### Task 7 — Responsive Polish & Accessibility Audit

**Context:** Final pass. Ensures the app is usable on mobile and meets WCAG AA minimums. No new features — only corrections discovered by testing.

**Acceptance Criteria:**
- All pages are usable at 375px viewport width (no horizontal scroll, no overlapping elements)
- Color contrast: all text meets WCAG AA (4.5:1 for body, 3:1 for large text) — verify with browser devtools
- All interactive elements are reachable by keyboard in logical tab order
- Focus is never trapped (unless in a modal, which this app doesn't use)
- All images/icons have `alt` text or `aria-hidden="true"` where decorative
- The salience bar has `aria-label="Issue salience X%"` or equivalent
- The progress view's pulsing indicator has `aria-live="polite"` so screen readers announce new events
- `npm run build` produces no TypeScript errors and no React warnings in the console

**Verify:**
```bash
npm run build
# 0 errors, 0 warnings

# Manual: open Chrome devtools → Lighthouse → Accessibility
# Target score: ≥ 90

# Manual: navigate entire app using only keyboard (Tab, Enter, Space, arrow keys)
# Every screen and interactive element reachable and operable
```

---

## Task Order

```
1 (scaffold) → 2 (design system) → 3 (form) → 4 (progress) → 5 (slate board) → 6 (detail) → 7 (polish)
```

Tasks 3–6 are sequential (each view builds on the previous navigation target). Task 7 runs last.

---

## Environment Variables

```
NEXT_PUBLIC_API_URL=          # unset = mock mode (/api/mock)
                              # set to http://localhost:8000 for local backend
                              # set to https://campaign-copilot.onrender.com for prod
```

---

## Mock Mode Behavior

When `NEXT_PUBLIC_API_URL` is unset:
- `POST /slate` → hits `/api/mock/runs` → returns `{ run_id: "mock-run-001" }`
- `GET /runs/[id]/ui-stream` → hits `/api/mock/runs/[id]/stream` → chunked OpenUI Lang text (~280ms/line, ~7s total)
- `GET /runs/[id]/events` → hits `/api/mock/runs/[id]/events` → fixture ProgressEvents as JSON (kept for contract parity)
- `GET /runs/[id]` → hits `/api/mock/runs/[id]` → returns slate from `slate.sample.json`

This means Tasks 3–6 are fully demoable without a running backend.
