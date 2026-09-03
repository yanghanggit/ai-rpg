"""场景切换命令：直接切换到目标场景，供 HomeScreen 的 /switch（/sw）调用。"""

from typing import List

from loguru import logger

from ..models.api import HomePlayerActionType
from .server_client import (
    TaskFailedError,
    fetch_stages_state,
    home_player_action,
    watch_task_until_done,
)
from .utils import display_name


async def switch_stage(
    user_name: str, game_name: str, player_actor: str, target_stage: str
) -> str:
    """直接切换到目标场景，返回可写入正文区的富文本字符串。

    Args:
        user_name: 用户名
        game_name: 游戏名称
        player_actor: 玩家角色名，用于判断是否已在目标场景
        target_stage: 目标场景名（原始名称）

    Returns:
        可写入 RichLog 的富文本字符串；未知场景或已在目标场景时返回提示文本。

    Raises:
        获取场景列表或发送切换请求失败时向上抛出异常，由调用方决定如何展示错误。
    """
    logger.info(
        f"switch_stage: 切换场景 user_name={user_name} game_name={game_name} "
        f"target_stage={target_stage}"
    )
    stages_resp = await fetch_stages_state(user_name, game_name)

    if target_stage not in stages_resp.mapping:
        return (
            f"[yellow]未知场景：{display_name(target_stage)}，"
            f"可用场景见 /stage。[/]"
        )

    if player_actor in stages_resp.mapping.get(target_stage, []):
        return f"[yellow]你已经在场景：{display_name(target_stage)}。[/]"

    resp = await home_player_action(
        user_name,
        game_name,
        HomePlayerActionType.SWITCH_STAGE,
        {"stage_name": target_stage},
    )
    task_id = resp.task_id
    logger.info(f"switch_stage: 任务已创建 task_id={task_id}")

    lines: List[str] = [f"[dim]任务已创建：{task_id}[/]"]

    try:
        await watch_task_until_done(task_id)
        logger.info(f"switch_stage: 任务完成 task_id={task_id}")
        lines.append("[bold green]✅ 场景切换完成[/]")
    except TaskFailedError as e:
        logger.error(f"switch_stage: 任务失败 task_id={task_id} error={e}")
        lines.append(f"[bold red]❌ 场景切换失败: {e}[/]")
    except TimeoutError:
        logger.warning(f"switch_stage: 轮询超时 task_id={task_id}")
        lines.append("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
    except Exception as e:
        logger.warning(f"switch_stage: 等待任务失败 task_id={task_id} error={e}")
        lines.append(f"[bold red]❌ 等待任务失败: {e}[/]")

    return "\n".join(lines)
