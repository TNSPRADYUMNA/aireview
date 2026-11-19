import json
import httpx
import pytest
from fastapi import HTTPException
import api


@pytest.mark.parametrize("line,accepted", [(2,True),(1,False),(99,False)])
def test_model_findings_reference_changed_evidence(monkeypatch,line,accepted):
    for name,value in (("LLM_CHAT_URL","https://fixture.invalid"),("LLM_API_KEY","fixture"),("LLM_MODEL","fixture")):
        monkeypatch.setenv(name,value)
    def reply(request):
        body = json.loads(request.content)
        assert json.loads(body["messages"][1]["content"])["after"] == "def f(x):\n    return 1/x"
        content = json.dumps([{"line":line,"title":"Zero divisor","suggestion":"Handle x equal to zero",
                               "rationale":"The division may raise ZeroDivisionError."}])
        return httpx.Response(200,json={"choices":[{"message":{"content":content}}]})
    client = httpx.Client(transport=httpx.MockTransport(reply))
    monkeypatch.setattr(api.httpx,"Client",lambda **kwargs:client)
    code = api.Code(before="def f(x):\n    return x",after="def f(x):\n    return 1/x",use_llm=True)
    if accepted:
        findings = api.model_findings(code)
        assert findings[0]["evidence"] == "return 1/x"
        assert findings[0]["confidence"] == "unverified model suggestion"
    else:
        with pytest.raises(HTTPException) as caught:
            api.model_findings(code)
        assert caught.value.status_code == 502
