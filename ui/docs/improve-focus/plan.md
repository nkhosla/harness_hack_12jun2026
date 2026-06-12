# Plan: improve-focus

**Goal:** Every keyboard-focusable element shows a noticeable, animated focus ring — no silent states.

**Current problems (from code audit):**
- `focusRingIn` only tweens `scale: 1.015` — not a visible ring, just a subtle wobble
- `globals.css` wipes `:focus-visible { outline: none }` globally — elements missed by GSAP show nothing
- `FocusRing` wrapper uses deprecated `React.cloneElement` and is never applied to any page element
- Form inputs use `focus:` (fires on mouse too), no GSAP animation
- Text links have no GSAP focus handler; `underlineIn/Out` was built but never wired
- GSAP lazy-loads async — first focus event can silently miss animation while module loads

**Design rule (from original spec):** every hover and keyboard focus action must have a noticeable animation. No silent state changes.

**Affected files:**
- `src/lib/animations.ts`
- `src/app/globals.css`
- `src/components/ui/FocusRing.tsx`
- `src/components/ui/AnimatedCard.tsx`
- `src/components/ui/AnimatedLink.tsx` (new)
- `src/app/page.tsx`
- `src/app/runs/[run_id]/page.tsx`
- `src/app/runs/[run_id]/slate/page.tsx`
- `src/app/runs/[run_id]/slate/[issue_id]/page.tsx`

---

## Task 1 — Fix the focus ring animation and pre-load GSAP

**Context:** `focusRingIn` currently tweens only `scale: 1.015`. There is no visible ring animation — the Tailwind `focus-visible:ring-2` class shows a static ring on focus, but it appears instantly with no animation. Fix the GSAP tween to animate the ring in (via `outline` or `box-shadow`) and pre-load GSAP eagerly so the first focus event always fires.

**Acceptance Criteria:**
- `focusRingIn(el)` tweens `boxShadow` from `0 0 0 0px transparent` to `0 0 0 3px #2D6A4F` (the accent color) plus `scale: 1.015`, over 150ms ease-out
- `focusRingOut(el)` tweens `boxShadow` back to `0 0 0 0px transparent` and `scale: 1`, over 150ms ease-out
- A `preloadGsap()` export calls `getGsap()` once eagerly; callers invoke it in a `useEffect` at mount time so the module is ready before any focus event
- The global `:focus-visible { outline: none }` in `globals.css` is replaced with a CSS fallback: `outline: 2px solid #2D6A4F; outline-offset: 3px` — this shows immediately if GSAP hasn't loaded yet; elements that have GSAP handlers add `outline-none` to suppress the CSS fallback
- `AnimatedCard` calls `preloadGsap()` on mount

**Verify:**
```bash
npm run type-check
# Open http://localhost:3000, tab to the submit button
# Focus ring should animate in with a glowing outline, not just a static ring
# Open devtools → disable JS → tab through page → fallback CSS ring should appear
```

---

## Task 2 — Apply GSAP focus animation to form elements and rewrite FocusRing

**Context:** Form inputs on `/` use `focus:ring-2` (CSS, fires on mouse too, no animation). The submit button has Tailwind `focus-visible:ring-2` but no GSAP handler. `FocusRing.tsx` uses deprecated `React.cloneElement` and is never used. Fix inputs and button on the home page, and rewrite `FocusRing` to a `forwardRef` wrapper so it can be applied without cloneElement.

**Acceptance Criteria:**
- Both `<input>` elements on `page.tsx` add `onFocus`/`onBlur` handlers that call `focusRingIn`/`focusRingOut` on their own ref; their CSS focus class changes from `focus:` to `focus-visible:` (keyboard-only)
- The submit button on `page.tsx` adds `onFocus`/`onBlur` GSAP handlers
- `FocusRing.tsx` is rewritten: instead of `cloneElement`, it renders a `<span>` (or `<div>`) wrapper that delegates keyboard events to its child via `onFocusCapture`/`onBlurCapture` and animates the wrapper element itself — no deprecated API
- `preloadGsap()` is called on mount in `page.tsx`
- The "Copy to clipboard" button in `[issue_id]/page.tsx` and the source links gain explicit `onFocus`/`onBlur` GSAP handlers

**Verify:**
```bash
npm run type-check
# Tab into the Region input — animated ring appears
# Click the Region input — no ring (mouse click, focus-visible only)
# Tab to submit button — animated ring appears
# Tab to Copy button in detail view — animated ring appears
```

---

## Task 3 — Animated underline for text links (AnimatedLink component)

**Context:** Several text links have hover `underline` via CSS but no animation. `underlineIn/Out` exist in `animations.ts` but are unused. The "← Back to slate", "← Generate another slate", and progress-view "← Try again" links should animate their underline on both hover and keyboard focus.

**Acceptance Criteria:**
- `src/components/ui/AnimatedLink.tsx` is a new `<a>` wrapper (accepts all anchor props + optional `className`):
  - Renders the text with a pseudo-underline: `background-image: linear-gradient(currentColor, currentColor)` at `backgroundSize: "0% 1px"`, positioned at the bottom
  - On mouseenter/focus: calls `underlineIn(ref.current)` (expands to `100% 1px` over 200ms)
  - On mouseleave/blur: calls `underlineOut(ref.current)` (shrinks to `0% 1px` over 200ms)
  - Also calls `focusRingIn`/`focusRingOut` on focus/blur for the scale + box-shadow ring
  - Calls `preloadGsap()` on mount
- `AnimatedLink` replaces the back/try-again links in:
  - `src/app/runs/[run_id]/page.tsx` — "← Try again"
  - `src/app/runs/[run_id]/slate/page.tsx` — "← Generate another slate"
  - `src/app/runs/[run_id]/slate/[issue_id]/page.tsx` — "← Back to slate"
- The "View full briefing →" span inside `AnimatedCard` gains a matching animated underline on card focus (driven by the card's existing `onFocus` handler, not a separate `AnimatedLink`)
- Source links in the detail view use `AnimatedLink`
- The `Next.js` `<Link>` wrapper for navigation links passes the `href` through; `AnimatedLink` uses `<a>` directly and handles navigation via `href` prop

**Verify:**
```bash
npm run type-check
npm run build  # no errors
# http://localhost:3000/runs/mock-run-001/slate/issue-water-001
# Hover "← Back to slate" — underline animates in from left
# Tab to "← Back to slate" — animated ring + underline appears
# Source links: hover animates underline in
# http://localhost:3000/runs/mock-run-001/slate
# Hover "← Generate another slate" — underline animates in
```

---

## Task Order

```
1 (fix animation + pre-load) → 2 (form elements + FocusRing rewrite) → 3 (AnimatedLink)
```

Task 1 must land first — Tasks 2 and 3 depend on the corrected `focusRingIn/Out` and `preloadGsap`.

---

## CSS fallback strategy

Remove the blanket `:focus-visible { outline: none }` from `globals.css`. Replace with:

```css
:focus-visible {
  outline: 2px solid #2D6A4F;
  outline-offset: 3px;
}
```

Elements that have GSAP handlers add `outline-none` to their className to suppress the CSS version. This ensures that if GSAP fails (slow network, no-JS, SSR hydration gap), the user still sees a ring.
