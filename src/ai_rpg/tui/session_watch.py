"""客户端会话消息同步：定时增量拉取 + 任务成功即时拉取。

替代旧的 SSE `/stream` 长连接。设计依据：

- 会话消息是「可增量、幂等、有水位线」的拉取型资源，用一次性 `/since` 端点即可，
  无需服务端为一个没有推送语义的流维持长连接与轮询协程。
- 「有新会话消息」在时间上几乎总等价于「某个任务成功收尾」（消息在 pipeline 处理时产生，
  而 pipeline 由任务驱动）。因此任务成功时立刻同步一次；无任务时用定时器兜底。
- 同步只推进 `notify_last_sequence_id`（未读水位）并刷新徽标，不渲染消息内容；
  渲染仍由用户显式 `/session` 触发（推进 `last_sequence_id`）。
"""

import asyncio
from typing import Callable

from loguru import logger

from .app import GameClient
from .server_client import fetch_session_messages

DEFAULT_SESSION_POLL_INTERVAL_SECONDS = 2.0


async def sync_session_messages(app: GameClient) -> None:
    """增量拉取一次会话消息，只推进未读水位（`notify_last_sequence_id`）。

    幂等：按 `sequence_id >` 过滤，重复拉取安全；失败只记日志、不抛出。
    """
    session = app.session
    if session is None:
        return

    try:
        resp = await fetch_session_messages(
            session.user_name, session.game_name, session.notify_last_sequence_id
        )
    except Exception as e:
        logger.warning(f"sync_session_messages: 拉取失败 error={e}")
        return

    # 拉取期间会话可能已切换/登出：丢弃过期结果
    if app.session is not session:
        return

    for msg in resp.session_messages:
        if msg.sequence_id > session.notify_last_sequence_id:
            session.notify_last_sequence_id = msg.sequence_id


async def watch_session_messages(
    app: GameClient,
    on_update: Callable[[], None],
    is_active: Callable[[], bool] = lambda: True,
    interval: float = DEFAULT_SESSION_POLL_INTERVAL_SECONDS,
) -> None:
    """循环同步会话消息：每 `interval` 秒拉一次；任务成功时被唤醒立刻拉一次。

    以 `on_update` 回调刷新界面（典型实现：更新未读徽标）。

    Textual 不会在 Screen 卸载时自动取消 `@work` worker，因此传入 `is_active`
    （典型实现：`lambda: self.is_mounted`）让循环在界面卸载后自行退出，
    避免对已卸载的界面执行 HTTP 拉取与徽标刷新。
    """
    session = app.session
    if session is None:
        return

    # 建立基线：进入界面那一刻已有的历史不算未读
    session.notify_last_sequence_id = session.last_sequence_id
    logger.info(f"watch_session_messages: 启动会话消息同步 user={session.user_name}")

    while app.session is session and is_active():
        # 先清位再拉取：若同步期间任务成功置位，拉完后会立刻再拉一次（保证不漏，重复无害）
        app.session_sync_event.clear()
        await sync_session_messages(app)
        if not is_active():
            break
        on_update()
        try:
            await asyncio.wait_for(app.session_sync_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass

    logger.info("watch_session_messages: 会话切换/登出/界面卸载，停止同步")
