from pathlib import Path

import pytest

from ai_war_game.infrastructure.persistence.paths import SaveLocator


def test_should_return_directory_for_valid_save_id(tmp_path: Path):
    locator = SaveLocator(root=tmp_path / "saves")

    save_dir = locator.dir_for("save-1.alpha")

    assert save_dir == tmp_path / "saves" / "save-1.alpha"


@pytest.mark.parametrize("save_id", ["", "../escape", "bad/slash", "空 白"])
def test_should_reject_invalid_save_id(tmp_path: Path, save_id: str):
    locator = SaveLocator(root=tmp_path / "saves")

    with pytest.raises(ValueError):
        locator.dir_for(save_id)


def test_should_iterate_existing_save_ids(tmp_path: Path):
    root = tmp_path / "saves"
    (root / "save-b").mkdir(parents=True)
    (root / "save-a").mkdir()
    (root / "not-a-save.txt").write_text("x", encoding="utf-8")
    locator = SaveLocator(root=root)

    save_ids = sorted(locator.iter_save_ids())

    assert save_ids == ["save-a", "save-b"]


def test_should_return_empty_iterator_when_root_missing(tmp_path: Path):
    locator = SaveLocator(root=tmp_path / "missing")

    assert list(locator.iter_save_ids()) == []


def test_should_create_root_directory(tmp_path: Path):
    root = tmp_path / "nested" / "saves"
    locator = SaveLocator(root=root)

    locator.ensure_root()

    assert root.is_dir()

