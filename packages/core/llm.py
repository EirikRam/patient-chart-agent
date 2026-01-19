from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request
from typing import Optional

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o"


def _read_http_error_body(error: urllib.error.HTTPError) -> str:
    try:
        body_bytes = error.read()
    except Exception:
        return ""
    try:
        return body_bytes.decode("utf-8", errors="replace")
    except Exception:
        return ""


class LLMClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
        self.model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

    def is_available(self) -> bool:
        return bool(self.api_key)

    def complete(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a careful clinical summarizer."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        url = f"{self.base_url}/chat/completions"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        max_retries = 5
        for attempt in range(max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    status = response.getcode()
                    content_type = (
                        response.headers.get("Content-Type", "unknown")
                        if response.headers
                        else "unknown"
                    )
                    raw = response.read()
                text = raw.decode("utf-8", errors="replace")
                try:
                    body = json.loads(text)
                except Exception as exc:
                    raise RuntimeError(
                        "OpenAI non-JSON response: "
                        f"status={status} content_type={content_type} url={url} "
                        f"body_preview={text[:500]}"
                    ) from exc
                return body["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as exc:
                body_text = _read_http_error_body(exc)
                status = getattr(exc, "code", "unknown")
                retry_after = None
                if exc.headers:
                    retry_after = exc.headers.get("Retry-After")
                if retry_after is not None:
                    try:
                        retry_after = float(retry_after)
                    except ValueError:
                        retry_after = None

                if status in {429, 503} and attempt < max_retries:
                    backoff = 2**attempt
                    jitter = random.random() * 0.25
                    delay = retry_after if retry_after is not None else backoff
                    time.sleep(delay + jitter)
                    continue

                content_type = exc.headers.get("Content-Type", "unknown") if exc.headers else "unknown"
                preview = body_text.strip()[:500]
                message = (
                    "OpenAI HTTPError: "
                    f"status={status} content_type={content_type} url={url} "
                    f"body_preview={preview}"
                )
                raise RuntimeError(message) from exc
            except Exception as exc:
                raise RuntimeError(
                    f"OpenAI request failed: url={url} error={type(exc).__name__}: {exc}"
                ) from exc

        raise RuntimeError("LLM request failed after retries")


__all__ = ["LLMClient"]
