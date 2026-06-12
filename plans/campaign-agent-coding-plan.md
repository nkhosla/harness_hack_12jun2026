# Coding Plan — Campaign Copilot

**Harness Engineering Hack · June 12, 2026 · companion to the project brief**

---

## How to use this plan

- **Contracts first, then parallel.** One 30-minute foundation step (WS-0) defines the shared schemas and mock fixtures. After that, every workstream builds **against mocks**, in parallel, with no cross-blocking.
- **Atomic tasks.** Each task below is self-contained: it has an Input, an Output, a "Done when," and the file(s) it touches. You can paste a single task into a coding agent and it should not need the rest of this plan — only the `schemas/` and `mocks/` modules, which live in the repo from minute 30.
- **Hard file boundaries.** Each workstream owns its own directory/files. Two coding agents working at once never edit the same file. This is what makes parallel agent work safe.
- **UI is fully decoupled** (WS-UI). It owns `ui/` and builds against the `Slate` JSON fixture + the REST contract. It never waits on the backend.
- **Don't let an unfamiliar sponsor SDK block the critical path.** Build agents as plain async functions / PydanticAI agents first. Wrapping them in Guild.ai for the orchestration prize is a separate integration task, not a dependency.

## Repo layout (the boundaries)

```
campaign-copilot/
├── schemas/            # WS-0  — Pydantic contracts (the seams)
│   └── models.py
├── mocks/              # WS-0  — canned objects + JSON fixtures
│   ├── fixtures.py
│   └── slate.sample.json
├── agents/
│   ├── scout.py        # WS-1  — Issue Scout
│   ├── architect.py    # WS-3  — Event Architect
│   └── strategist.py   # WS-4  — Slate Strategist
├── tools/
│   ├── weather.py      # WS-2  — Jua client
│   └── turnout.py      # WS-2  — voter CSV query
├── orchestrator.py     # WS-4  — wires Scout → Architects → Strategist
├── api.py              # WS-4  — POST /slate endpoint
├── ui/                 # WS-UI — owned entirely by the UI teammate
├── data/               # sample (scrubbed) voter CSV, news/social fixtures
├── render.yaml         # WS-DEPLOY
└── pyproject.toml
```

## The contracts (define these in WS-0; everything builds against them)

```python
# schemas/models.py
class Weather(BaseModel):
    summary: str
    condition: str
    temp_f: float
    precip_chance: float
    recommended_format: Literal["indoor", "outdoor"]

class TurnoutSummary(BaseModel):     # aggregated — NO PII
    area: str
    soft_precincts: list[str]
    target_segments: list[str]
    notes: str

class Issue(BaseModel):
    id: str
    title: str
    area: str                        # precinct / county
    summary: str
    source_links: list[str]
    salience: float                  # 0–1

class EventRecommendation(BaseModel):
    issue: Issue
    area: str
    proposed_date: date
    weather: Weather
    format: str                      # indoor / outdoor
    venue_suggestion: str
    target_voters: str
    talking_points: list[str]
    rationale: str
    draft_outreach: str | None = None

class Slate(BaseModel):
    region: str
    horizon: str
    ranked_events: list[EventRecommendation]
```

---

## WS-0 — Foundation / Contracts  ·  owner: ____  ·  ~30 min  ·  BLOCKS EVERYTHING

Do this together at kickoff. Nothing else starts until `schemas/` and `mocks/` are committed and pushed.

| ID | Task (file) | Input | Output | Done when |
|----|-------------|-------|--------|-----------|
| 0.1 | Define Pydantic schemas (`schemas/models.py`) | the contracts above | `Issue`, `EventRecommendation`, `Slate`, `Weather`, `TurnoutSummary` | imports clean; `python -c "import schemas.models"` works |
| 0.2 | Mock objects (`mocks/fixtures.py`) | the schemas | `mock_issues()`, `mock_event()`, `mock_slate()` returning valid instances | each returns a schema-valid object |
| 0.3 | Sample slate JSON (`mocks/slate.sample.json`) | `mock_slate()` | a realistic 4–5 event ranked slate as JSON | UI can `fetch()` it and render |
| 0.4 | Repo skeleton + deps (`pyproject.toml`, dir tree, `.env.example`) | layout above | installable repo, env-var template (ANTHROPIC_API_KEY, JUA_API_KEY) | `pip install -e .` succeeds; everyone has the tree |

---

## WS-1 — Issue Scout  ·  owner: ____  ·  Depends on: WS-0  ·  Blocks: none (mocks)

Scans local signal, returns issues tagged by area. Builds against fixture articles — no live scraping on the critical path.

