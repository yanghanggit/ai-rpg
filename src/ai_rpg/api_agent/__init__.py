"""API Agent：面向 AI 代理的服务器 HTTP 接口工具层。

本包只负责「与游戏服务器通过 HTTP 交互」这一件事（配置、状态观测、接口封装），
不包含任何界面渲染，也不缓存世界状态。它与 `ai_rpg/cli/agent_game.py`
（直接调用 services 层的本地快照入口）相对：本包走 HTTP，状态由服务端内存持有。

注意区分：本包的 `server_client` 是「代理侧调用服务器」的客户端封装，
与 `ai_rpg.services.*_api`（服务器侧的路由实现）是两个不同层次的东西。
"""

from .config import server_config

__all__ = ["server_config"]
