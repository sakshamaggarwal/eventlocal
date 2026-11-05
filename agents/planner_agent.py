"""
Planner Agent — takes scored events + Cognee context and generates
a personalized evening itinerary using Qwen3-32B via Groq.
"""
from __future__ import annotations

import json
import structlog

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

    # Serialize top events for the LLM
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
    itinerary_md = await chat(messages)

    return EveningPlan(
        city=city,
        date=date,
        user_profile=profile,
        events=events,
        itinerary_markdown=itinerary_md,
        explanation=f"Plan for a {profile.age}-year-old in {city} on {date}",
    )
