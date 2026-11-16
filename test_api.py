import json
import os

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

import api
from benchmark import FIXTURES
from review import review


@pytest.mark.parametrize("before,after,expected", FIXTURES)
def test_fixture(before, after, expected):
    assert {(r["rule"], r["line"]) for r in review(before, after)["findings"]} == set(expected)


def test_feedback(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    monkeypatch.setattr(api, "engine", engine)
    with TestClient(api.app) as client:
        data = client.post("/api/review", json={"before":"","after":"def f(x=[]):\n    return x"}).json()
        url = f"/api/review/{data['id']}"
        endpoint = url + "/feedback/" + data["findings"][0]["id"]
        assert client.put(endpoint, json={"decision":"corrected"}).status_code == 422
        assert client.put(endpoint, json={"decision":"corrected","correction":"Init in body"}).status_code == 200
        stored = client.get(url).json()
        assert stored["feedback"][0]["correction"] == "Init in body"
        monkeypatch.delenv("LLM_CHAT_URL", raising=False)
        assert client.post(url + "/draft").status_code == 503
    engine.dispose()


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="PostgreSQL is only required in integration CI")
def test_postgres_storage_and_llm_transport(monkeypatch):
    with TestClient(api.app) as browser:
        result = browser.post("/api/review", json={"before": "", "after": "def f(x=[]):\n    return x"})
        assert result.status_code == 200
        data = result.json()
        endpoint = f"/api/review/{data['id']}"
        finding = data["findings"][0]
        assert browser.put(endpoint + "/feedback/" + finding["id"], json={"decision":"accepted"}).status_code == 200
        assert browser.get(endpoint).json()["feedback"][0]["decision"] == "accepted"

        def fake_provider(request):
            assert request.headers["Authorization"] == "Bearer fixture"
            payload = json.loads(json.loads(request.content)["messages"][-1]["content"])
            assert payload == [{field: finding[field] for field in ("id", "rule", "title", "line")}]
            return httpx.Response(200, json={"choices":[{"message":{"content":"Review draft fixture"}}]})

        monkeypatch.setenv("LLM_CHAT_URL", "https://fixture.invalid/chat/completions")
        monkeypatch.setenv("LLM_API_KEY", "fixture")
        monkeypatch.setenv("LLM_MODEL", "fixture")
        client = httpx.Client(transport=httpx.MockTransport(fake_provider))
        monkeypatch.setattr(api.httpx, "Client", lambda **kwargs: client)
        assert browser.post(endpoint + "/draft").json() == {"draft":"Review draft fixture"}
