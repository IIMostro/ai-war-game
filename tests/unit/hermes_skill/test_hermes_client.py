"""tests/unit/hermes_skill/test_hermes_client.py"""

import stat
from pathlib import Path

import pytest

from hermes_client import (
    HermesUnavailableError,
    ScenarioGenerationError,
    ScenarioInvalidError,
    call_hermes,
    check_environment,
    parse_json_response,
)


class TestCheckEnvironment:
    def test_passes_when_bin_model_and_config_exist(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        hermes_bin = tmp_path / "hermes"
        hermes_bin.write_text("#!/bin/sh\nexit 0\n")
        hermes_bin.chmod(hermes_bin.stat().st_mode | stat.S_IXUSR)
        config = tmp_path / "hermes.yaml"
        config.write_text("model: demo\n")
        monkeypatch.setenv("AI_WAR_GAME_HERMES_BIN", str(hermes_bin))
        monkeypatch.setenv("AI_WAR_GAME_HERMES_MODEL", "hermes-3")
        monkeypatch.setenv("AI_WAR_GAME_HERMES_CONFIG", str(config))

        check_environment()  # should not raise

    def test_raises_when_bin_missing(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        config = tmp_path / "hermes.yaml"
        config.write_text("model: demo\n")
        monkeypatch.setenv("AI_WAR_GAME_HERMES_BIN", "definitely-missing")
        monkeypatch.setenv("AI_WAR_GAME_HERMES_MODEL", "hermes-3")
        monkeypatch.setenv("AI_WAR_GAME_HERMES_CONFIG", str(config))

        with pytest.raises(HermesUnavailableError):
            check_environment()

    def test_raises_when_model_missing(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        hermes_bin = tmp_path / "hermes"
        hermes_bin.write_text("#!/bin/sh\nexit 0\n")
        hermes_bin.chmod(hermes_bin.stat().st_mode | stat.S_IXUSR)
        config = tmp_path / "hermes.yaml"
        config.write_text("model: demo\n")
        monkeypatch.setenv("AI_WAR_GAME_HERMES_BIN", str(hermes_bin))
        monkeypatch.delenv("AI_WAR_GAME_HERMES_MODEL", raising=False)
        monkeypatch.setenv("AI_WAR_GAME_HERMES_CONFIG", str(config))

        with pytest.raises(HermesUnavailableError):
            check_environment()

    def test_raises_when_config_file_missing(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        hermes_bin = tmp_path / "hermes"
        hermes_bin.write_text("#!/bin/sh\nexit 0\n")
        hermes_bin.chmod(hermes_bin.stat().st_mode | stat.S_IXUSR)
        monkeypatch.setenv("AI_WAR_GAME_HERMES_BIN", str(hermes_bin))
        monkeypatch.setenv("AI_WAR_GAME_HERMES_MODEL", "hermes-3")
        monkeypatch.setenv("AI_WAR_GAME_HERMES_CONFIG", str(tmp_path / "nonexistent.yaml"))

        with pytest.raises(HermesUnavailableError, match="不存在"):
            check_environment()


class TestCallHermes:
    def test_returns_stdout_on_success(self, monkeypatch, tmp_path):
        def fake_run(*args, **kwargs):
            class Result:
                returncode = 0
                stdout = '{"summary": "test"}'
                stderr = ""

            return Result()

        hermes_bin = tmp_path / "hermes"
        hermes_bin.write_text("#!/bin/sh\nexit 0\n")
        hermes_bin.chmod(hermes_bin.stat().st_mode | stat.S_IXUSR)
        config = tmp_path / "hermes.yaml"
        config.write_text("model: demo\n")
        monkeypatch.setattr("hermes_client.subprocess.run", fake_run)
        monkeypatch.setenv("AI_WAR_GAME_HERMES_BIN", str(hermes_bin))
        monkeypatch.setenv("AI_WAR_GAME_HERMES_MODEL", "test-model")
        monkeypatch.setenv("AI_WAR_GAME_HERMES_CONFIG", str(config))

        result = call_hermes("hello")
        assert result == '{"summary": "test"}'

    def test_raises_on_nonzero_exit(self, monkeypatch, tmp_path):
        def fake_run(*args, **kwargs):
            class Result:
                returncode = 1
                stdout = ""
                stderr = "error msg"

            return Result()

        hermes_bin = tmp_path / "hermes"
        hermes_bin.write_text("#!/bin/sh\nexit 0\n")
        hermes_bin.chmod(hermes_bin.stat().st_mode | stat.S_IXUSR)
        config = tmp_path / "hermes.yaml"
        config.write_text("model: demo\n")
        monkeypatch.setattr("hermes_client.subprocess.run", fake_run)
        monkeypatch.setenv("AI_WAR_GAME_HERMES_BIN", str(hermes_bin))
        monkeypatch.setenv("AI_WAR_GAME_HERMES_MODEL", "test-model")
        monkeypatch.setenv("AI_WAR_GAME_HERMES_CONFIG", str(config))

        with pytest.raises(ScenarioGenerationError, match="error msg"):
            call_hermes("hello")

    def test_parses_valid_json(self):
        result = parse_json_response('{"key": "val"}')
        assert result == {"key": "val"}

    def test_raises_on_invalid_json(self):
        with pytest.raises(ScenarioInvalidError, match="不是合法 JSON"):
            parse_json_response("not-json")

    def test_raises_on_json_array(self):
        with pytest.raises(ScenarioInvalidError, match="不是合法 JSON"):
            parse_json_response("[1, 2, 3]")

    def test_raises_on_json_string(self):
        with pytest.raises(ScenarioInvalidError, match="不是合法 JSON"):
            parse_json_response('"hello"')
