import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent.search_agent import SearchAgentError, search_market

load_dotenv()

app = FastAPI(title="AI Startup Idea Validator API")

frontend_origin = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)


class ValidateRequest(BaseModel):
    idea: str
    targetCustomer: str = ""
    problem: str = ""


@app.post("/validate")
def validate_idea(payload: ValidateRequest):
    if not payload.idea.strip():
        return JSONResponse(status_code=400, content={"error": "idea is required"})

    try:
        result = search_market(payload.idea, payload.targetCustomer, payload.problem)
    except SearchAgentError as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})

    return result


@app.get("/health")
def health():
    return {"status": "ok"}
