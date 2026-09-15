"""AI RPG 游戏客户端主应用（Textual TUI）"""

import asyncio
from typing import Callable, Optional

from textual.app import App, ComposeResult
from textual.screen import Screen

from .server_client import (
    add_task_succeeded_listener,
    remove_task_succeeded_listener,
)
from .session import ClientSession


class GameClient(App[None]):
    """游戏客户端主应用。启动后推入 launch_screen 指定的 Screen（由调用方决定）。"""

    # 不要重新绑定 ctrl+c：Textual 默认将其用于“复制选中文本”，
    # 覆盖为 quit 会导致鼠标选中文本后按 ctrl+c 直接退出游戏而非复制。
    # 退出请使用 Textual 默认绑定的 ctrl+q。

    # ── 会话状态：登录后写入，登出后清空 ──
    session: Optional[ClientSession] = None

    # 会话消息同步的唤醒信号：任务成功时置位，令各 Screen 的同步循环立即拉取一次。
    session_sync_event: asyncio.Event

    def __init__(
        self,
        *,
        launch_screen: Optional[Callable[[], "Screen[None]"]] = None,
    ) -> None:
        """launch_screen：启动时 push 的初始 Screen 工厂函数；None 时默认
        LaunchScreen（正常登录流程）。由调用方（如 scripts/run_tui_client.py）根据
        命令行参数决定传入哪个 Screen，方便开发时跳过登录流程直接进入指定页面调试。

        LaunchScreen 采用惰性导入，避免 app → launch → base → app 的循环导入。
        """
        if launch_screen is None:
            from .launch import LaunchScreen

            launch_screen = LaunchScreen
        super().__init__()
        self._launch_screen = launch_screen
        # 在事件循环内创建（on_mount），避免把 Event 绑定到错误的 loop。

    def compose(self) -> ComposeResult:
        # 保留 App 默认空 Screen 作为栈底，防止 switch_screen 时栈清空
        yield from []

    def on_mount(self) -> None:
        self.session_sync_event = asyncio.Event()
        add_task_succeeded_listener(self._wake_session_sync)
        self.push_screen(self._launch_screen())

    def on_unmount(self) -> None:
        # Textual 8 的 App._shutdown() 派发的是 events.Unmount()，真正会被调用的钩子是
        # on_unmount（没有 Shutdown 事件，on_shutdown 永远不会触发）。
        remove_task_succeeded_listener(self._wake_session_sync)

    def _wake_session_sync(self) -> None:
        """任务成功的回调：置位唤醒信号，令同步循环立刻拉取一次。"""
        self.session_sync_event.set()

    def clear_session(self) -> None:
        """登出时清空会话状态。"""
        self.session = None
