# Plan: landing

**Goal:** Replace the region/horizon form with a Z-pattern landing page that advertises the project and launches directly into slate generation for NCHD-50 / next two weeks. No inputs. One CTA.

**Hardcoded constants (never ask the user):**
```ts
const REGION  = "NCHD-50";
const HORIZON = "next two weeks";
```

**Flow change:**
```
BEFORE: / (form) → /runs/[id] → /runs/[id]/slate → /runs/[id]/slate/[issue_id]
AFTER:  / (landing) → /runs/[id] → /runs/[id]/slate → /runs/[id]/slate/[issue_id]
```

The "← Generate another slate" link on the slate board already points to `/` — no change needed there.

---

## Z-pattern layout

The Z describes the eye's reading path across the page. Each arm is a full-width horizontal band.

```
┌──────────────────────────────────────────────────┐
│  CAMPAIGN COPILOT          [See your slate →]    │  ← Z arm 1 (top)
├──────────────────────────────────────────────────┤
│                                                  │
│   [Stat/visual block]   Your field director,     │  ← Z bar (diagonal)
│                         for the price of nothing.│
│                                                  │
├──────────────────────────────────────────────────┤
│  · Scans local news                              │
│  · Weather-aware scheduling    [See your slate →]│  ← Z arm 2 (bottom)
│  · Ranked by voter salience                      │
└──────────────────────────────────────────────────┘
```

On mobile all sections stack vertically, left-aligned.

---

## Copy

**Z arm 1 — top bar:**
- Left: wordmark "Campaign Copilot" (small caps, accent color)
- Right: CTA button "See your slate →" (accent bg, GSAP hover lift)

**Z bar — mid section:**
- Left (40%): a stat block — three numbers that land the value
  - `5` / "events, ranked"
  - `2 wks` / "planning horizon"
  - `$0` / "field staff required"
- Right (60%): headline + body
  - Headline: "Your field director, for the price of nothing."
  - Body: "Local campaigns can't afford a $60k field director. Campaign Copilot scans the news your voters are reading, cross-checks the weather, and hands you a ranked action plan — in seconds."

**Z arm 2 — bottom bar:**
- Left (60%): three feature pills / bullet lines
  - "Scans local news and social signal by area"
  - "Schedules around weather — indoor vs. outdoor"
  - "Ranks events by issue salience × turnout opportunity"
- Right (40%): secondary CTA block
  - District badge: "NCHD-50" (accent pill)
  - CTA button "See your slate →" (same as top-right)
  - Subtext: "Demo mode · No sign-up required"

---

## Tasks

---

### Task 1 — Hardcode the district constants and remove the form dependency

**Context:** `postSlate(region, horizon)` is currently called from the form's submit handler. Before building the landing page, make the constants available app-wide so any component can trigger a run without repeating the strings. No UI changes in this task.

**Acceptance Criteria:**
- `src/lib/constants.ts` exports `DEMO_REGION = "NCHD-50"` and `DEMO_HORIZON = "next two weeks"`
- `src/app/page.tsx` is cleared of all form state (`region`, `horizon`, `error`, `loading`, Field components, Base UI imports) — replaced with a placeholder `<main>` (single line) so the file compiles; the landing UI is built in Task 2
- The `Field` import from `@base-ui/react/field` is removed from `page.tsx` (it will not be needed)
- `npm run type-check` passes

**Verify:**
```bash
npm run type-check
# No errors
grep -r "e.g. NCHD-50" src/
# No matches — placeholder text is gone
```

---

### Task 2 — Build the Z-pattern landing page

**Context:** Replaces the placeholder from Task 1. Three horizontal sections forming the Z. The CTA in both Z-arm-1 and Z-arm-2 calls `postSlate(DEMO_REGION, DEMO_HORIZON)` directly, shows a brief loading state on the clicked button, then navigates to `/runs/[run_id]`. Only the clicked button enters loading state — not the whole page.

**Acceptance Criteria:**

