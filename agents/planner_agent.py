"""
Planner Agent — takes scored events + Cognee context and generates
a personalized evening itinerary using Qwen3-32B via Groq.

Falls back to a template-based plan when no LLM key is available.
"""
from __future__ import annotations

import structlog

from app.config import settings
from app.llm import chat
from app.prompts import load_system_prompt
from models.user_profile import Event, EveningPlan, UserProfile

log = structlog.get_logger()

SYSTEM_PROMPT = """\
You are the eventlocal Planner — an expert evening-outing planner for {city}.

Given a list of scored events and knowledge-graph context about venues,
build a personalized evening plan. Structure it as:

1. DINNER — a restaurant recommendation near the main event area
2. PRE-GAME — a bar or lounge to start the evening
3. MAIN EVENT — the top-scored event from the list
4. LATE NIGHT — wind-down spot or backup option

Rules:
- Keep venues walkable from each other when possible
- Include realistic travel times between stops
- Note cover charges, dress codes, reservation needs
- Tailor tone and suggestions to the user's age bracket ({age_bracket})
- Be direct and opinionated — pick the best option, don't hedge
- If fewer than 4 stops make sense, that's fine — quality over quantity

Return your plan as markdown with emoji headers matching this format:
🍽️ DINNER (Time) — Venue
🍸 PRE-GAME (Time) — Venue
🎶 MAIN EVENT (Time) — Venue
🌙 LATE NIGHT (Time) — Venue

End with a one-line "WHY THIS PLAN WORKS" summary.
"""


async def generate_plan(
    events: list[Event],
    profile: UserProfile,
    city: str,
    date: str,
    cognee_context: str = "",
) -> EveningPlan:
    """Generate an evening plan from scored events using the LLM."""

    events_text = "\n".join(
        f"- [{e.age_score:.2f}] {e.title} @ {e.venue_name or 'TBD'} "
        f"({e.start_time}) — {e.source} — {e.price or 'Price TBD'}"
        for e in events
    )

    if settings.groq_api_key:
        itinerary_md = await _llm_plan(events, events_text, profile, city, date, cognee_context)
    else:
        log.info("planner.demo_mode", msg="No GROQ_API_KEY — using template-based plan")
        itinerary_md = _template_plan(events, profile, city, date)

    return EveningPlan(
        city=city,
        date=date,
        user_profile=profile,
        events=events,
        itinerary_markdown=itinerary_md,
        explanation=f"Plan for a {profile.age}-year-old in {city} on {date}",
    )


async def _llm_plan(
    events: list[Event],
    events_text: str,
    profile: UserProfile,
    city: str,
    date: str,
    cognee_context: str,
) -> str:
    """Generate plan via Qwen3-32B on Groq."""
    concierge_context = load_system_prompt()
    planner_instructions = SYSTEM_PROMPT.format(
        city=city,
        age_bracket=profile.age_bracket.value,
    )

    messages = [
        {
            "role": "system",
            "content": f"{planner_instructions}\n\n---\n\n{concierge_context}",
        },
        {
            "role": "user",
            "content": (
                f"Date: {date}\n"
                f"User age: {profile.age} ({profile.age_bracket.value})\n\n"
                f"## Top Events (scored by age fit)\n{events_text}\n\n"
                f"## Venue & Review Context from Knowledge Graph\n{cognee_context or 'No additional context available.'}\n\n"
                f"Build me the best evening plan."
            ),
        },
    ]

    log.info("planner.generating", event_count=len(events), age=profile.age)
    return await chat(messages)


def _template_plan(events: list[Event], profile: UserProfile, city: str, date: str) -> str:
    """Build a structured plan from the top-scored events without an LLM."""
    bracket = profile.age_bracket.value

    # Pick events by role
    main_event = events[0] if events else None
    venues = [e for e in events if e.source == "google_places"]
    ticketed = [e for e in events if e.source in ("luma", "eventbrite") and e != main_event]

    dinner_spot = next((v for v in venues if any(t in v.tags for t in ["fine-dining", "gastropub", "supper-club"])), None)
    pregame_spot = next((v for v in venues if any(t in v.tags for t in ["cocktail", "speakeasy", "rooftop", "craft-beer", "wine-bar"])), None)
    if not pregame_spot and ticketed:
        pregame_spot = ticketed[0]
    late_spot = next((v for v in venues if v != dinner_spot and v != pregame_spot), None)
    if not late_spot and len(ticketed) > 1:
        late_spot = ticketed[1]

    lines = []
    lines.append(f"# Your Evening in {city.replace('-', ' ').title()} — {date}\n")
    lines.append(f"*Curated for age bracket: **{bracket.replace('_', ' ')}***\n")

    if dinner_spot:
        lines.append(f"## 🍽️ DINNER (7:00 PM) — {dinner_spot.venue_name}")
        lines.append(f"_{dinner_spot.description[:120]}_")
        lines.append(f"📍 {dinner_spot.venue_address} · {dinner_spot.price or 'Price TBD'}")
        lines.append(f"Age fit score: **{dinner_spot.age_score:.2f}**\n")

    if pregame_spot:
        lines.append(f"## 🍸 PRE-GAME (8:30 PM) — {pregame_spot.venue_name or pregame_spot.title}")
        lines.append(f"_{pregame_spot.description[:120]}_")
        if pregame_spot.venue_address:
            lines.append(f"📍 {pregame_spot.venue_address} · {pregame_spot.price or 'Price TBD'}")
        lines.append(f"Age fit score: **{pregame_spot.age_score:.2f}**\n")

    if main_event:
        lines.append(f"## 🎶 MAIN EVENT ({main_event.start_time[11:16] if len(main_event.start_time) > 11 else '10:00 PM'}) — {main_event.title}")
        lines.append(f"_{main_event.description[:150]}_")
        lines.append(f"📍 {main_event.venue_address or main_event.venue_name} · {main_event.price or 'Price TBD'}")
        if main_event.rsvp_count:
            lines.append(f"🎟️ {main_event.rsvp_count} RSVPs · Source: {main_event.source}")
        lines.append(f"Age fit score: **{main_event.age_score:.2f}**\n")

    if late_spot:
        lines.append(f"## 🌙 LATE NIGHT (11:30 PM) — {late_spot.venue_name or late_spot.title}")
        lines.append(f"_{late_spot.description[:120]}_")
        if late_spot.venue_address:
            lines.append(f"📍 {late_spot.venue_address}")
        lines.append(f"Age fit score: **{late_spot.age_score:.2f}**\n")

    # Summary
    lines.append("---")
    lines.append(
        f"💡 **WHY THIS PLAN WORKS:** Events curated and scored for your age bracket "
        f"({bracket.replace('_', ' ')}), with {len(events)} options analyzed across "
        f"Luma, Eventbrite, and Google Places."
    )

    if not settings.groq_api_key:
        lines.append("")
        lines.append(
            "> 🔑 **Demo Mode:** Add a `GROQ_API_KEY` to your `.env` file for "
            "AI-generated personalized itineraries powered by Qwen3-32B. "
            "Get a free key at [console.groq.com](https://console.groq.com)."
        )

    return "\n".join(lines)
