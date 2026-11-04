"""
eventlocal — Streamlit demo UI (Hackathon MVP).

Run: streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import asyncio
import streamlit as st

# Ensure event loop works with Streamlit
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from agents.master_agent import discover_events
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
# Header
# ---------------------------------------------------------------------------

st.title("🎉 eventlocal")
st.markdown(
    "**Your city's Event Brain** — personalized evening plans "
    "powered by a knowledge graph + AI"
)
st.divider()

# ---------------------------------------------------------------------------
# Sidebar — User Profile (Age Slider = MVP personalization)
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

    # Show which bracket they fall into
    bracket_labels = {
        range(0, 21): "🎮 Under 21 — All-ages events, gaming, cafes",
        range(21, 30): "🍸 Twenties — Nightlife, rooftops, tech meetups",
        range(30, 40): "🍷 Thirties — Cocktail bars, live music, comedy",
        range(40, 50): "🎭 Forties — Jazz, theater, wine, fine dining",
        range(50, 101): "🎵 50+ — Classical, opera, cultural events",
    }
    for age_range, label in bracket_labels.items():
        if age in age_range:
            st.caption(label)
            break

    st.divider()

    city = st.selectbox(
        "City",
        ["bay-area", "seattle"],
        index=0,
    )

    date = st.date_input("Date")
    date_str = date.isoformat() if date else "today"

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
            # Progress indicators
            progress = st.progress(0)
            status = st.empty()

            status.text("📡 Fetching events from all sources...")
            progress.progress(20)

            try:
                plan = asyncio.run(
                    discover_events(profile=profile, date=date_str, city=city)
                )
                progress.progress(100)
                status.empty()

                # Display the plan
                st.success(f"Found {len(plan.events)} events — here's your plan!")
                st.markdown("---")
                st.markdown(plan.itinerary_markdown)

                # Show scored events in an expander
                with st.expander(f"📊 All {len(plan.events)} scored events"):
                    for ev in plan.events:
                        score_bar = "🟢" * int(ev.age_score * 5) + "⚪" * (5 - int(ev.age_score * 5))
                        st.markdown(
                            f"**{ev.title}** — {ev.venue_name or ev.source}  \n"
                            f"Age fit: {score_bar} ({ev.age_score:.2f})  \n"
                            f"_{ev.start_time}_ | {ev.price or 'Price TBD'}"
                        )
                        st.markdown("---")

            except Exception as exc:
                progress.progress(100)
                status.empty()
                st.error(f"Something went wrong: {exc}")
                st.info(
                    "Make sure your .env file has at least GROQ_API_KEY set. "
                    "Event source API keys are optional — the app works with any subset."
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
