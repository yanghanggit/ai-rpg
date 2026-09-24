"""Game Agent：面向 AI 代理的**进程内**游戏动作层。

与 `scripts/run_agent_game.py`（本包的薄 CLI 壳）配合使用：直接从本地快照
（`.worlds/...`）恢复游戏实例、执行**一次**动作、再写出新快照，进程退出后无残留。
真正的游戏规则校验仍在 `ai_rpg.services.*`，本包只是「快照读 → 动作 → 快照写」的驱动层。

它和 `ai_rpg.api_agent`（走 HTTP、状态在服务端）是**平行**的两条代理通道：
- 本包：进程内直接调 services，无服务器，一次性、可回溯；
- api_agent：通过常驻服务器的 HTTP 接口，交互式走查。
"""

from .core import create_and_initialize_game, restore_game

__all__ = ["create_and_initialize_game", "restore_game"]
