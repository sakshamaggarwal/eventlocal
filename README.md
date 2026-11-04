# eventlocal — Your City's Event Brain 🎉🧠

> Personalized event discovery platform powered by a knowledge graph (Cognee) and open-source AI (Qwen3-32B).

**Built for the Company Brain Hackathon 2026** — TechEquity AI @ Snowflake SVAI Hub, Menlo Park

## What is eventlocal?

eventlocal is an **Event Brain** — it treats a city's event ecosystem like a company's internal knowledge base:

| Company Brain | Event Brain (eventlocal) |
|---|---|
| Company docs | Event listings (Luma, Eventbrite) |
| Meeting notes | Venue reviews & crowd reports |
| Employee directory | Venue database + promoter network |
| FAQ knowledge base | Event patterns & recommendations |
| Onboarding guide | Personalized evening planner |

The platform aggregates events from multiple sources, builds a knowledge graph of venues/reviews/patterns using **Cognee**, and generates personalized evening plans through **Qwen3-32B** (via Groq).

## Architecture

```
User (age slider) → Streamlit UI
                         ↓
                    FastAPI Backend
                         ↓
         ┌───────────────┼───────────────┐
         ↓               ↓               ↓
    Luma API      Eventbrite API   Google Places API
         └───────────────┼───────────────┘
                         ↓
                  Cognee (Knowledge Graph)
                    cognee.add() → cognee.cognify()
                         ↓
                  Age Personalization Layer
                    (score 0-1 per event)
                         ↓
                  Qwen3-32B via Groq
                    (itinerary generation)
                         ↓
                  Evening Plan 🌃
```

## Hackathon MVP

- **1 personalization layer**: Age bracket slider (under 21 / 20s / 30s / 40s / 50+)
- **3 event sources**: Luma, Eventbrite, Google Places (flexible — can swap)
- **1 city**: Bay Area
- **Knowledge graph**: Cognee builds relationships between events, venues, reviews
- **LLM**: Qwen3-32B on Groq (free tier, ~100 tok/s)

## Quick Start

```bash
# 1. Clone
git clone https://github.com/sakshamtech12-org/eventlocal.git
cd eventlocal

# 2. Install
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env — at minimum set GROQ_API_KEY (free from console.groq.com)

# 4a. Run Streamlit UI (hackathon demo)
streamlit run app/streamlit_app.py

# 4b. Or run FastAPI backend
python -m app.main
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

## Project Structure

```
eventlocal/
├── app/
│   ├── main.py              # FastAPI app
│   ├── streamlit_app.py     # Streamlit demo UI
│   ├── config.py            # Settings from .env
│   └── llm.py               # Groq/Qwen3 client
├── agents/
│   ├── master_agent.py      # Orchestrator — fetch → cognify → score → plan
│   ├── planner_agent.py     # LLM-powered itinerary builder
│   └── layers/
│       └── age_layer.py     # Age personalization (MVP layer)
├── sources/
│   ├── base.py              # Abstract EventSource
│   ├── luma_client.py       # Luma API
│   ├── eventbrite_client.py # Eventbrite API
│   └── google_places_client.py  # Google Places API + reviews
├── knowledge/
│   └── cognee_engine.py     # Cognee knowledge graph wrapper
├── models/
│   └── user_profile.py      # Pydantic models
├── tests/
│   └── test_age_layer.py    # Age layer unit tests
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

## Post-Hackathon Roadmap

- **More personalization layers**: Solo/group, local/traveling, networking/party, relationship status, cultural affinity
- **More cities**: Seattle, NYC, LA, Austin
- **More sources**: Partiful (scrape), Meetup (GraphQL), venue Instagram, Sulekha/EventMozo
- **React frontend**: Replace Streamlit with production React UI
- **User accounts**: Firestore, saved preferences, plan history
- **Deployment**: GCP Cloud Run (sakshamtech12-org project)

## Tech Stack

| Component | Technology |
|---|---|
| LLM | Qwen3-32B via Groq (free) |
| Knowledge Graph | Cognee (GraphRAG) |
| Backend | FastAPI + Python 3.12 |
| Frontend (MVP) | Streamlit |
| Frontend (Prod) | React |
| Event Sources | Luma, Eventbrite, Google Places |
| Deployment | Docker → GCP Cloud Run |

---

*Built by Saksham Aggarwal — eventlocal is an Event Brain that knows your city's nightlife.*
