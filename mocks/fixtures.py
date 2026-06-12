from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from schemas.models import EventRecommendation, Issue, ProgressEvent, Slate, Weather

ProgressStatus = Literal["started", "tool_call", "done", "failed"]

_BASE_DATE = date(2026, 6, 15)

_ISSUES: list[Issue] = [
    Issue(
        id="issue-water-001",
        title="Alachua Creek water quality concerns",
        area="north Gainesville, Alachua County",
        summary=(
            "Residents near Alachua Creek report discoloration and odor after recent "
            "storm runoff. City council scheduled a public works briefing; neighborhood "
            "associations are organizing for answers."
        ),
        source_links=[
            "https://www.gainesville.com/story/news/local/2026/06/alachua-creek-water-quality",
            "https://www.wuft.org/news/2026/06/12/north-gainesville-water-concerns",
        ],
        salience=0.92,
    ),
    Issue(
        id="issue-school-002",
        title="Marion County school funding shortfall",
        area="Ocala, Marion County",
        summary=(
            "The Marion County School Board faces a budget gap heading into fall, "
            "with proposed cuts to arts and after-school programs. Parent groups "
            "and teachers' associations are mobilizing ahead of the July budget vote."
        ),
        source_links=[
            "https://www.ocala.com/story/news/education/2026/06/marion-school-budget-gap",
            "https://www.wuft.org/news/2026/06/10/marion-county-school-funding",
        ],
        salience=0.88,
    ),
    Issue(
        id="issue-housing-003",
        title="East Gainesville affordable housing crunch",
        area="east Gainesville, Alachua County",
        summary=(
            "Rising rents and limited inventory are squeezing longtime east "
            "Gainesville residents. A proposed infill development has sparked debate "
            "over displacement versus new affordable units."
        ),
        source_links=[
            "https://www.gainesville.com/story/news/local/2026/06/east-gainesville-housing",
            "https://www.wuft.org/news/2026/06/08/affordable-housing-alachua",
        ],
        salience=0.85,
    ),
    Issue(
        id="issue-broadband-004",
        title="Rural broadband gaps in western Marion",
        area="western Marion County",
        summary=(
            "Farmers and small businesses west of Ocala report unreliable internet "
            "after a provider delayed fiber expansion. County commissioners are "
            "weighing a public-private partnership to close coverage gaps."
        ),
        source_links=[
            "https://www.ocala.com/story/news/local/2026/06/western-marion-broadband",
        ],
        salience=0.72,
    ),
    Issue(
        id="issue-transit-005",
        title="RTS bus route cuts proposed",
        area="Gainesville, Alachua County",
        summary=(
            "Gainesville RTS proposed eliminating two east-side routes to close a "
            "budget shortfall. Riders and transit advocates are pushing back, citing "
            "disproportionate impact on working families and UF staff."
        ),
        source_links=[
            "https://www.gainesville.com/story/news/local/2026/06/rts-route-cuts",
            "https://www.wuft.org/news/2026/06/11/gainesville-transit-cuts",
        ],
        salience=0.68,
    ),
]

_WEATHER_BY_RANK: list[Weather] = [
    Weather(
        summary="Steady rain through Saturday afternoon",
        condition="rain",
        temp_f=78.0,
        precip_chance=0.65,
        recommended_format="indoor",
    ),
    Weather(
        summary="Clear skies, low humidity",
        condition="clear",
        temp_f=88.0,
        precip_chance=0.10,
        recommended_format="outdoor",
    ),
    Weather(
        summary="Afternoon thunderstorms likely",
        condition="thunderstorms",
        temp_f=82.0,
        precip_chance=0.80,
        recommended_format="indoor",
    ),
    Weather(
        summary="Partly cloudy, warm breeze",
        condition="partly_cloudy",
        temp_f=85.0,
        precip_chance=0.25,
        recommended_format="outdoor",
    ),
    Weather(
        summary="Hot and humid, heat index near 100",
        condition="hot_humid",
        temp_f=94.0,
        precip_chance=0.35,
        recommended_format="indoor",
    ),
]

