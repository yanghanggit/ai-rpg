"""对话命令：向当前场景 NPC 说话，供 HomeScreen 的 /speak（/sp）调用。"""

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


async def speak_to(
    user_name: str,
    game_name: str,
    player_actor: str,
    target: str,
    content: str,
) -> str:
    """向当前场景的目标 NPC 发送对话，返回可写入正文区的富文本字符串。

    Args:
        user_name: 用户名
        game_name: 游戏名称
        player_actor: 玩家角色名，用于定位当前场景并排除玩家自身
        target: 对话目标角色名（不含 @ 前缀）
        content: 对话内容

    Returns:
        可写入 RichLog 的富文本字符串；目标非法时返回提示文本。

    Raises:
        获取场景列表或发送对话请求失败时向上抛出异常，由调用方决定如何展示错误。
    """
    logger.info(
        f"speak_to: 对话 user_name={user_name} game_name={game_name} "
        f"target={target} content={content}"
    )
    stages_resp = await fetch_stages_state(user_name, game_name)

    # 收集全部场景中的全部角色（服务端说话动作只校验目标是否存在，不限制同场景）
    all_actors: set[str] = set()
    current_actors: List[str] = []
    for stage, actors in stages_resp.mapping.items():
        all_actors.update(actors)
        if player_actor in actors:
            current_actors = actors

    if target == player_actor:
        return "[yellow]不能对自己说话，请选择 NPC。[/]"

    if target not in all_actors:
        npcs = [a for a in current_actors if a != player_actor]
        if npcs:
            names = "、".join(display_name(a) for a in npcs)
            return (
                f"[yellow]目标 {display_name(target)} 不存在，"
                f"请核对角色名。当前场景可对话：{names}[/]"
            )
        return f"[yellow]目标 {display_name(target)} 不存在，" f"可用 /stage 查看。[/]"

    resp = await home_player_action(
        user_name,
        game_name,
        HomePlayerActionType.SPEAK,
        {"target": target, "content": content},
    )
    job_id = resp.job_id
    logger.info(f"speak_to: 任务已创建 job_id={job_id}")

    lines: List[str] = [f"[dim]任务已创建：{job_id}[/]"]

    try:
        await watch_task_until_done(job_id)
        logger.info(f"speak_to: 任务完成 job_id={job_id}")
        lines.append("[bold green]✅ 对话完成[/]")
    except TaskFailedError as e:
        logger.error(f"speak_to: 任务失败 job_id={job_id} error={e}")
        lines.append(f"[bold red]❌ 对话失败: {e}[/]")
    except TimeoutError:
        logger.warning(f"speak_to: 轮询超时 job_id={job_id}")
        lines.append("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
    except Exception as e:
        logger.warning(f"speak_to: 等待任务失败 job_id={job_id} error={e}")
        lines.append(f"[bold red]❌ 等待任务失败: {e}[/]")

    return "\n".join(lines)
