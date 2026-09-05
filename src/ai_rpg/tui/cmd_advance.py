"""推进家园命令：执行一轮 home 推进流程，供 HomeScreen 的 /advance（/a）调用。"""

from typing import List

from loguru import logger

from ..models import StagesStateResponse
from .server_client import (
    TaskFailedError,
    fetch_stages_state,
    home_advance,
    watch_task_until_done,
)


def _get_all_actors(stages_resp: StagesStateResponse) -> List[str]:
    """返回全部场景中出现过的全部角色（跨场景去重，保持首次出现顺序）。"""
    all_actors: List[str] = []
    seen: set[str] = set()
    for actors in stages_resp.mapping.values():
        for actor in actors:
            if actor not in seen:
                seen.add(actor)
                all_actors.append(actor)
    return all_actors


async def run_home_advance(user_name: str, game_name: str) -> str:
    """推进家园：对全部场景中的全部角色触发一轮规划与行动，返回结果文本。

    Args:
        user_name: 用户名
        game_name: 游戏名称

    Returns:
        可写入正文区的富文本字符串（任务 ID 及最终结果）。

    Raises:
        获取场景状态或触发推进请求失败时向上抛出异常，由调用方决定如何展示错误。
    """
    logger.info(
        f"run_home_advance: 开始推进 user_name={user_name} game_name={game_name}"
    )
    stages_resp = await fetch_stages_state(user_name, game_name)
    actor_names = _get_all_actors(stages_resp)

    if not actor_names:
        logger.error("run_home_advance: 没有可推进的角色")
        return "[bold red]❌ 当前没有可推进的角色[/]"

    resp = await home_advance(user_name, game_name, actor_names)
    job_id = resp.job_id
    logger.info(f"run_home_advance: 任务已创建 job_id={job_id}")

    lines: List[str] = [f"[dim]任务已创建：{job_id}[/]"]

    try:
        await watch_task_until_done(job_id)
        logger.info(f"run_home_advance: 任务完成 job_id={job_id}")
        lines.append(f"[bold green]✅ 任务完成 job_id={job_id}[/]")
    except TaskFailedError as e:
        logger.error(f"run_home_advance: 任务失败 job_id={job_id} error={e}")
        lines.append(f"[bold red]❌ 推进失败: {e}[/]")
    except TimeoutError:
        logger.warning(f"run_home_advance: 任务轮询超时 job_id={job_id}")
        lines.append("[bold yellow]⚠️ 推进超时，请检查服务器状态[/]")
    except Exception as e:
        logger.warning(f"run_home_advance: 等待任务失败 job_id={job_id} error={e}")
        lines.append(f"[bold red]❌ 等待任务失败: {e}[/]")

    return "\n".join(lines)
