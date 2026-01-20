import os

import pytest

from packages.core.llm import load_dotenv


def test_load_dotenv_sets_openai_key(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=from_file\nOTHER_VAR=abc\n", encoding="utf-8")

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OTHER_VAR", raising=False)

    loaded = load_dotenv(env_path)

    assert os.getenv("OPENAI_API_KEY") == "from_file"
    assert os.getenv("OTHER_VAR") == "abc"
    assert loaded["OPENAI_API_KEY"] == "from_file"


def test_load_dotenv_noop_when_key_present(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=from_file\nOTHER_VAR=abc\n", encoding="utf-8")

    monkeypatch.setenv("OPENAI_API_KEY", "from_env")
    monkeypatch.delenv("OTHER_VAR", raising=False)

    loaded = load_dotenv(env_path)

    assert os.getenv("OPENAI_API_KEY") == "from_env"
    assert os.getenv("OTHER_VAR") is None
    assert loaded == {}
