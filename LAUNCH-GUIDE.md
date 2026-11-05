# eventlocal — Launch Guide

How to go from a public clone to a fully tuned deployment.

## Quick Start (Demo Mode)

The app works immediately with zero configuration:

```bash
git clone https://github.com/sakshamaggarwal/eventlocal.git
cd eventlocal
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

This runs with generic stubs and 16 sample events — good for demos and judging.

## Full Launch (Tuned Mode)

To run with the full tuned parameters, add two files that are not in the public repo:

### Step 1: Add `config/proprietary.py`

Create `config/proprietary.py` with these exports:

```python
AGE_SIGNALS: dict[str, dict]          # boost/penalize keywords per age bracket
SCORING_BASE: float                    # base score (default: 0.5)
SCORING_BOOST: float                   # per-keyword boost (default: 0.1)
SCORING_PENALIZE: float                # per-keyword penalty (default: 0.1)
KB_USER_WEIGHT: float                  # user KB merge weight (default: 1.5)
KB_GLOBAL_WEIGHT: float                # global KB merge weight (default: 1.0)
FEEDBACK_CHOSEN_WEIGHT: float          # weight for chosen events (default: 0.1)
FEEDBACK_RATED_MULTIPLIER: float       # multiplier for rated events (default: 0.05)
FEEDBACK_SKIPPED_WEIGHT: float         # weight for skipped events (default: -0.05)
ONTOLOGY_EXTRACTION_PROMPT: str        # full Cognee extraction prompt
QUERY_TEMPLATES: dict[str, str]        # 6 multi-hop query templates
```

The `config/__init__.py` loader will automatically pick it up over the defaults.

### Step 2: Add `system-prompt.md`

Place the full Event Concierge system prompt (289 lines) at the repo root as `system-prompt.md`. The `app/prompts.py` loader checks for it first, falling back to `system-prompt.example.md`.

### Step 3: (Optional) Add API keys

```bash
cp .env.example .env
# Edit .env with your keys:
# GROQ_API_KEY=...          → AI-generated itineraries
# LUMA_API_KEY=...          → Live Luma events
# EVENTBRITE_API_KEY=...    → Live Eventbrite events
# GOOGLE_PLACES_API_KEY=... → Live venues + reviews
```

### Step 4: Run

```bash
streamlit run app/streamlit_app.py
```

Or with Docker:

```bash
docker build -t eventlocal .
docker run -p 8501:8501 --env-file .env eventlocal
```

## How the Fallback Works

```
config/__init__.py tries:
  1. config/proprietary.py  (full tuned values — gitignored)
  2. config/proprietary_defaults.py  (generic stubs — in repo)

app/prompts.py tries:
  1. system-prompt.md  (full prompt — gitignored)
  2. system-prompt.example.md  (placeholder — in repo)
  3. Inline default  ("You are an event discovery assistant...")
```

The `PROPRIETARY_LOADED` flag (importable from `config`) tells you which tier is active.

## Deploy to Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with GitHub
3. Click **New app** → select `sakshamaggarwal/eventlocal`, branch `main`, file `app/streamlit_app.py`
4. In **Advanced settings > Secrets**, add your API keys and optionally paste `config/proprietary.py` content
5. Click **Deploy!**

## Files Summary

| File | In repo? | Purpose |
|---|---|---|
| `config/proprietary_defaults.py` | Yes | Generic stubs — app runs with these |
| `config/proprietary.py` | No (gitignored) | Full tuned parameters |
| `system-prompt.example.md` | Yes | Placeholder prompt (25 lines) |
| `system-prompt.md` | No (gitignored) | Full Event Concierge prompt (289 lines) |
| `.env` | No (gitignored) | API keys |

---

*Built by Saksham Aggarwal for the Company Brain Hackathon 2026*