_EVENT_BRIEFS: list[dict[str, object]] = [
    {
        "venue_suggestion": "Thelma A. Boltin Center community room",
        "target_voters": (
            "Soft precincts 14, 22, and 31 in north Gainesville; environmentally "
            "engaged homeowners and renters near creek corridors"
        ),
        "talking_points": [
            "Commit to transparent water testing and public reporting timelines",
            "Fund stormwater infrastructure upgrades in north Gainesville",
            "Establish a resident advisory panel for creek-adjacent neighborhoods",
        ],
        "rationale": (
            "Highest-salience issue in the district with an active neighborhood "
            "coalition. Rain forecast makes an indoor listening session the "
            "credible, weather-safe format this week."
        ),
        "draft_outreach": (
            "North Gainesville neighbors: join us Saturday for a community listening "
            "session on Alachua Creek water quality. Share what you're seeing, ask "
            "questions, and help shape our clean-water priorities. Indoor event — "
            "Thelma A. Boltin Center, 2pm. RSVP link in bio."
        ),
    },
    {
        "venue_suggestion": "Citizens' Circle at Tuscawilla Park",
        "target_voters": (
            "Parents and educators in Marion County precincts 8, 12, and 19; "
            "soft turnout among suburban families in southwest Ocala"
        ),
        "talking_points": [
            "Protect classroom funding and after-school programs",
            "Oppose cuts that hit arts and vocational education first",
            "Push for transparent budget hearings before the July vote",
        ],
        "rationale": (
            "School funding is the top Marion County conversation with a hard "
            "budget deadline. Clear weather supports an outdoor rally that draws "
            "families and local press."
        ),
        "draft_outreach": (
            "Marion County families: our schools need us before the July budget vote. "
            "Join us at Tuscawilla Park this Sunday for a rally to protect classroom "
            "funding and after-school programs. Bring signs, bring neighbors."
        ),
    },
    {
        "venue_suggestion": "Eastside Community Center multipurpose hall",
        "target_voters": (
            "Renters and longtime homeowners in east Gainesville precincts 5, 9, "
            "and 17; seniors facing displacement pressure"
        ),
        "talking_points": [
            "Require affordable-unit set-asides in new infill developments",
            "Expand tenant protections and anti-displacement resources",
            "Invest in community land trusts for east Gainesville",
        ],
        "rationale": (
            "Housing costs are climbing fastest on the east side, where turnout "
            "opportunity is high among renters who rarely hear from campaigns. "
            "Thunderstorms favor an indoor town hall."
        ),
        "draft_outreach": (
            "East Gainesville: rents are up and options are down. Come to a town hall "
            "on affordable housing and the proposed infill project — your voice "
            "shapes what gets built. Eastside Community Center, Thursday 6:30pm."
        ),
    },
    {
        "venue_suggestion": "Dunnellon Community Park pavilion",
        "target_voters": (
            "Rural voters in western Marion precincts 27, 33, and 41; small-business "
            "owners dependent on reliable connectivity"
        ),
        "talking_points": [
            "Accelerate county fiber partnerships for underserved rural roads",
            "Treat broadband as essential infrastructure for farms and small business",
            "Demand accountability from providers that miss expansion deadlines",
        ],
        "rationale": (
            "Western Marion voters feel overlooked on infrastructure; an outdoor "
            "event in Dunnellon signals the campaign shows up beyond Ocala. "
            "Partly cloudy forecast is workable for a park pavilion format."
        ),
        "draft_outreach": (
            "Western Marion: tired of spotty internet holding back your farm or "
            "business? Meet us at Dunnellon Community Park to talk rural broadband "
            "and what the county can do now. Saturday morning, coffee provided."
        ),
    },
    {
        "venue_suggestion": "RTS Downtown Transfer Station meeting room",
        "target_voters": (
            "Transit-dependent riders in Gainesville precincts 3, 7, and 11; "
            "UF staff and service workers on proposed cut routes"
        ),
        "talking_points": [
            "Oppose route cuts that hit east-side workers hardest",
            "Fund RTS through fair-share county and city partnerships",
            "Center rider testimony in any service-reduction decision",
        ],
        "rationale": (
            "Route cuts are imminent and riders are already organizing. An indoor "
            "forum near the transfer station makes participation easy for the "
            "people most affected."
        ),
        "draft_outreach": (
            "Gainesville riders: proposed RTS cuts would hit east-side routes first. "
            "Join a rider forum at the Downtown Transfer Station to share your story "
            "and fight for reliable transit. Wednesday 5:30pm."
        ),
    },
]


def mock_issues() -> list[Issue]:
    return [issue.model_copy(deep=True) for issue in _ISSUES]


def mock_event(issue: Issue | None = None, rank: int = 0) -> EventRecommendation:
    issues = mock_issues()
    selected = issue if issue is not None else issues[rank % len(issues)]
    brief = _EVENT_BRIEFS[rank % len(_EVENT_BRIEFS)]
    weather = _WEATHER_BY_RANK[rank % len(_WEATHER_BY_RANK)]

    return EventRecommendation(
        issue=selected.model_copy(deep=True),
        area=selected.area,
        proposed_date=_BASE_DATE + timedelta(days=rank * 3 + 2),
        weather=weather.model_copy(deep=True),
        format=weather.recommended_format,
        venue_suggestion=str(brief["venue_suggestion"]),
        target_voters=str(brief["target_voters"]),
        talking_points=list(brief["talking_points"]),  # type: ignore[arg-type]
        rationale=str(brief["rationale"]),
        draft_outreach=str(brief["draft_outreach"]),
    )


def mock_slate(
    region: str = "Florida HD-21",
    horizon: str = "next two weeks",
) -> Slate:
    return Slate(
        region=region,
        horizon=horizon,
        ranked_events=[mock_event(rank=rank) for rank in range(len(_ISSUES))],
    )


def mock_progress_events(run_id: str = "mock-run-001") -> list[ProgressEvent]:
    issues = mock_issues()
    events: list[ProgressEvent] = []
    seq = 0

    def add(agent: str, status: ProgressStatus, detail: str) -> None:
        nonlocal seq
        events.append(
            ProgressEvent(
                run_id=run_id,
                seq=seq,
                agent=agent,
                status=status,
                detail=detail,
            )
        )
        seq += 1

    add(
        "scout",
        "started",
        "Scanning local news and social signal across Florida HD-21 (Marion + Alachua)",
    )
    add(
        "scout",
        "tool_call",
        "Fetching RSS feeds for Gainesville Sun, Ocala Star-Banner, and WUFT",
    )
    add(
        "scout",
        "done",
        f"Identified {len(issues)} issues across Gainesville, Marion, and Alachua counties",
    )

    for issue in issues:
        agent = f"architect:{issue.id}"
        add(agent, "started", f"Event Architect spinning up for '{issue.title}'")
        add(
            agent,
            "tool_call",
            f"Pulling Jua weather forecast for {issue.area}",
        )
        add(
            agent,
            "tool_call",
            f"Querying turnout history for soft precincts in {issue.area}",
        )
        add(
            agent,
            "done",
            f"Briefed event recommendation for {issue.area}",
        )

    add(
        "strategist",
        "started",
        f"Ranking {len(issues)} event recommendations by salience × turnout opportunity × feasibility",
    )
    add(
        "strategist",
        "done",
        f"Slate ranked: {len(issues)} events ready for {issues[0].area.split(',')[-1].strip()} and Marion County",
    )

    return events
