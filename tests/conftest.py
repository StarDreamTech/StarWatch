"""测试夹具。"""

from __future__ import annotations

import pytest

from starwatch_core.bootstrap import register_builtins


@pytest.fixture(autouse=True)
def _plugins() -> None:
    """每个测试都能看到内置插件。"""
    register_builtins()
