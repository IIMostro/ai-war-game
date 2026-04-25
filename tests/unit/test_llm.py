"""tests/unit/test_llm.py"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ai_war_game.llm import (
    LLMResponseError,
    llm_call,
    llm_call_json,
)


class MockChoice:
    def __init__(self, content: str):
        self.message = self
        self.content = content


class MockResponse:
    def __init__(self, content: str):
        self.choices = [MockChoice(content)]


def _mock_completion(content: str):
    def mock(*args, **kwargs):
        return MockResponse(content)

    return mock


class TestLlmCall:
    def test_returns_text_on_success(self):
        with patch("litellm.completion", _mock_completion("hello world")):
            result = llm_call("system", "user", model="test/model")
        assert result == "hello world"

    def test_raises_on_completion_error(self):
        with patch("litellm.completion", side_effect=Exception("API error")):
            with pytest.raises(LLMResponseError, match="API error"):
                llm_call("sys", "user", model="test/model")


class TestLlmCallJson:
    def test_parses_valid_json(self):
        with patch("litellm.completion", _mock_completion('{"key": "val"}')):
            result = llm_call_json("sys", "user", model="test/model")
        assert result == {"key": "val"}

    def test_strips_markdown_fences(self):
        with patch(
            "litellm.completion",
            _mock_completion('```json\n{"key": "val"}\n```'),
        ):
            result = llm_call_json("sys", "user", model="test/model")
        assert result == {"key": "val"}

    def test_retries_on_invalid_json(self):
        with (
            patch(
                "litellm.completion",
                _mock_completion("not-json"),
            ),
            pytest.raises(LLMResponseError),
        ):
            llm_call_json("sys", "user", model="test/model")

    def test_raises_on_json_array(self):
        with (
            patch(
                "litellm.completion",
                _mock_completion("[1, 2, 3]"),
            ),
            pytest.raises(LLMResponseError),
        ):
            llm_call_json("sys", "user", model="test/model")
