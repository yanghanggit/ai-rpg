"""工坊命令：craft-consumable / craft-gear / craft-costume，供 HomeScreen 调用。"""

from typing import Awaitable, Callable, List

from loguru import logger

from ..models import HomeCraftItemResponse
from .server_client import (
    home_craft_costume_item,
    home_craft_gear_item,
    home_craft_item,
    watch_task_until_done,
)


async def _submit_craft(
    user_name: str,
    game_name: str,
    materials: List[str],
    craft_fn: Callable[[str, str, List[str]], Awaitable[HomeCraftItemResponse]],
    verb: str,
) -> str:
    """提交合成请求并等待后台任务完成，返回成功或失败文本。"""
    logger.info(
        f"{verb}: 提交 user_name={user_name} materials={materials}"
    )
    try:
        resp = await craft_fn(user_name, game_name, materials)
        await watch_task_until_done(resp.task_id)
    except Exception as e:
        logger.error(f"{verb}: 失败 materials={materials} error={e}")
        return f"[bold red]❌ {verb}失败: {e}[/]"

    logger.info(f"{verb}: 成功 materials={materials}")
    return f"[bold green]✅ {verb}完成，结果见 /list-items。[/]"


async def craft_consumable(
    user_name: str, game_name: str, materials: List[str]
) -> str:
    """合成消耗品，返回成功或失败文本。"""
    return await _submit_craft(
        user_name, game_name, materials, home_craft_item, "合成消耗品"
    )


async def craft_gear(
    user_name: str, game_name: str, materials: List[str]
) -> str:
    """锻造装备，返回成功或失败文本。"""
    return await _submit_craft(
        user_name, game_name, materials, home_craft_gear_item, "锻造装备"
    )


async def craft_costume(
    user_name: str, game_name: str, materials: List[str]
) -> str:
    """制作时装，返回成功或失败文本。"""
    return await _submit_craft(
        user_name, game_name, materials, home_craft_costume_item, "制作时装"
    )
