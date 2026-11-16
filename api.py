import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from typing import Literal

from review import review

app = FastAPI(title="AIReview")
engine = create_engine(os.getenv("DATABASE_URL", "sqlite:///reviews.db"), pool_pre_ping=True)


def setup(db):
    db.execute(text("CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY, report TEXT NOT NULL)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS feedback (review_id TEXT NOT NULL, finding_id TEXT NOT NULL, "
                    "decision TEXT NOT NULL, correction TEXT NOT NULL, PRIMARY KEY(review_id, finding_id))"))


class Code(BaseModel):
    before: str = Field(max_length=100000)
    after: str = Field(max_length=100000)


class Feedback(BaseModel):
    decision: Literal["accepted", "rejected", "corrected"]
    correction: str = Field(default="", max_length=2000)


@app.post("/api/review")
def create(code: Code):
    report = review(code.before, code.after)
    key = uuid4().hex
    with engine.begin() as connection:
        setup(connection)
        connection.execute(text("INSERT INTO reviews VALUES (:id,:report)"),
                           {"id": key, "report": json.dumps(report)})
    return {"id": key, **report}


@app.get("/api/review/{key}")
def fetch(key: str):
    with engine.begin() as db:
        setup(db)
        report = db.execute(text("SELECT report FROM reviews WHERE id=:id"), {"id": key}).scalar_one_or_none()
        if report is None:
            raise HTTPException(404)
        comments = db.execute(text("SELECT finding_id,decision,correction FROM feedback WHERE review_id=:id"),
                              {"id": key}).mappings().all()
    return {"id": key, **json.loads(report), "feedback": [dict(item) for item in comments]}


@app.put("/api/review/{key}/feedback/{finding}")
def update(key: str, finding: str, item: Feedback):
    with engine.begin() as db:
        setup(db)
        report = db.execute(text("SELECT report FROM reviews WHERE id=:id"), {"id": key}).scalar_one_or_none()
        if report is None or finding not in {row["id"] for row in json.loads(report)["findings"]}:
            raise HTTPException(404, "Finding not found")
        if item.decision == "corrected" and not item.correction.strip():
            raise HTTPException(422, "A correction requires a note")
        db.execute(text("INSERT INTO feedback VALUES (:id,:finding,:decision,:correction) "
                        "ON CONFLICT(review_id,finding_id) DO UPDATE "
                        "SET decision=excluded.decision, correction=excluded.correction"),
                   {"id": key, "finding": finding, **item.model_dump()})
    return {"saved": True}


@app.post("/api/review/{key}/draft")
def draft(key: str):
    url, token, model = (os.getenv(name) for name in ("LLM_CHAT_URL", "LLM_API_KEY", "LLM_MODEL"))
    if not all((url, token, model)):
        raise HTTPException(503, "LLM provider is not configured")
    findings = fetch(key)["findings"]
    # Send rule titles and locations only. Source snippets and reviewer notes stay local.
    payload = [{field: item[field] for field in ("id", "rule", "title", "line")} for item in findings]
    if not payload:
        return {"draft": "No findings to summarize."}
    try:
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            response = client.post(url, headers={"Authorization": "Bearer " + token}, json={
                "model": model, "messages": [
                    {"role": "system", "content": "Summarize only these code review findings. "
                     "Cite their IDs and distinguish observed facts from suggested actions."},
                    {"role": "user", "content": json.dumps(payload)},
                ],
            })
            response.raise_for_status()
        message = response.json()["choices"][0]["message"]["content"]
        if not isinstance(message, str):
            raise ValueError("Invalid response")
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as error:
        raise HTTPException(502, "The LLM provider did not return a usable draft") from error
    return {"draft": message[:6000]}


dist = Path(__file__).with_name("web") / "dist"
if dist.is_dir():
    app.mount("/", StaticFiles(directory=dist, html=True), name="web")
