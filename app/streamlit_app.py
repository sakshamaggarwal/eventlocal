"""
eventlocal — Streamlit demo UI (Hackathon MVP).

Run: streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import asyncio
import streamlit as st

try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from agents.master_agent import discover_events
from app.config import settings
from models.user_profile import UserProfile

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="eventlocal — Your Event Brain",
    page_icon="🎉",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Custom styling
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    .stApp { max-width: 1200px; margin: 0 auto; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; }
    .event-card {
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
        background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
    }
    .score-high { color: #10b981; font-weight: bold; }
    .score-med { color: #f59e0b; font-weight: bold; }
    .score-low { color: #ef4444; font-weight: bold; }
    .demo-banner {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        margin-bottom: 16px;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("🎉 eventlocal")
st.markdown(
    "**Your city's Event Brain** — personalized evening plans "
    "powered by a knowledge graph + AI"
)

# Show demo mode banner if no API keys
has_groq = bool(settings.groq_api_key)
has_sources = bool(settings.luma_api_key or settings.eventbrite_api_key or settings.google_places_api_key)

if not has_groq or not has_sources:
    missing = []
    if not has_groq:
        missing.append("GROQ_API_KEY (for AI itineraries)")
    if not has_sources:
        missing.append("event source keys (Luma/Eventbrite/Google Places)")
    st.markdown(
        f'<div class="demo-banner">🎮 <b>Demo Mode</b> — running with sample data. '
        f'Add {", ".join(missing)} to .env for live results.</div>',
        unsafe_allow_html=True,
    )

st.divider()

# ---------------------------------------------------------------------------
# Sidebar — User Profile
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("👤 Your Profile")

    age = st.slider(
        "Your Age",
        min_value=13,
        max_value=80,
        value=28,
        help="We personalize events to your age bracket",
    )

    bracket_labels = {
        range(0, 21): ("🎮 Under 21", "All-ages events, gaming, cafes"),
        range(21, 30): ("🍸 Twenties", "Nightlife, rooftops, tech meetups"),
        range(30, 40): ("🍷 Thirties", "Cocktail bars, live music, comedy"),
        range(40, 50): ("🎭 Forties", "Jazz, theater, wine, fine dining"),
        range(50, 101): ("🎵 50+", "Classical, opera, cultural events"),
    }
    for age_range, (label, desc) in bracket_labels.items():
        if age in age_range:
            st.info(f"**{label}**\n\n{desc}")
            break

    st.divider()

    city = st.selectbox(
        "City",
        ["bay-area"],
        index=0,
        help="Bay Area is the only supported city for the MVP",
    )

    date = st.date_input("Date")
    date_str = date.isoformat() if date else "today"

    st.divider()

    # Status indicators
    st.markdown("### System Status")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"{'🟢' if has_groq else '🟡'} LLM")
        st.markdown(f"{'🟢' if has_sources else '🟡'} APIs")
    with col_b:
        st.markdown("🟡 Cognee")
        st.markdown("🟢 Scoring")

    st.divider()
    st.caption("🧠 Powered by Cognee + Qwen3-32B")
    st.caption("Built for Company Brain Hackathon 2026")

# ---------------------------------------------------------------------------
# Main — Discover Events
# ---------------------------------------------------------------------------

col1, col2 = st.columns([2, 1])

with col1:
    if st.button("🔍 Discover My Evening", type="primary", use_container_width=True):
        profile = UserProfile(age=age)

        with st.spinner("🧠 Building your personalized plan..."):
            progress = st.progress(0)
            status = st.empty()

            status.text("📡 Fetching events from all sources...")
            progress.progress(20)

            try:
                plan = asyncio.run(
                    discover_events(profile=profile, date=date_str, city=city)
                )

                progress.progress(60)
                status.text("🎯 Scoring events for your age bracket...")

                progress.progress(80)
                status.text("✍️ Building your personalized itinerary...")

                progress.progress(100)
                status.empty()
                progress.empty()

                if not plan.events:
                    st.warning("No events found for this date and location.")
                    st.stop()

                # Stats row
                st.success(f"Found {len(plan.events)} events — here's your plan!")
                m1, m2, m3 = st.columns(3)
                m1.metric("Events Found", len(plan.events))
                m2.metric("Age Bracket", profile.age_bracket.value.replace("_", " ").title())
                top_score = max(e.age_score for e in plan.events) if plan.events else 0
                m3.metric("Best Match", f"{top_score:.0%}")

                st.markdown("---")

                # The itinerary
                st.markdown(plan.itinerary_markdown)

                # Scored events breakdown
                with st.expander(f"📊 All {len(plan.events)} scored events", expanded=False):
                    for ev in plan.events:
                        score_pct = ev.age_score * 100
                        if score_pct >= 70:
                            score_class = "score-high"
                        elif score_pct >= 50:
                            score_class = "score-med"
                        else:
                            score_class = "score-low"

                        score_bar = "🟢" * int(ev.age_score * 5) + "⚪" * (5 - int(ev.age_score * 5))

                        st.markdown(
                            f"**{ev.title}** — {ev.venue_name or ev.source}  \n"
                            f"Age fit: {score_bar} ({ev.age_score:.0%})  \n"
                            f"_{ev.start_time or 'Time TBD'}_ | {ev.price or 'Price TBD'} | Source: {ev.source}"
                        )
                        if ev.tags:
                            st.caption(f"Tags: {', '.join(ev.tags[:6])}")
                        st.markdown("---")

            except Exception as exc:
                progress.progress(100)
                status.empty()
                st.error(f"Something went wrong: {exc}")
                st.info(
                    "Make sure your .env file has at least GROQ_API_KEY set. "
                    "Event source API keys are optional — the app works with sample data without them."
                )

with col2:
    st.markdown("### How it works")
    st.markdown("""
1. **Fetch** events from Luma, Eventbrite, Google Places
2. **Cognify** — build a knowledge graph of events, venues & reviews
3. **Score** — rate each event by your age bracket fit
4. **Plan** — AI generates a complete evening itinerary

The more data in the knowledge graph, the smarter it gets.
    """)

    st.markdown("### Architecture")
    st.markdown("""
```
User (age slider)
    ↓
Master Agent
    ├── Luma API
    ├── Eventbrite API
    ├── Google Places API
    ↓
Cognee (Knowledge Graph)
    ↓
Age Scoring Layer
    ↓
Planner Agent (Qwen3-32B)
    ↓
Evening Itinerary
```
    """)

    st.markdown("### Try different ages")
    st.markdown("""
- **18** — all-ages gaming & food festivals
- **25** — nightlife, rooftops, tech meetups
- **35** — cocktail bars, comedy, speakeasies
- **45** — jazz, theater, fine dining
- **55** — classical, opera, cultural events
    """)
