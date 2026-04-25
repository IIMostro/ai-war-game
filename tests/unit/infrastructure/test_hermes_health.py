import stat
from pathlib import Path

import pytest

from ai_war_game.domain.errors import HermesUnavailableError
from ai_war_game.infrastructure.hermes.health import (
    ENV_BIN,
    ENV_CONFIG,
    ENV_MODEL,
    HermesEnvironmentCheck,
)


def test_should_pass_when_bin_model_and_config_exist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    hermes_bin = tmp_path / "hermes"
    hermes_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    hermes_bin.chmod(hermes_bin.stat().st_mode | stat.S_IXUSR)
    config_path = tmp_path / "hermes.yaml"
    config_path.write_text("model: demo\n", encoding="utf-8")
    monkeypatch.setenv(ENV_BIN, str(hermes_bin))
    monkeypatch.setenv(ENV_MODEL, "hermes-3")
    monkeypatch.setenv(ENV_CONFIG, str(config_path))

    HermesEnvironmentCheck().check()


def test_should_raise_when_bin_is_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    config_path = tmp_path / "hermes.yaml"
    config_path.write_text("model: demo\n", encoding="utf-8")
    monkeypatch.setenv(ENV_BIN, "definitely-missing-hermes")
    monkeypatch.setenv(ENV_MODEL, "hermes-3")
    monkeypatch.setenv(ENV_CONFIG, str(config_path))

    with pytest.raises(HermesUnavailableError):
        HermesEnvironmentCheck().check()


def test_should_raise_when_model_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    hermes_bin = tmp_path / "hermes"
    hermes_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    hermes_bin.chmod(hermes_bin.stat().st_mode | stat.S_IXUSR)
    config_path = tmp_path / "hermes.yaml"
    config_path.write_text("model: demo\n", encoding="utf-8")
    monkeypatch.setenv(ENV_BIN, str(hermes_bin))
    monkeypatch.delenv(ENV_MODEL, raising=False)
    monkeypatch.setenv(ENV_CONFIG, str(config_path))

    with pytest.raises(HermesUnavailableError):
        HermesEnvironmentCheck().check()
