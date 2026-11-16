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
