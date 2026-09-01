import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent.graph import pipeline

load_dotenv()

app = FastAPI(title="Affinity API")

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

    state = pipeline.invoke(
        {
            "idea": payload.idea,
            "targetCustomer": payload.targetCustomer,
            "problem": payload.problem,
        }
    )

    if state.get("error"):
        return JSONResponse(status_code=502, content={"error": state["error"]})

    return {
        "summary": state["summary"],
        "results": state["results"],
        "marketOpportunity": state.get("marketOpportunity"),
    }


@app.get("/health")
def health():
    return {"status": "ok"}
