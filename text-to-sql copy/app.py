import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent_core import SUGGESTED_QUESTIONS, answer_user_query

app = FastAPI(title="Football SQL Agent")

CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "https://mythaonguyen.github.io,http://127.0.0.1:8000,http://localhost:8000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in CORS_ORIGINS if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class QueryResponse(BaseModel):
    question: str
    sql_query: str
    answer: str
    row_count: int
    rows_truncated: bool = False
    columns_truncated: bool = False
    columns: list[str]
    rows: list[dict]


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/suggestions")
def suggestions():
    return {"suggestions": SUGGESTED_QUESTIONS}


@app.post("/api/query", response_model=QueryResponse)
def query(request: QueryRequest):
    try:
        result = answer_user_query(request.question.strip())
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
