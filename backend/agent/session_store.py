"""
In-memory session store for Milestone 3 Conversational Advisor.

Stores validation pipeline outputs and running chat transcripts keyed by unique sessionId.
Follows zero-database lightweight state management pattern.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# In-memory session store: dict[session_id, session_data]
_SESSIONS: Dict[str, Dict[str, Any]] = {}


def create_session(pipeline_output: Dict[str, Any]) -> str:
    """Create a new validation session and return a unique sessionId."""
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    _SESSIONS[session_id] = {
        "sessionId": session_id,
        "idea": pipeline_output.get("idea", ""),
        "targetCustomer": pipeline_output.get("targetCustomer", ""),
        "problem": pipeline_output.get("problem", ""),
        "summary": pipeline_output.get("summary", ""),
        "opportunityScore": pipeline_output.get("opportunityScore"),
        "marketOpportunity": pipeline_output.get("marketOpportunity"),
        "competitors": pipeline_output.get("competitors"),
        "whiteSpace": pipeline_output.get("whiteSpace"),
        "swot": pipeline_output.get("swot"),
        "mvp": pipeline_output.get("mvp"),
        "gtm": pipeline_output.get("gtm"),
        "transcript": [],  # List of {"role": "user"|"advisor", "content": "..."}
    }
    logger.info("Created session %s", session_id)
    return session_id


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve session data by sessionId."""
    return _SESSIONS.get(session_id)


def add_chat_turn(session_id: str, role: str, content: str) -> None:
    """Add a message turn to the session chat transcript."""
    session = _SESSIONS.get(session_id)
    if session:
        session["transcript"].append({"role": role, "content": content})