| ID | Task (file) | Input | Output | Done when |
|----|-------------|-------|--------|-----------|
| 1.1 | Local news fetcher (`tools/news.py`) | region + feed URLs | `list[Article]` (title, text, url) | returns articles from a pinned feed; cached to disk |
| 1.2 | Social fixture loader (`tools/social.py`) | path to seeded sample | `list[Post]` | loads the sample; same shape as news output |
| 1.3 | Issue clustering (`agents/scout.py::cluster`) | raw articles/posts | `list[Issue]` tagged by area, with salience | Claude structured-output returns valid `Issue` list on fixtures |
| 1.4 | Scout entrypoint + cache (`agents/scout.py::run`) | region | `list[Issue]` | `run(region)` returns ranked issues; second call hits cache |

## WS-2 — Data Tools  ·  owner: ____  ·  Depends on: WS-0  ·  Blocks: none (independent)

Two clean function contracts the Event Architect calls. Each is independently testable — ideal to shard to a coding agent from its row alone.

| ID | Task (file) | Input | Output | Done when |
|----|-------------|-------|--------|-----------|
| 2.1 | Scrub/generate sample voter CSV (`data/voters.sample.csv`) | real export or synthetic | precinct-level CSV, **no PII** | columns: precinct, county, turnout_history, segment counts |
| 2.2 | Turnout query (`tools/turnout.py::get_turnout`) | `area` | `TurnoutSummary` | DuckDB/pandas over the CSV; returns soft precincts + segments; no PII in output |
| 2.3 | Area→geo resolver (`tools/geo.py`) | area name | lat/long (static lookup) | every demo area resolves to coords for Jua |
| 2.4 | Jua weather client (`tools/weather.py::get_weather`) | `area`, `date` | `Weather` (incl. `recommended_format`) | live Jua call wrapped with **timeout + cache**; maps precip→indoor/outdoor |

## WS-3 — Event Architect  ·  owner: ____  ·  Depends on: WS-0 (+ WS-2 *contracts*, mocked)  ·  Blocks: none

One issue → one fully-briefed event. Build against **mocked** `get_weather`/`get_turnout`; swap reals at integration. Bounded: one call each, hard timeout, no loops.

| ID | Task (file) | Input | Output | Done when |
|----|-------------|-------|--------|-----------|
| 3.1 | Event ideation prompt (`agents/architect.py::ideate`) | `Issue` + `Weather` + `TurnoutSummary` | partial `EventRecommendation` (format, venue, audience, talking points, rationale) | Claude structured-output valid against mocked inputs |
| 3.2 | Architect assembly (`agents/architect.py::build_event`) | `Issue` | `EventRecommendation` | calls weather+turnout (mock or real) then ideate; bounded + timeout |
| 3.3 | Parallel runner (`agents/architect.py::build_events`) | `list[Issue]` | `list[EventRecommendation]` | `asyncio.gather` with per-event timeout; a failed event is dropped, not fatal |
| 3.4 | Draft outreach (stretch) (`agents/architect.py::draft`) | `EventRecommendation` | fills `draft_outreach` | produces a sendable post/email for the event |

## WS-4 — Strategist + Orchestrator + API  ·  owner: ____  ·  Depends on: WS-0 (+ WS-1/WS-3 *contracts*, mocked)  ·  Blocks: none

Ranks events, wires the pipeline, exposes the endpoint the UI calls.

| ID | Task (file) | Input | Output | Done when |
|----|-------------|-------|--------|-----------|
| 4.1 | Ranking (`agents/strategist.py::rank`) | `list[EventRecommendation]` | ranked `Slate` | scores by salience × turnout opportunity × feasibility; returns ordered `Slate` (build on `mock_event()` list) |
| 4.2 | Orchestrator (`orchestrator.py::run`) | region + horizon | `Slate` | wires Scout → `build_events` → rank; works end-to-end on **mocks** first |
| 4.3 | API endpoint (`api.py`) | `POST /slate {region, horizon}` | `Slate` JSON | FastAPI serves the orchestrator; returns the sample slate even before reals are wired |
| 4.4 | Determinism/cache layer (`orchestrator.py`) | — | cached Scout + tool outputs | a second identical run returns instantly; demo reproducible |
| 4.5 | Guild.ai wrap (integration) (`orchestrator.py`) | the working agents | agents registered/orchestrated under Guild.ai | demo shows Guild orchestrating; **only after 4.2 works standalone** |

## WS-UI — Frontend  ·  owner: ____ (the UI teammate)  ·  Depends on: WS-0 fixture + REST contract ONLY  ·  Never blocks on backend

