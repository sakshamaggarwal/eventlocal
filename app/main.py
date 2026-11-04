"""
eventlocal — FastAPI backend.

POST /discover  →  personalized evening plan
GET  /health    →  service status
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agents.master_agent import discover_events
from models.user_profile import UserProfile

app = FastAPI(
    title="eventlocal",
    description="Personalized event discovery powered by Cognee + Qwen3",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class DiscoverRequest(BaseModel):
    age: int = Field(ge=13, le=100, description="User's age for personalization")
    date: str = Field(default="today", description="Date to plan for (YYYY-MM-DD or 'today')")
    city: str = Field(default="bay-area", description="City to search in")


class DiscoverResponse(BaseModel):
    itinerary: str
    event_count: int
    explanation: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "service": "eventlocal", "version": "0.1.0"}


@app.post("/discover", response_model=DiscoverResponse)
async def discover(req: DiscoverRequest):
    """Generate a personalized evening plan."""
    profile = UserProfile(age=req.age)
    plan = await discover_events(profile=profile, date=req.date, city=req.city)

    return DiscoverResponse(
        itinerary=plan.itinerary_markdown,
        event_count=len(plan.events),
        explanation=plan.explanation,
    )


# ---------------------------------------------------------------------------
# Run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    from app.config import settings
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.app_port, reload=True)
