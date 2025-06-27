"""Test configuration and fixtures."""

import pytest
from pathlib import Path

# 添加 src 目录到 Python 路径
import sys

src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

try:
    from multi_agents_game.game.tcg_game import TCGGame
    from multi_agents_game.models.objects import Actor
except ImportError:
    # 在包未完全安装时跳过导入
    TCGGame = None
    Actor = None


@pytest.fixture
def sample_game():
    """Create a sample game for testing."""
    if TCGGame is None:
        pytest.skip("TCGGame not available")
    return TCGGame(name="test_game")


@pytest.fixture
def sample_actor():
    """Create a sample actor for testing."""
    if Actor is None:
        pytest.skip("Actor not available")
    return Actor(name="test_actor")
