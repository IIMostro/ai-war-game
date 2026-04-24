"""Normalize pytest exit codes for prek hooks."""

from __future__ import annotations

import pytest


def main() -> int:
    """Run pytest and treat "no tests collected" as success for hook usage."""
    exit_code = pytest.main()
    if exit_code == pytest.ExitCode.NO_TESTS_COLLECTED:
        return 0
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
