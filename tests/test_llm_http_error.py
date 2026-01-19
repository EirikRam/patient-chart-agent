from io import BytesIO
from urllib.error import HTTPError

from packages.core.llm import _format_http_error


def test_format_http_error_includes_body() -> None:
    body = b'{"error":{"message":"Too Many Requests"}}'
    error = HTTPError(
        url="https://api.openai.com/v1/chat/completions",
        code=429,
        msg="Too Many Requests",
        hdrs={"Retry-After": "1"},
        fp=BytesIO(body),
    )
    text = _format_http_error(error, body.decode("utf-8"))
    assert "Too Many Requests" in text
    assert "body=" in text
