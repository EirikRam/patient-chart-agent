from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from openai import OpenAI

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o"


def load_dotenv(env_path: Optional[Path] = None) -> dict[str, str]:
    if os.getenv("OPENAI_API_KEY"):
        return {}
    env_path = env_path or (Path.cwd() / ".env")
    if not env_path.exists() or not env_path.is_file():
        return {}
    loaded: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].lstrip()
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value
        loaded[key] = value
    return loaded


def ensure_openai_api_key(env_path: Optional[Path] = None) -> bool:
    if os.getenv("OPENAI_API_KEY"):
        return True
    load_dotenv(env_path)
    return bool(os.getenv("OPENAI_API_KEY"))


def _extract_response_text(response: object) -> str:
    try:
        output = getattr(response, "output", None) or []
        for item in output:
            content = getattr(item, "content", None) or []
            for part in content:
                text = getattr(part, "text", None)
                if text:
                    return text
    except Exception:
        return ""
    return ""


class LLMClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
        self.model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

    def is_available(self) -> bool:
        return bool(self.api_key or os.getenv("OPENAI_API_KEY"))

    def complete(self, prompt: str) -> str:
        api_key = self.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set (env or .env)")

        client = OpenAI(api_key=api_key, base_url=self.base_url)
        try:
            response = client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": "You are a careful clinical summarizer."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
            )
        except Exception as exc:
            error = RuntimeError(f"OpenAI request failed: {type(exc).__name__}: {exc}")
            status = getattr(exc, "status_code", None)
            if status is not None:
                error.status_code = status
            raise error from exc

        text = getattr(response, "output_text", None)
        if text:
            return text
        return _extract_response_text(response)


__all__ = ["LLMClient", "ensure_openai_api_key", "load_dotenv"]
