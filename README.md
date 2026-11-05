# eventlocal — Your City's Event Brain 🎉🧠

> AI-powered event discovery that understands your vibe. We aggregate events, build a knowledge graph, and plan your perfect evening.

**Built for the Company Brain Hackathon 2026** — TechEquity AI @ Snowflake SVAI Hub, Menlo Park (Nov 3–6)

## What is eventlocal?

eventlocal is an **Event Brain** — it treats a city's event ecosystem like a company's internal knowledge base:

| Company Brain | Event Brain (eventlocal) |
|---|---|
| Company docs | Event listings (Luma, Eventbrite, Google Places) |
| Meeting notes | Venue reviews & crowd reports |
| Employee directory | Venue database + promoter network |
| FAQ knowledge base | Event patterns & recommendations |
| Onboarding guide | Personalized evening planner |

## Architecture

```
User (age slider + social mode) → Streamlit UI
                                      ↓
                                 Master Agent
                                      ↓
                  ┌───────────────────┼───────────────────┐
                  ↓                   ↓                   ↓
             Luma API          Eventbrite API       Google Places API
                  │             (or sample data in demo mode)            │
                  └───────────────────┼───────────────────┘
                                      ↓
                        Two-Tier Cognee Knowledge Graph
                          ├─ Global KB (events/venues/reviews)
                          └─ Per-User KB (preferences/feedback)
                                      ↓
                            Custom Ontology (4 entities, 15 rels)
                                      ↓
                           Age Personalization Layer (score 0-1)
                                      ↓
                         Qwen3-32B via Groq (or template fallback)
                                      ↓
                              Evening Plan 🌃
```

## Features

### Demo Mode (Zero API Keys)
The app runs end-to-end with **no API keys required**:
- **16 curated Bay Area sample events** from all 3 sources (Luma, Eventbrite, Google Places)
- **Template-based itinerary generation** with rule-based venue selection
- **Full age personalization** — scoring works on sample data

### Live Mode (With API Keys)
Set keys incrementally — each one unlocks more:
- `GROQ_API_KEY` → AI-generated itineraries via Qwen3-32B
- `LUMA_API_KEY` → Live Luma events
- `EVENTBRITE_API_KEY` → Live Eventbrite events
- `GOOGLE_PLACES_API_KEY` → Live Google Places venues + reviews

### Knowledge Graph (Cognee)
- **Two-tier architecture**: Global KB (shared events/venues/reviews) + per-user local KB (preferences/feedback)
- **Custom ontology**: 4 entity types (Event, Venue, Review, Pattern), 15 named relationships
- **6 multi-hop query templates**: age_personalized, solo_friendly, date_night, group_outing, hidden_gems, neighborhood_crawl

### TriggerWare Integration
Event monitoring with 5 trigger types:
- `new_events` — New events matching criteria
- `price_drop` — Price changes on tracked events
- `trending` — Events gaining traction
- `venue_update` — Venue changes (hours, capacity)
- `sold_out` — Sellout alerts for watchlisted events

### Personalization
- **Age bracket scoring** (MVP): Under 21 / 20s / 30s / 40s / 50+ with keyword-based 0-1 scoring
- **Social mode toggle**: Solo / Group / Date
- **Event Concierge** system prompt (289 lines) guiding the LLM's personality and recommendations

### UI (Streamlit)
- Dark theme with gradient accents
- Category filter chips (Nightlife, Live Music, Tech Meetup, Comedy, etc.)
- Scored event cards with match percentage
- AI-generated evening plan
- Saved plans
- Knowledge graph view
- System status indicators
- "How it works" 4-step cards
- Event Brain concept comparison table

## Quick Start

```bash
# 1. Clone
git clone https://github.com/sakshamaggarwal/eventlocal.git
cd eventlocal

# 2. Install
pip install -r requirements.txt

# 3. Run (works immediately — no API keys needed for demo mode)
streamlit run app/streamlit_app.py

# 4. (Optional) Configure live APIs
cp .env.example .env
# Get a free API key from console.groq.com and add to .env
```

