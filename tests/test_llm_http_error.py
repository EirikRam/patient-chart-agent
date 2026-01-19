from io import BytesIO
from urllib.error import HTTPError
import urllib.request

import pytest

from packages.core.llm import LLMClient


def test_llm_http_error_includes_body_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    body = b'{"error":{"message":"Too Many Requests"}}'

    def fake_urlopen(*_args, **_kwargs):
        raise HTTPError(
            url="https://api.openai.com/v1/chat/completions",
            code=429,
            msg="Too Many Requests",
            hdrs={"Retry-After": "0", "Content-Type": "application/json"},
            fp=BytesIO(body),
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("time.sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("random.random", lambda: 0.0)

    client = LLMClient(api_key="test-key")
    with pytest.raises(RuntimeError) as excinfo:
        client.complete("test prompt")

    message = str(excinfo.value)
    assert "status=429" in message
    assert "content_type=application/json" in message
    assert "body_preview" in message
