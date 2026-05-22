import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sdk.guard import Guard
from datetime import datetime

app = FastAPI(
    title="LLMGuard API",
    description="Prompt injection firewall, hallucination blocker, and agent memory layer",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# initialise guard once at startup
guard = Guard()

# in-memory log store
logs = {"input": [], "output": [], "memory": []}


# ── request models ───────────────────────────────────────────────────
class InputRequest(BaseModel):
    text: str
    session_id: str = "default"

class OutputRequest(BaseModel):
    response: str
    sources: list[str]
    session_id: str = "default"

class MemoryWriteRequest(BaseModel):
    session_id: str
    fact: str

class MemoryQueryRequest(BaseModel):
    session_id: str
    question: str
    top_k: int = 3

class RunRequest(BaseModel):
    user_input: str
    llm_response: str
    sources: list[str] = []
    session_id: str = "default"


# ── routes ───────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "name": "LLMGuard API",
        "version": "0.1.0",
        "status": "running",
        "endpoints": ["/check/input", "/check/output", "/memory/write", "/memory/query", "/run", "/logs"]
    }

@app.post("/check/input")
def check_input(req: InputRequest):
    result = guard.check_input(req.text)
    logs["input"].append({
        "timestamp": str(datetime.now()),
        "text":      req.text[:100],
        "blocked":   result["blocked"],
        "confidence": result["confidence"],
        "session_id": req.session_id
    })
    return result

@app.post("/check/output")
def check_output(req: OutputRequest):
    result = guard.check_output(req.response, req.sources)
    logs["output"].append({
        "timestamp":  str(datetime.now()),
        "response":   req.response[:100],
        "consistent": result["consistent"],
        "confidence": result["confidence"],
        "session_id": req.session_id
    })
    return result

@app.post("/memory/write")
def memory_write(req: MemoryWriteRequest):
    result = guard.remember(req.session_id, req.fact)
    logs["memory"].append({
        "timestamp":  str(datetime.now()),
        "session_id": req.session_id,
        "fact":       req.fact[:100],
        "action":     "write"
    })
    return result

@app.post("/memory/query")
def memory_query(req: MemoryQueryRequest):
    return guard.recall(req.session_id, req.question, req.top_k)

@app.post("/run")
def run(req: RunRequest):
    return guard.run(
        user_input=req.user_input,
        llm_response=req.llm_response,
        sources=req.sources,
        session_id=req.session_id
    )

@app.get("/logs")
def get_logs():
    return {
        "input_checks":  logs["input"][-20:],
        "output_checks": logs["output"][-20:],
        "memory_ops":    logs["memory"][-20:],
    }

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": str(datetime.now())}
