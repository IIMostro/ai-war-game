"""HermesScenarioGenerator: 通过子进程调用 hermes CLI 生成剧本."""

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

from ai_war_game.domain.errors import ScenarioGenerationError
from ai_war_game.domain.scenario import Scenario
from ai_war_game.infrastructure.hermes.parser import parse_scenario_payload
from ai_war_game.infrastructure.hermes.prompts import render_prompt


@dataclass(frozen=True, slots=True)
class SubprocessOutcome:
    returncode: int
    stdout: str
    stderr: str


SubprocessRunner = Callable[..., SubprocessOutcome]


def _default_runner(*, argv: list[str], stdin: str, timeout: float) -> SubprocessOutcome:
    completed = subprocess.run(
        argv,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return SubprocessOutcome(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


@dataclass(slots=True)
class HermesScenarioGenerator:
    bin_path: str
    model: str
    config_path: str
    runner: SubprocessRunner = _default_runner
    timeout_seconds: float = 120.0

    def generate(self, *, theme: str, player_display_name: str) -> Scenario:
        prompt = render_prompt(theme=theme, player_display_name=player_display_name)
        argv = [
            self.bin_path,
            "skill",
            "run",
            "scenario-generator",
            "--model",
            self.model,
            "--config",
            self.config_path,
        ]
        outcome = self.runner(argv=argv, stdin=prompt, timeout=self.timeout_seconds)
        if outcome.returncode != 0:
            raise ScenarioGenerationError(
                f"hermes 退出码 {outcome.returncode}: {outcome.stderr.strip() or '(无 stderr)'}"
            )
        try:
            payload = json.loads(outcome.stdout)
        except json.JSONDecodeError as exc:
            raise ScenarioGenerationError(
                f"hermes 输出不是合法 JSON: {exc}; raw={outcome.stdout[:200]!r}"
            ) from exc
        return parse_scenario_payload(theme, payload)
