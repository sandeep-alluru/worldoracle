"""Tests for worldoracle.mcp_server module structure."""

from __future__ import annotations

import pytest


def test_mcp_server_importable() -> None:
    """mcp_server module should import without error (even without mcp installed)."""
    import worldoracle.mcp_server as m

    assert hasattr(m, "run_server")


def test_mcp_server_has_run_server_callable() -> None:
    """run_server should be a callable function."""
    from worldoracle.mcp_server import run_server

    assert callable(run_server)


def test_require_mcp_exits_without_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    """_require_mcp should exit with code 1 when mcp is not importable."""
    import builtins

    real_import = builtins.__import__

    def mock_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "mcp" or name.startswith("mcp."):
            raise ImportError("mocked: mcp not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    # Re-import the module to get fresh _require_mcp
    import importlib

    import worldoracle.mcp_server as m

    importlib.reload(m)

    with pytest.raises(SystemExit) as exc_info:
        m._require_mcp()

    assert exc_info.value.code == 1
