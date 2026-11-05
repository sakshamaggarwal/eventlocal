"""
eventlocal — Streamlit UI (Hackathon MVP).

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
from app.db import is_available as db_is_available, load_user_kb, save_user_kb
from knowledge.cognee_engine import (
    export_all_kbs,
    get_user_kb,
    restore_user_kb,
)
from models.user_profile import UserProfile
from sources.sample_data import get_sample_events
from triggers import get_integration

# ---------------------------------------------------------------------------
# Page config & custom CSS
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="eventlocal — Your Event Brain",
    page_icon="🎉",
    layout="wide",
)

st.markdown("""
<style>
    /* Dark theme overrides */
    .stApp { background-color: #0e1117; }

    /* Hero section */
    .hero-title {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
        line-height: 1.2;
    }
    .hero-subtitle {
        font-size: 1.2rem;
        color: #9ca3af;
        margin-top: 0.5rem;
    }

    /* Category chip styling */
    .chip-container {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin: 1rem 0;
    }
    .chip {
        display: inline-block;
        padding: 0.4rem 1rem;
        border-radius: 2rem;
        background: #1e2130;
        border: 1px solid #374151;
        color: #d1d5db;
        font-size: 0.85rem;
        cursor: pointer;
        transition: all 0.2s;
    }
    .chip.active {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-color: #667eea;
        color: white;
    }

    /* Event card styling */
    .event-card {
        background: #1a1d2e;
        border: 1px solid #2d3148;
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        transition: transform 0.2s;
    }
    .event-card:hover { transform: translateY(-2px); }
    .event-title { font-size: 1.05rem; font-weight: 600; color: #e5e7eb; margin-bottom: 0.3rem; }
    .event-venue { font-size: 0.85rem; color: #9ca3af; }
    .event-meta { display: flex; gap: 1rem; margin-top: 0.5rem; font-size: 0.8rem; color: #6b7280; }
    .score-badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 1rem;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .score-high { background: #065f46; color: #6ee7b7; }
    .score-mid { background: #78350f; color: #fcd34d; }
    .score-low { background: #7f1d1d; color: #fca5a5; }

    /* Step cards */
    .step-card {
        background: #1a1d2e;
        border: 1px solid #2d3148;
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        height: 100%;
    }
    .step-icon { font-size: 2rem; margin-bottom: 0.5rem; }
    .step-label { font-size: 0.75rem; color: #667eea; text-transform: uppercase; letter-spacing: 0.1em; }
    .step-title { font-size: 1.1rem; font-weight: 600; color: #e5e7eb; margin: 0.3rem 0; }
    .step-desc { font-size: 0.85rem; color: #9ca3af; }

    /* Status indicator */
    .status-bar {
        display: flex;
        gap: 1.5rem;
        padding: 0.8rem 1.2rem;
        background: #1a1d2e;
        border-radius: 8px;
        margin-bottom: 1rem;
        font-size: 0.8rem;
        color: #9ca3af;
    }
    .status-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 0.4rem;
    }
    .dot-green { background: #10b981; }
    .dot-yellow { background: #f59e0b; }
    .dot-red { background: #ef4444; }

    /* Comparison table */
    .comparison-table {
        width: 100%;
        border-collapse: collapse;
        margin: 1rem 0;
    }
    .comparison-table th {
        background: #1a1d2e;
        padding: 0.8rem 1rem;
        text-align: left;
        font-weight: 600;
        color: #e5e7eb;
        border-bottom: 2px solid #667eea;
    }
    .comparison-table td {
        padding: 0.7rem 1rem;
        border-bottom: 1px solid #2d3148;
        color: #d1d5db;
    }
    .comparison-table tr:hover td { background: #1a1d2e; }

    /* Demo mode banner */
    .demo-banner {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d1b69 100%);
        border: 1px solid #374191;
        border-radius: 8px;
        padding: 0.8rem 1.2rem;
        margin-bottom: 1rem;
        font-size: 0.85rem;
        color: #93c5fd;
    }

    /* Graph placeholder */
    .graph-container {
        background: #1a1d2e;
        border: 1px solid #2d3148;
        border-radius: 12px;
        padding: 2rem;
        text-align: center;
        min-height: 300px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }

    /* Footer */
    .footer {
        text-align: center;
        padding: 2rem 0;
        color: #6b7280;
        font-size: 0.85rem;
        border-top: 1px solid #2d3148;
        margin-top: 3rem;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _score_class(score: float) -> str:
    if score >= 0.7:
        return "score-high"
    if score >= 0.4:
        return "score-mid"
    return "score-low"


def _is_demo_mode() -> bool:
    return not bool(settings.groq_api_key)


def _system_status() -> str:
    llm_ok = bool(settings.groq_api_key)
    luma_ok = bool(settings.luma_api_key)
    eb_ok = bool(settings.eventbrite_api_key)
    gp_ok = bool(settings.google_places_api_key)
    tm_ok = bool(settings.ticketmaster_api_key)
    yelp_ok = bool(settings.yelp_api_key)
    sg_ok = bool(settings.seatgeek_client_id)
    sources_live = sum([luma_ok, eb_ok, gp_ok, tm_ok, yelp_ok, sg_ok])

    from knowledge.cognee_engine import COGNEE_AVAILABLE
    tw = get_integration()
    db_ok = db_is_available()

    def _dot(ok: bool) -> str:
        return '<span class="status-dot dot-green"></span>' if ok else '<span class="status-dot dot-yellow"></span>'

    return (
        f'<div class="status-bar">'
        f'<span>{_dot(llm_ok)} LLM (Qwen3-32B): {"Live" if llm_ok else "Demo"}</span>'
        f'<span>{_dot(sources_live > 0)} Sources: {sources_live}/6 connected</span>'
        f'<span>{_dot(COGNEE_AVAILABLE)} Cognee: {"Active" if COGNEE_AVAILABLE else "Fallback"}</span>'
        f'<span>{_dot(not tw.is_mock)} Triggers: {"Live" if not tw.is_mock else "Mock"}</span>'
        f'<span>{_dot(db_ok)} DB: {"Supabase" if db_ok else "In-Memory"}</span>'
        f'</div>'
    )


CATEGORIES = [
    ("All Events", None),
    ("Nightlife", ["nightclub", "dance", "rave", "edm"]),
    ("Live Music", ["live-music", "jazz", "concert"]),
    ("Tech Meetup", ["tech-meetup", "startup", "hackathon"]),
    ("Comedy", ["comedy"]),
    ("Food & Drink", ["food-festival", "gastropub", "fine-dining", "craft-beer", "wine-tasting"]),
    ("Art & Culture", ["art", "gallery", "museum", "opera", "classical"]),
    ("Networking", ["networking", "happy-hour"]),
    ("Rooftop", ["rooftop"]),
    ("Gaming", ["gaming", "esports"]),
]


# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------

if "plan" not in st.session_state:
    st.session_state.plan = None
if "scored_events" not in st.session_state:
    st.session_state.scored_events = None
if "saved_plans" not in st.session_state:
    st.session_state.saved_plans = []
if "active_category" not in st.session_state:
    st.session_state.active_category = "All Events"
if "show_graph" not in st.session_state:
    st.session_state.show_graph = False
if "user_kbs" not in st.session_state:
    st.session_state.user_kbs = {}
if "user_id" not in st.session_state:
    import uuid
    st.session_state.user_id = str(uuid.uuid4())[:8]

# Restore user KB: try Supabase first, fall back to session state
_uid = st.session_state.user_id
if _uid not in st.session_state.get("user_kbs", {}):
    _db_kb = loop.run_until_complete(load_user_kb(_uid))
    if _db_kb:
        st.session_state.user_kbs[_uid] = _db_kb

_persisted_kbs = st.session_state.get("user_kbs", {})
for _uid, _kb_data in _persisted_kbs.items():
    restore_user_kb(_uid, _kb_data)


# ---------------------------------------------------------------------------
# Hero header
# ---------------------------------------------------------------------------

st.markdown('<p class="hero-title">🎉 eventlocal</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="hero-subtitle">'
    'Your city knows what\'s happening tonight. '
    'AI-powered event discovery that understands your vibe.'
    '</p>',
    unsafe_allow_html=True,
)

# System status bar
st.markdown(_system_status(), unsafe_allow_html=True)

# Demo mode banner
if _is_demo_mode():
    st.markdown(
        '<div class="demo-banner">'
        '🧪 <strong>Demo Mode</strong> — Running with sample Bay Area events and template-based plans. '
        'Set API keys in your environment to unlock live data and AI-generated itineraries.'
        '</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Sidebar — Profile controls
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Your Profile")

    age = st.slider(
        "Your Age",
        min_value=13,
        max_value=80,
        value=28,
        help="We personalize events to your age bracket",
    )

    bracket_labels = {
        range(0, 21): "🎮 Under 21 — All-ages events, gaming, cafes",
        range(21, 30): "🍸 Twenties — Nightlife, rooftops, meetups",
        range(30, 40): "🍷 Thirties — Cocktail bars, live music, comedy",
        range(40, 50): "🎭 Forties — Jazz, theater, wine, fine dining",
        range(50, 101): "🎵 50+ — Classical, opera, cultural events",
    }
    for age_range, label in bracket_labels.items():
        if age in age_range:
            st.caption(label)
            break

    st.divider()

    social_mode = st.radio(
        "Going out...",
        ["Solo", "Group", "Date"],
        horizontal=True,
        help="Adjusts venue recommendations",
    )

    st.divider()

    city = st.selectbox("City", ["bay-area"], index=0)
    date = st.date_input("Date")
    date_str = date.isoformat() if date else "today"

    st.divider()
    st.caption("Powered by Cognee + Qwen3-32B")
    st.caption("Built for Company Brain Hackathon 2026")

    if st.button("🧠 Knowledge Graph View"):
        st.session_state.show_graph = not st.session_state.show_graph


# ---------------------------------------------------------------------------
# Category chips
# ---------------------------------------------------------------------------

cols = st.columns(len(CATEGORIES))
for i, (label, _tags) in enumerate(CATEGORIES):
    with cols[i]:
        if st.button(label, key=f"cat_{i}", use_container_width=True):
            st.session_state.active_category = label


# ---------------------------------------------------------------------------
# Discover button
# ---------------------------------------------------------------------------

if st.button("🔍 Discover My Evening", type="primary", use_container_width=True):
    profile = UserProfile(age=age, social_mode=social_mode.lower())
    uid = st.session_state.user_id

    with st.spinner("Building your personalized plan..."):
        try:
            plan = asyncio.run(
                discover_events(profile=profile, date=date_str, city=city, user_id=uid)
            )
            st.session_state.plan = plan
            st.session_state.scored_events = plan.events
            # Persist user KB to session state + Supabase
            st.session_state.user_kbs = export_all_kbs()
            for _persist_uid, _persist_data in st.session_state.user_kbs.items():
                loop.run_until_complete(save_user_kb(_persist_uid, _persist_data))
        except Exception as exc:
            st.error(f"Something went wrong: {exc}")


# ---------------------------------------------------------------------------
# Main content area
# ---------------------------------------------------------------------------

if st.session_state.show_graph:
    # Live knowledge graph visualization built from actual event data
    st.markdown("### Knowledge Graph")

    graph_events = st.session_state.scored_events or get_sample_events()
    venues: dict[str, list[str]] = {}
    tag_edges: list[tuple[str, str]] = []
    all_tags: set[str] = set()

    for ev in graph_events:
        vname = ev.venue_name or ev.source
        venues.setdefault(vname, []).append(ev.title)
        all_tags.update(ev.tags)

    # Build graphviz DOT source
    dot_lines = [
        'digraph EventBrain {',
        '  bgcolor="#0e1117";',
        '  node [style=filled, fontcolor=white, fontsize=10];',
        '  edge [color="#4b5563"];',
        '  rankdir=LR;',
    ]

    # Venue nodes
    for vname in venues:
        safe = vname.replace('"', '\\"')
        dot_lines.append(f'  "{safe}" [shape=house, fillcolor="#1e3a5f", label="{safe}"];')

    # Event nodes + HOSTED_AT edges
    for ev in graph_events[:20]:
        eid = ev.title[:30].replace('"', '\\"')
        sc_color = "#065f46" if ev.composite_score >= 0.7 else "#78350f" if ev.composite_score >= 0.4 else "#7f1d1d"
        dot_lines.append(f'  "{eid}" [shape=box, fillcolor="{sc_color}", label="{eid}"];')
        vname = (ev.venue_name or ev.source).replace('"', '\\"')
        dot_lines.append(f'  "{eid}" -> "{vname}" [label="hosted_at", fontsize=8, fontcolor="#6b7280"];')

    # Tag cluster nodes (top 10 tags)
    from collections import Counter
    tag_counts = Counter(t for ev in graph_events for t in ev.tags)
    top_tags = [t for t, _ in tag_counts.most_common(10)]
    for tag in top_tags:
        safe = tag.replace('"', '\\"')
        dot_lines.append(f'  "tag:{safe}" [shape=ellipse, fillcolor="#2d1b69", label="{safe}"];')

    # Event→Tag edges
    for ev in graph_events[:20]:
        eid = ev.title[:30].replace('"', '\\"')
        for tag in ev.tags:
            if tag in top_tags:
                safe = tag.replace('"', '\\"')
                dot_lines.append(f'  "{eid}" -> "tag:{safe}" [style=dashed, color="#374151"];')

    dot_lines.append('}')
    dot_source = '\n'.join(dot_lines)

    st.graphviz_chart(dot_source, use_container_width=True)

    # Live stats from actual data
    unique_venues = len(venues)
    unique_tags = len(all_tags)
    event_count = len(graph_events)
    edges = event_count + sum(len(ev.tags) for ev in graph_events[:20])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Events Indexed", event_count)
    col2.metric("Venues", unique_venues)
    col3.metric("Tags", unique_tags)
    col4.metric("Graph Edges", edges)

    # User KB stats
    uid = st.session_state.user_id
    user_kb = get_user_kb(uid)
    if user_kb.query_history or user_kb.feedback:
        st.markdown("#### Your Personal Knowledge Base")
        kb_c1, kb_c2, kb_c3 = st.columns(3)
        kb_c1.metric("Queries", len(user_kb.query_history))
        kb_c2.metric("Feedback Signals", len(user_kb.feedback))
        kb_c3.metric("Learned Tags", len(user_kb.preferred_tags) + len(user_kb.avoided_tags))

    # TriggerWare status
    tw = get_integration()
    tw_status = asyncio.run(tw.status())
    st.markdown("#### TriggerWare Status")
    tw_c1, tw_c2, tw_c3 = st.columns(3)
    tw_c1.metric("Mode", tw_status["mode"].title())
    tw_c2.metric("Triggers", tw_status["triggers_registered"])
    tw_c3.metric("Deltas Processed", tw_status["deltas_processed"])
    if tw_status["trigger_names"]:
        st.caption(f"Active triggers: {', '.join(tw_status['trigger_names'])}")

else:
    # --- Scored events section ---
    events_to_show = st.session_state.scored_events
    if events_to_show is None:
        from agents.layers.age_layer import apply_age_scores
        preview_profile = UserProfile(age=age, social_mode=social_mode.lower())
        preview_events = get_sample_events(city, date_str)
        events_to_show = apply_age_scores(preview_events, preview_profile)

    # Filter by category
    active_cat = st.session_state.active_category
    active_tags = None
    for label, tags in CATEGORIES:
        if label == active_cat:
            active_tags = tags
            break

    if active_tags:
        filtered = [e for e in events_to_show if any(t in e.tags for t in active_tags)]
    else:
        filtered = events_to_show

    st.markdown(f"### Tonight in {city.replace('-', ' ').title()}")
    st.caption(f"{len(filtered)} events scored for you")

    # Event cards grid
    source_icons = {
        "luma": "🟣", "eventbrite": "🟠", "google_places": "📍",
        "ticketmaster": "🎫", "yelp": "⭐", "seatgeek": "🎟️",
    }
    cols_per_row = 3
    for row_start in range(0, len(filtered), cols_per_row):
        cols = st.columns(cols_per_row)
        for col_idx, ev in enumerate(filtered[row_start : row_start + cols_per_row]):
            with cols[col_idx]:
                sc = _score_class(ev.composite_score)
                icon = source_icons.get(ev.source, "📌")
                st.markdown(
                    f'<div class="event-card">'
                    f'<div class="event-title">{ev.title}</div>'
                    f'<div class="event-venue">{icon} {ev.venue_name or ev.source}</div>'
                    f'<div class="event-meta">'
                    f'<span class="score-badge {sc}">{ev.composite_score:.0%} match</span>'
                    f'<span title="Age: {ev.age_score:.0%} | Social: {ev.social_score:.0%}">🎯 {ev.age_score:.0%} / 👥 {ev.social_score:.0%}</span>'
                    f'<span>{ev.price or "Price TBD"}</span>'
                    f'<span>{ev.start_time[11:16] if len(ev.start_time) > 11 else ""}</span>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # --- Evening plan section ---
    st.markdown("---")
    st.markdown("### Your Evening Plan")

    if st.session_state.plan:
        plan = st.session_state.plan
        st.markdown(
            f"*AI-generated itinerary based on your age bracket and event scores*"
        )
        st.markdown(plan.itinerary_markdown)

        if st.button("💾 Save This Plan"):
            st.session_state.saved_plans.append(
                {"date": plan.date, "city": plan.city, "md": plan.itinerary_markdown}
            )
            st.success("Plan saved!")
    else:
        st.info(
            "Hit **Discover My Evening** above to generate a personalized itinerary."
        )


# ---------------------------------------------------------------------------
# Saved plans section
# ---------------------------------------------------------------------------

st.markdown("---")
st.markdown("### Your evening plans")

if st.session_state.saved_plans:
    for i, sp in enumerate(reversed(st.session_state.saved_plans)):
        with st.expander(f"Plan for {sp['city']} — {sp['date']}"):
            st.markdown(sp["md"])
else:
    st.markdown(
        '<div class="event-card" style="text-align:center; padding:2rem;">'
        '<div style="font-size:2rem; margin-bottom:0.5rem;">📋</div>'
        '<div style="color:#9ca3af;">No saved plans yet. Discover events and generate a plan to get started.</div>'
        '</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# How eventlocal works — 4-step cards
# ---------------------------------------------------------------------------

st.markdown("---")
st.markdown("### How eventlocal works")
st.caption(
    "We treat your city's event ecosystem like a company knowledge base "
    "— connected, searchable, and personalized to you."
)

steps = [
    ("📡", "Step 1", "Aggregate", "Events from 6 sources: Luma, Eventbrite, Google Places, Ticketmaster, Yelp, SeatGeek"),
    ("🧠", "Step 2", "Cognify", "Cognee builds a knowledge graph connecting events, venues, reviews and patterns"),
    ("🎯", "Step 3", "Personalize", "Each event scored by age bracket + social mode (solo/group/date), blended 70/30"),
    ("🌃", "Step 4", "Plan", "AI builds your complete evening: dinner → pre-game → main event → late night"),
]

step_cols = st.columns(4)
for i, (icon, label, title, desc) in enumerate(steps):
    with step_cols[i]:
        st.markdown(
            f'<div class="step-card">'
            f'<div class="step-icon">{icon}</div>'
            f'<div class="step-label">{label}</div>'
            f'<div class="step-title">{title}</div>'
            f'<div class="step-desc">{desc}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Event Brain concept table
# ---------------------------------------------------------------------------

st.markdown("---")
st.markdown("### The Event Brain Concept")
st.caption("eventlocal maps event ecosystems to company knowledge — here's the analogy")

st.markdown(
    '<table class="comparison-table">'
    '<tr><th>Company Brain</th><th>Event Brain</th></tr>'
    '<tr><td>Company docs</td><td>Event listings</td></tr>'
    '<tr><td>Meeting notes</td><td>Venue reviews</td></tr>'
    '<tr><td>Employee directory</td><td>Venue + promoter network</td></tr>'
    '<tr><td>FAQ knowledge base</td><td>Event patterns</td></tr>'
    '<tr><td>Onboarding guide</td><td>Personalized planner</td></tr>'
    '</table>',
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown(
    '<div class="footer">'
    'eventlocal — Your city\'s Event Brain · Built for Company Brain Hackathon 2026<br>'
    '<span style="color:#4b5563;">Powered by Cognee (Knowledge Graph) + Qwen3-32B (Groq)</span>'
    '</div>',
    unsafe_allow_html=True,
)
