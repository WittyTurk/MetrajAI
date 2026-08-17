from __future__ import annotations

from unittest.mock import patch

from metrajai.cli import _parent_is_alive, build_parser


def test_serve_accepts_desktop_parent_pid() -> None:
    args = build_parser().parse_args(
        ["serve", "--token", "secret", "--parent-pid", "1234"]
    )

    assert args.parent_pid == 1234


def test_parent_watchdog_detects_missing_process() -> None:
    with patch("metrajai.cli.os.kill", side_effect=ProcessLookupError):
        assert _parent_is_alive(1234) is False


def test_parent_watchdog_treats_permission_error_as_alive() -> None:
    with patch("metrajai.cli.os.kill", side_effect=PermissionError):
        assert _parent_is_alive(1234) is True
