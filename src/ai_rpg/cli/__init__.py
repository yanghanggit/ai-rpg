"""命令行入口（console scripts）。

原本散落在 ``scripts/`` 的可运行 CLI 集中于此，由 ``pyproject.toml`` 的
``[project.scripts]`` 暴露为可执行命令：

- ``ai-rpg-server``     —— 游戏服务器（``uvicorn ai_rpg.cli.server:app``）
- ``ai-rpg-agent-game`` —— 快照驱动的离线游戏推进
- ``ai-rpg-agent-api``  —— 服务器 API 走查

``scripts/`` 仅保留仓库工具类脚本。
"""
