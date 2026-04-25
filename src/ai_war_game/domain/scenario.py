"""剧本对象: 保留 Hermes 生成结果以供后续校验和重放。"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Scenario:
    """Hermes 生成的剧本快照。"""

    theme: str
    summary: str
    starting_day: int
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.theme.strip():
            raise ValueError("theme 不能为空")
        if not self.summary.strip():
            raise ValueError("summary 不能为空")
        if self.starting_day < 1:
            raise ValueError("starting_day 必须 >= 1")
