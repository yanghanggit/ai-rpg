"""压缩命令：手动压缩指定实体/角色的 LLM 记忆，供 HomeScreen 的 /compact（/cp）调用。"""

from typing import List

from loguru import logger

from .server_client import (
    TaskFailedError,
    compact_context,
    fetch_entities_details,
    watch_task_until_done,
)
from .utils import display_name


async def compact_target(
    user_name: str,
    game_name: str,
    target: str,
) -> str:
    """压缩指定实体的记忆，返回可写入正文区的富文本字符串。

    Args:
        user_name: 用户名
        game_name: 游戏名称
        target: 目标实体名（角色/怪物/场景/世界，不含 @ 前缀）

    Returns:
        可写入 RichLog 的富文本字符串；目标非法时返回提示文本。
    """
    logger.info(
        f"compact_target: 压缩记忆 user_name={user_name} game_name={game_name} "
        f"target={target}"
    )

    # 校验目标实体存在（任意类型：角色/怪物/场景/世界）
    details_resp = await fetch_entities_details(user_name, game_name, [target])
    if not details_resp.entities:
        return (
            f"[yellow]目标 {display_name(target)} 不存在，"
            f"请核对实体名（可用 /browse 查看）。[/]"
        )

    resp = await compact_context(user_name, game_name, target)
    job_id = resp.job_id
    logger.info(f"compact_target: 任务已创建 job_id={job_id}")

    lines: List[str] = [f"[dim]任务已创建：{job_id}[/]"]

    try:
        await watch_task_until_done(job_id)
        logger.info(f"compact_target: 任务完成 job_id={job_id}")
        lines.append("[bold green]✅ 上下文压缩完成[/]")
    except TaskFailedError as e:
        logger.error(f"compact_target: 任务失败 job_id={job_id} error={e}")
        lines.append(f"[bold red]❌ 上下文压缩失败: {e}[/]")
    except TimeoutError:
        logger.warning(f"compact_target: 轮询超时 job_id={job_id}")
        lines.append("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
    except Exception as e:
        logger.warning(f"compact_target: 等待任务失败 job_id={job_id} error={e}")
        lines.append(f"[bold red]❌ 等待任务失败: {e}[/]")

    return "\n".join(lines)