**Structure:**
- The page is a single `<main>`, no nav bar, no footer
- Three sections separated by generous vertical whitespace (min 80px between sections, min 120px top padding)
- Max content width `1120px` (the `max-w-page` token), centered with `px-6` gutters
- On desktop (≥768px): Z-arm sections use `flex` with explicit left/right proportions; Z-bar uses `flex flex-row-reverse` to put the stat block on the left
- On mobile (<768px): all sections stack, full-width, top-to-bottom

**Z arm 1 (top):**
- Left: "Campaign Copilot" in small-caps accent label + one-line tagline "Ranked moves for local campaigns."
- Right: `<CTAButton>` (see below) labeled "See your slate →"
- Section padding: 48px top, 40px bottom

**Z bar (mid):**
- Left (40%): stat block — three rows of `[large number] / [label]`. Numbers: `5`, `2 wks`, `$0`. Labels: "events, ranked", "planning horizon", "field staff required". Numbers use a large font (48px+, `font-semibold`, `text-ink`); labels use `text-sm text-ink-muted`. Rows stagger in via `staggerIn` on mount.
- Right (60%): headline "Your field director, for the price of nothing." (`text-3xl font-semibold`) + body paragraph (from copy above). Both `fadeUpIn` on mount.
- Section padding: 80px top and bottom; subtle top and bottom `border-t border-border`

**Z arm 2 (bottom):**
- Left (60%): three feature lines, each with a small accent `·` prefix and `fadeUpIn` on mount (staggered)
- Right (40%): district badge (`<Badge variant="area">NCHD-50</Badge>`) + `<CTAButton>` labeled "See your slate →" + subtext "Demo mode · No sign-up required" in `text-xs text-ink-muted`
- Section padding: 80px top, 120px bottom

**CTAButton behavior:**
- Accent background, white text, rounded-md, `py-3.5 px-8`
- Hover: `cardHoverIn` (lift + shadow) via GSAP
- Keyboard focus: `focusRingIn` via GSAP
- On click: sets `isLoading = true` on that specific button instance only; calls `postSlate(DEMO_REGION, DEMO_HORIZON)`; on success navigates to `/runs/[run_id]`; on error shows `text-danger` message below the button and resets `isLoading`
- While loading: button text becomes "Starting…", button is `disabled`
- `CTAButton` is a self-contained component in `src/components/ui/CTAButton.tsx` — not a page-level component

**Animations on mount:**
- Z arm 1: left content `fadeUpIn(delay=0)`, right button `fadeUpIn(delay=0.08)`
- Z bar: stat rows `staggerIn(delay=0.08)`, headline `fadeUpIn(delay=0)`, body `fadeUpIn(delay=0.1)`
- Z arm 2: feature lines `staggerIn(delay=0.06)`, CTA block `fadeUpIn(delay=0.1)`

**Verify:**
```bash
npm run type-check
npm run build  # no errors
# Visit http://localhost:3000
# 1. Three sections visible with correct Z layout on desktop
# 2. Resize to <768px — sections stack vertically
# 3. Click "See your slate →" (top) — button shows "Starting…", then navigates to /runs/mock-run-001
# 4. Navigate back, click bottom CTA — same behavior
# 5. Tab through page — CTA buttons show animated focus rings
# 6. Hover CTA — visible lift animation
# 7. Stat rows animate in on load
```

---

## Task Order

```
1 (constants + clear form) → 2 (landing page)
```

Task 1 is a 5-minute cleanup. Task 2 is the full build. Keep them separate so the repo is never in a broken state between commits.

---

## Files changed

| File | Change |
|------|--------|
| `src/lib/constants.ts` | New — exports `DEMO_REGION`, `DEMO_HORIZON` |
| `src/app/page.tsx` | Replaced — Z-pattern landing |
| `src/components/ui/CTAButton.tsx` | New — self-contained CTA with loading state |
| `src/app/runs/[run_id]/slate/page.tsx` | No change needed — "← Generate another slate" already links to `/` |
