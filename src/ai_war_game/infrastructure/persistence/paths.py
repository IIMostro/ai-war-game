"""存档路径解析."""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

_SAFE_SAVE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


@dataclass(slots=True)
class SaveLocator:
    root: Path

    def ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def dir_for(self, save_id: str) -> Path:
        if not save_id or not _SAFE_SAVE_ID.match(save_id):
            raise ValueError(f"save_id 必须为非空字母数字与 ._- 组成: {save_id!r}")
        return self.root / save_id

    def iter_save_ids(self) -> Iterator[str]:
        if not self.root.exists():
            return iter(())
        return (p.name for p in self.root.iterdir() if p.is_dir())

