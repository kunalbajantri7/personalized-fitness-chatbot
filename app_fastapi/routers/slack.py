from fastapi import APIRouter, Request
from backend.app import slack_events, slack_interactive

router = APIRouter(prefix="/slack", tags=["Slack"])


# ---------------- SLACK EVENTS ----------------

@router.post("/events")
async def events(request: Request):
    """
    Forward Slack event requests to the main chatbot logic in app.py
    """
    return await slack_events(request)


# ---------------- SLACK INTERACTIVE BUTTONS ----------------

@router.post("/interactive")
async def interactive(request: Request):
    """
    Forward Slack button interactions to app.py
    """
    return await slack_interactive(request)