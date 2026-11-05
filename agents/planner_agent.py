"""
Planner Agent — takes scored events + Cognee context and generates
a personalized evening itinerary using Qwen3-32B via Groq.

Falls back to a template-based plan when no GROQ_API_KEY is set.
"""
from __future__ import annotations

import structlog

from app.config import settings
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
    """Generate an evening plan — live LLM when available, template fallback."""

    if not settings.groq_api_key:
        log.info("planner.template_fallback", reason="No GROQ_API_KEY set")
        return _template_plan(events, profile, city, date)

    from app.llm import chat

    events_text = "\n".join(
        f"- [{e.age_score:.2f}] {e.title} @ {e.venue_name or 'TBD'} "
        f"({e.start_time}) — {e.source} — {e.price or 'Price TBD'}"
        for e in events
    )

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

    try:
        itinerary_md = await chat(messages)
    except Exception as exc:
        log.error("planner.llm_error", error=str(exc))
        return _template_plan(events, profile, city, date)

    return EveningPlan(
        city=city,
        date=date,
        user_profile=profile,
        events=events,
        itinerary_markdown=itinerary_md,
        explanation=f"AI-generated plan for a {profile.age}-year-old in {city} on {date}",
    )


def _template_plan(
    events: list[Event],
    profile: UserProfile,
    city: str,
    date: str,
) -> EveningPlan:
    """Build a rule-based itinerary when no LLM is available."""
    sorted_events = sorted(events, key=lambda e: e.age_score, reverse=True)

    def _find(tags: list[str]) -> Event | None:
        for ev in sorted_events:
            if any(t in ev.tags for t in tags):
                return ev
        return None

    dinner = _find(["fine-dining", "gastropub", "food-festival", "supper-club"])
    pregame = _find(["cocktail", "craft-beer", "wine-bar", "speakeasy", "rooftop", "happy-hour"])
    main = sorted_events[0] if sorted_events else None
    late = _find(["nightclub", "dance", "jazz", "comedy", "live-music"])

    lines = [f"# Your Evening in {city.replace('-', ' ').title()} — {date}\n"]

    if dinner and dinner != main:
        lines.append(f"🍽️ **DINNER (6:30 PM)** — {dinner.title} @ {dinner.venue_name}")
        lines.append(f"   {dinner.description[:120]}\n")

    if pregame and pregame not in (dinner, main):
        lines.append(f"🍸 **PRE-GAME (8:00 PM)** — {pregame.title} @ {pregame.venue_name}")
        lines.append(f"   {pregame.description[:120]}\n")

    if main:
        lines.append(f"🎶 **MAIN EVENT ({main.start_time[11:16] if len(main.start_time) > 11 else '9:00 PM'})** — {main.title} @ {main.venue_name}")
        lines.append(f"   Score: {main.age_score:.2f} | {main.price or 'Price TBD'}")
        lines.append(f"   {main.description[:120]}\n")

    if late and late not in (dinner, pregame, main):
        lines.append(f"🌙 **LATE NIGHT (11:00 PM)** — {late.title} @ {late.venue_name}")
        lines.append(f"   {late.description[:120]}\n")

    lines.append(f"\n**WHY THIS PLAN WORKS:** Curated for the {profile.age_bracket.value.replace('_', '-')} crowd based on age-fit scoring across {len(events)} events.")
    lines.append("\n> *This is a template plan. Set GROQ_API_KEY for AI-generated itineraries.*")

    return EveningPlan(
        city=city,
        date=date,
        user_profile=profile,
        events=sorted_events[:15],
        itinerary_markdown="\n".join(lines),
        explanation=f"Template plan for a {profile.age}-year-old in {city} on {date}",
    )
