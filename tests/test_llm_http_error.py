import pytest

from packages.core.llm import LLMClient


def test_llm_http_error_includes_status(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAPIError(Exception):
        def __init__(self, message: str, status_code: int) -> None:
            super().__init__(message)
            self.status_code = status_code

    class FakeResponses:
        def create(self, *args, **kwargs):
            raise FakeAPIError("Too Many Requests", status_code=429)

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            self.responses = FakeResponses()

    monkeypatch.setattr("packages.core.llm.OpenAI", FakeClient)

    client = LLMClient(api_key="test-key")
    with pytest.raises(RuntimeError) as excinfo:
        client.complete("test prompt")

    error = excinfo.value
    message = str(error)
    assert "FakeAPIError" in message
    assert getattr(error, "status_code", None) == 429