Owns `ui/` entirely. Builds against `mocks/slate.sample.json` and the `POST /slate` contract. Use OpenUI (sponsor). Pick whatever framework you like — the only contract is the `Slate` shape + the endpoint.

| ID | Task (file) | Input | Output | Done when |
|----|-------------|-------|--------|-----------|
| U.1 | Project scaffold (`ui/`) | OpenUI starter | running dev server | renders a hello page locally |
| U.2 | Slate board (`ui/`) | `slate.sample.json` | ranked grid of event cards | cards show issue, area, date, weather, format from the fixture |
| U.3 | Event detail view (`ui/`) | one `EventRecommendation` | full briefing panel | click a card → talking points, target voters, venue, draft outreach |
| U.4 | "Agents working" view (`ui/`) | mock progress events | live coordination display | shows Scout→Architects→Strategist progress (mocked first); **the autonomy beat** |
| U.5 | Input + wire to API (`ui/`) | region + horizon form | calls `POST /slate`, renders result | with backend up, a real run renders end-to-end |
| U.6 | Demo polish (`ui/`) | the above | clean, legible slate | looks good on the projector; readable from the back of the room |

## WS-DEPLOY — Infra  ·  owner: ____ (can be WS-4 owner)  ·  Depends on: an endpoint exists

| ID | Task (file) | Input | Output | Done when |
|----|-------------|-------|--------|-----------|
| D.1 | Render service for API (`render.yaml`) | `api.py` | deployed API URL | `POST /slate` works against the live URL |
| D.2 | Deploy UI | `ui/` build | live UI URL | UI loads publicly and hits the live API |
| D.3 | Secrets + smoke test | API keys | green end-to-end on prod | one real run produces a slate on the deployed stack |

---

## Dependency graph

```
                         WS-0  (schemas + mocks)   ← everything waits on this, 30 min
                           │
        ┌──────────┬───────┼───────────┬──────────────┐
        ▼          ▼       ▼           ▼              ▼
      WS-1       WS-2    WS-3        WS-4           WS-UI
     Scout      Tools  Architect  Strat+Orch+API   Frontend
        │          │       │           │              │
        └──────────┴───────┴─────┬─────┘              │  (builds on fixture + REST
                                 ▼                    │   contract — never blocks)
                        INTEGRATION  ◄────────────────┘
                  (swap mocks→reals, wire Guild.ai,
                   connect UI to live API)
                                 │
                                 ▼
                            WS-DEPLOY
```

After WS-0, the five workstreams run fully in parallel. Each builds and tests against mocks. They only converge at integration.

## Timeline (90-minute checkpoints, anchored to hacking start = T0)

- **T0 → T+0:30 — WS-0.** Whole team. Schemas, mocks, repo skeleton committed. Nobody branches off until this is pushed.
- **T+0:30 → T+1:30 — parallel build.** Each workstream gets its happy path working against mocks.
  - **Checkpoint A (T+1:30):** every workstream demos its happy path on mocks. Scout returns issues; tools return weather+turnout; Architect builds one event; Orchestrator runs end-to-end on mocks; UI renders the sample slate. *(Lunch ~1:30.)*
- **T+1:30 → T+3:00 — integration.** Swap mocks for reals: Architect calls real tools, Orchestrator calls real Scout, UI hits the live API. Wrap with Guild.ai (4.5).
  - **Checkpoint B (T+3:00):** one real region produces a real slate, rendered in the real UI.
- **T+3:00 → T+4:30 — freeze + harden.** No new features. Add caching/determinism (4.4), bound every agent, polish the UI (U.6), deploy (WS-DEPLOY).
  - **Checkpoint C (T+4:30):** feature freeze. Stack is deployed and reproducible.
- **T+4:30 → submission — demo.** Record the 3-minute video against the deployed stack. Dry-run the script twice. Submit Devpost (repo + video) by **4:30 PM**.

## Assigning tasks to coding agents

- Give an agent **one task row** plus access to `schemas/models.py` and `mocks/fixtures.py`. That's all it needs — the row's Input/Output/Done is the spec.
- Tell it to **build against the mock**, not the real dependency (e.g. Architect agent uses a mocked `get_weather`), and to write a tiny `if __name__ == "__main__"` smoke test that proves the Done condition.
- Keep each agent **inside its workstream's files** (the boundaries above). If a task needs to touch a shared file, that's a sign it belongs in WS-0 or integration, not a parallel branch.

## The first 30 minutes decide the day

The entire reason to go multi-agent is parallelism, and parallelism only works if the contracts exist before anyone branches. Do WS-0 together, push it, and confirm everyone can `import schemas.models` and load `slate.sample.json` before splitting up. Skip this and you'll be merging conflicting type definitions at 3pm.
