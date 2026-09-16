"""
Conversational Startup Advisor Graph for Milestone 3.

Executes multi-turn follow-up chat conversations using validation context
and retrieved market insights.
"""

import logging
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from .llm import get_llm, kickoff_with_fallback
from .output_guard import strip_reasoning
from .session_store import add_chat_turn, get_session

logger = logging.getLogger(__name__)


class ChatState(TypedDict, total=False):
    sessionId: str
    message: str
    sessionData: Dict[str, Any]
    reply: str
    error: str


def advisor_respond(session_id: str, message: str) -> Dict[str, Any]:
    """Generate a conversational response for the user's follow-up question."""
    session = get_session(session_id)
    if not session:
        return {"error": "Session not found or expired.", "reply": "Session not found."}

    idea = session.get("idea", "")
    target = session.get("targetCustomer", "")
    problem = session.get("problem", "")
    score = (session.get("opportunityScore") or {}).get("score", "N/A")
    market = session.get("marketOpportunity") or {}
    competitors = (session.get("competitors") or {}).get("competitors") or []
    swot = session.get("swot") or {}
    mvp = session.get("mvp") or {}
    gtm = session.get("gtm") or {}
    transcript = session.get("transcript") or []

    # Format conversation history
    history_str = "\n".join([f"{t['role'].capitalize()}: {t['content']}" for t in transcript[-4:]])
    if not history_str:
        history_str = "No prior messages."

    # Format competitor names
    comp_names = ", ".join([c.get("name", "") for c in competitors[:4] if c.get("name")]) or "None identified"

    # Save user message to transcript
    add_chat_turn(session_id, "user", message)

    prompt = f"""You are Affinity, an expert AI Startup Advisor and Market Validation Analyst.
Answer the founder's question concisely based on their validation dossier.

STARTUP DOSSIER CONTEXT:
- Idea: {idea}
- Target Customer: {target}
- Problem: {problem}
- Opportunity Score: {score}/100
- Market Size & Growth: {market.get('marketSize', 'N/A')} ({market.get('cagr', 'N/A')})
- Discovered Competitors: {comp_names}
- SWOT Summary: {swot.get('summary', 'N/A')}
- GTM Positioning: {gtm.get('positioning', 'N/A')}

RECENT CHAT HISTORY:
{history_str}

USER QUESTION:
"{message}"

Provide a direct, encouraging, highly actionable response in 2-3 short paragraphs:"""

    try:
        llm_obj = get_llm()
        if hasattr(llm_obj, "call"):
            raw_reply = llm_obj.call([{"role": "user", "content": prompt}])
        elif hasattr(llm_obj, "invoke"):
            raw_reply = llm_obj.invoke(prompt)
        else:
            from litellm import completion
            res = completion(model=str(llm_obj), messages=[{"role": "user", "content": prompt}])
            raw_reply = res.choices[0].message.content
        reply = strip_reasoning(str(raw_reply))
        if not reply:
            reply = f"Based on your dossier for '{idea}', focus on your core target audience ({target}) and early wedge features."
    except Exception as exc:
        logger.exception("[chat_agent] LLM call failed")
        reply = f"Regarding '{idea}': Focus on validating customer pain points with a small targeted MVP before scaling marketing spend."

    # Save advisor reply to transcript
    add_chat_turn(session_id, "advisor", reply)

    return {"sessionId": session_id, "reply": reply}
