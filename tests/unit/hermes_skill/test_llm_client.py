"""tests/unit/hermes_skill/test_llm_client.py"""

import json

import pytest

from llm_client import _direct_chat, llm_chat


class TestDirectChat:
    def test_sends_correct_request(self, monkeypatch):
        monkeypatch.setenv("AI_WAR_GAME_LLM_API_BASE", "https://fake.api/v1")
        monkeypatch.setenv("AI_WAR_GAME_LLM_API_KEY", "test-key")
        monkeypatch.setenv("AI_WAR_GAME_LLM_MODEL", "test-model")
        monkeypatch.setenv("AI_WAR_GAME_LLM_MODE", "direct")

        captured = {}

        def fake_urlopen(req, timeout=180):
            captured["url"] = req.full_url
            captured["headers"] = dict(req.headers)
            captured["body"] = json.loads(req.data)

            class FakeResp:
                def read(self):
                    return json.dumps({
                        "choices": [{"message": {"content": "hello world"}}]
                    }).encode()

                def __enter__(self):
                    return self

                def __exit__(self, *exc_info):
                    pass
            return FakeResp()

        monkeypatch.setattr("llm_client.urllib.request.urlopen", fake_urlopen)

        result = llm_chat(system_prompt="You are helpful", user_message="Hi")

        assert result == "hello world"
        assert captured["url"] == "https://fake.api/v1/chat/completions"
        assert captured["headers"]["Authorization"] == "Bearer test-key"
        assert captured["body"]["model"] == "test-model"
        assert captured["body"]["messages"][0]["content"] == "You are helpful"
        assert captured["body"]["messages"][1]["content"] == "Hi"

    def test_raises_on_http_error(self, monkeypatch):
        monkeypatch.setenv("AI_WAR_GAME_LLM_API_KEY", "test-key")
        monkeypatch.setenv("AI_WAR_GAME_LLM_MODE", "direct")

        def fake_urlopen(req, timeout=180):
            raise RuntimeError("API error")

        monkeypatch.setattr("llm_client.urllib.request.urlopen", fake_urlopen)

        with pytest.raises(RuntimeError):
            llm_chat(system_prompt="x", user_message="x")

    def test_raises_without_api_key(self, monkeypatch):
        monkeypatch.setenv("AI_WAR_GAME_LLM_MODE", "direct")
        monkeypatch.delenv("AI_WAR_GAME_LLM_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(ValueError, match="API_KEY"):
            _direct_chat("sys", "user")

    def test_raises_on_unexpected_response(self, monkeypatch):
        monkeypatch.setenv("AI_WAR_GAME_LLM_MODE", "direct")
        monkeypatch.setenv("AI_WAR_GAME_LLM_API_KEY", "key")

        def fake_urlopen(req, timeout=180):
            class FakeResp:
                def read(self):
                    return json.dumps({"choices": []}).encode()

                def __enter__(self):
                    return self

                def __exit__(self, *exc_info):
                    pass
            return FakeResp()

        monkeypatch.setattr("llm_client.urllib.request.urlopen", fake_urlopen)

        with pytest.raises(RuntimeError, match="Unexpected"):
            _direct_chat("sys", "user")


class TestHermesFallback:
    def test_falls_back_to_direct_when_hermes_missing(self, monkeypatch):
        monkeypatch.setenv("AI_WAR_GAME_LLM_MODE", "hermes")
        monkeypatch.setenv("AI_WAR_GAME_HERMES_BIN", "/nonexistent/hermes")
        monkeypatch.setenv("AI_WAR_GAME_LLM_API_KEY", "fallback-key")

        monkeypatch.setattr("llm_client._direct_chat", lambda s, u, m=None: "fallback response")

        result = llm_chat(system_prompt="sys", user_message="user")
        assert result == "fallback response"


class TestHermesChat:
    def test_calls_subprocess(self, monkeypatch):
        monkeypatch.setenv("AI_WAR_GAME_LLM_MODE", "hermes")
        monkeypatch.setenv("AI_WAR_GAME_HERMES_BIN", "hermes")

        def fake_run(*args, **kwargs):
            class Result:
                returncode = 0
                stdout = "hermes response"
                stderr = ""
            return Result()

        monkeypatch.setattr("llm_client.subprocess.run", fake_run)

        result = llm_chat(system_prompt="sys", user_message="user")
        assert result == "hermes response"
