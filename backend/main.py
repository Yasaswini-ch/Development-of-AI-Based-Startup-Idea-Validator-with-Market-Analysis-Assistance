import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent.tools import run_web_search
#from agent.graph import pipeline

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
    result = run_web_search(payload.idea, payload.targetCustomer, payload.problem)

    if result.get("error"):
        return JSONResponse(status_code=502, content={"error": result["error"]})

    return {"summary": result["summary"], "results": result["results"]}

    return {"summary": state["summary"], "results": state["results"]}


@app.get("/health")
def health():
    return {"status": "ok"}