## API

```bash
# Health check
curl http://localhost:8000/health

# Get personalized plan
curl -X POST http://localhost:8000/discover \
  -H "Content-Type: application/json" \
  -d '{"age": 28, "date": "2026-11-05", "city": "bay-area"}'
```

## Testing

```bash
pytest tests/ -v
```

## Project Structure

```
eventlocal/
├── app/
│   ├── main.py                 # FastAPI app (API mode)
│   ├── streamlit_app.py        # Streamlit UI (primary demo interface)
│   ├── config.py               # Settings from .env
│   ├── llm.py                  # Groq/Qwen3-32B client
│   └── prompts.py              # System prompt loader (with fallback chain)
├── agents/
│   ├── master_agent.py         # Orchestrator — fetch → cognify → score → plan
│   ├── planner_agent.py        # LLM itinerary builder + template fallback
│   └── layers/
│       └── age_layer.py        # Age personalization (MVP layer)
├── config/
│   ├── __init__.py             # Proprietary config loader (fallback chain)
│   └── proprietary_defaults.py # Generic stubs (public — app runs with these)
├── sources/
│   ├── base.py                 # Abstract EventSource
│   ├── luma_client.py          # Luma API
│   ├── eventbrite_client.py    # Eventbrite API
│   ├── google_places_client.py # Google Places API + reviews
│   └── sample_data.py          # 16 curated Bay Area events (demo mode)
├── knowledge/
│   ├── cognee_engine.py        # Two-tier Cognee knowledge graph
│   └── ontology.py             # Custom ontology (4 entities, 15 rels)
├── triggers/
│   ├── client.py               # TriggerWare integration (mock + live)
│   └── definitions.py          # 5 trigger definitions
├── models/
│   └── user_profile.py         # Pydantic models (UserProfile, Event, EveningPlan)
├── tests/
│   ├── test_age_layer.py       # Age scoring unit tests (6)
│   ├── test_cognee_engine.py   # Two-tier KB tests (27)
│   ├── test_ontology.py        # Ontology tests (21)
│   ├── test_triggers.py        # TriggerWare tests (35)
│   ├── test_sample_data.py     # Sample data validation (7)
│   └── test_pipeline.py        # End-to-end demo pipeline tests (7)
├── system-prompt.example.md    # Placeholder Event Concierge prompt (public)
├── .streamlit/config.toml      # Streamlit dark theme config
├── requirements.txt
├── runtime.txt                 # Python version for Streamlit Cloud
├── Dockerfile
├── .env.example
└── README.md
```

## Privacy & Proprietary Config

The public repo ships with **generic stubs** — the app runs, but uses simplified parameters. For the full tuned experience, add two private files:

| File | What it contains |
|---|---|
| `config/proprietary.py` | Tuned age signals, scoring weights, KB weights, ontology prompt, query templates |
| `system-prompt.md` | Full 289-line Event Concierge system prompt |

See [LAUNCH-GUIDE.md](LAUNCH-GUIDE.md) for exact steps.

## Tech Stack

| Component | Technology |
|---|---|
| LLM | Qwen3-32B via Groq (free tier) |
| Knowledge Graph | Cognee (GraphRAG) — two-tier architecture |
| Backend | FastAPI + Python 3.12 |
| Frontend (MVP) | Streamlit |
| Event Sources | Luma, Eventbrite, Google Places |
| Monitoring | TriggerWare (mock + live backends) |
| Deployment | Streamlit Community Cloud (primary) / Docker |

## Hackathon MVP Scope

- **1 personalization layer**: Age bracket slider (+ social mode toggle)
- **3 event sources**: Luma, Eventbrite, Google Places
- **1 city**: Bay Area
- **Demo mode**: Works with zero API keys; keys unlock features incrementally

---

*Built by Saksham Aggarwal — eventlocal is an Event Brain that knows your city's nightlife.*
