"""副本本体记忆归档模块

在副本退出、实体销毁之前，以「副本本体」的拟人化视角，对本次副本中所有
场景与角色实体的事实记忆（Human/AI/Tool 消息）做一次总结与压缩。

设计约束（当前阶段）：
  - 只读取实体上下文，绝不修改任何实体上下文、组件或游戏状态；
  - 与 CombatArchiveSystem 完全独立，互不依赖、互不污染；
  - 压缩结果当前不落盘、不写回任何 AgentContext，仅通过日志输出并返回给调用方，
    供观察验证后再决定后续落点。
"""

from typing import List, Optional, Sequence, Set, Tuple
from loguru import logger

from ..deepseek import DeepSeekClient, MODEL_FLASH
from ..entitas import Entity
from ..game.dbg_game import DBGGame
from ..models import (
    BaseMessage,
    Dungeon,
    SystemMessage,
    get_buffer_string,
)


###################################################################################################################################################################
def _build_dungeon_persona(dungeon: Dungeon) -> SystemMessage:
    """构建副本本体的拟人化系统提示词（人设来源：dungeon.premise）。"""

    premise = dungeon.premise or "（无）"

    return SystemMessage(
        content=(
            f"你是副本「{dungeon.name}」本身的意识化身，是的拟人化人格。\n"
            f"\n"
            f"你的身份设定（premise）：\n"
            f"{premise}\n"
            f"\n"
            f"你能俯瞰并感知副本内每一个场景与每一个角色身上发生过的一切。"
            f"你以副本本体的第一人称视角，负责在副本结束时对全部事实记忆进行总结与压缩。"
        )
    )


###################################################################################################################################################################
def _build_entity_fact_block(
    label: str,
    entity: Entity,
    messages: Sequence[BaseMessage],
) -> str:
    """将单个实体的上下文（跳过 SystemMessage）拼接为一段事实文本。"""

    # 只总结 Human/AI/Tool 的事件内容，跳过首条 SystemMessage（人设/规则）
    facts = [msg for msg in messages if not isinstance(msg, SystemMessage)]

    header = f"## {label}：{entity.name}"

    if not facts:
        return f"{header}\n（本次副本中无事实记忆）"

    buffer = get_buffer_string(
        facts,
        human_prefix="Human",
        ai_prefix=f"AI({entity.name})",
        tool_prefix=f"Tool({entity.name})",
    )
    return f"{header}\n{buffer}"


###################################################################################################################################################################
def _build_archive_prompt(dungeon: Dungeon, facts_block: str) -> str:
    """构建副本本体归档总结提示词。"""

    return f"""# 任务：以副本本体的视角，总结并压缩本次副本的全部事实记忆。

以下是本次副本运行中，所有场景与角色留下的事实记忆（已去除各实体的系统人设，只保留事件内容）：

{facts_block}

## 要求
- 站在副本「{dungeon.name}」这一拟人化本体的第一人称视角，连贯地总结；
- 提炼关键事实：发生了什么、涉及哪些场景与角色、过程与结果；
- 压缩冗余与重复，输出一段简洁的中文总结正文；
- 只输出总结正文，不要额外解释或客套。"""


###################################################################################################################################################################
def _collect_dungeon_entities(
    dbg_game: DBGGame,
    dungeon: Dungeon,
) -> List[Tuple[str, Entity]]:
    """按（场景、其角色）的顺序收集副本实体，去重并保持稳定顺序。

    返回 (label, entity) 列表，label 用于提示词中的分组标题。
    """

    entities: List[Tuple[str, Entity]] = []
    seen: Set[str] = set()

    for room in dungeon.rooms:

        # 场景实体
        stage_entity = dbg_game.get_stage_entity(room.stage.name)
        if stage_entity is not None and stage_entity.name not in seen:
            seen.add(stage_entity.name)
            entities.append(("场景", stage_entity))

        # 角色实体
        for actor in room.stage.actors:
            actor_entity = dbg_game.get_actor_entity(actor.name)
            if actor_entity is not None and actor_entity.name not in seen:
                seen.add(actor_entity.name)
                entities.append(("角色", actor_entity))

    return entities


###################################################################################################################################################################
async def archive_dungeon(
    dbg_game: DBGGame,
    dungeon: Dungeon,
) -> Optional[str]:
    """以副本本体的拟人化视角，对本次副本所有场景/角色的事实记忆做总结压缩。

    只读取实体上下文，不写入任何状态；结果仅通过日志输出并返回给调用方。
    任何异常都会被捕获并记录，绝不向上抛出以阻断副本退出流程。
    """

    try:

        # 1. 检索副本中所有 actor/stage 实体（与 teardown 相同的数据来源）
        entities = _collect_dungeon_entities(dbg_game, dungeon)
        if not entities:
            logger.warning(f"[archive_dungeon] 副本 {dungeon.name!r} 没有可归档的实体")
            return None

        # 2. 取出每个实体的 agent context，过滤出事实记忆并拼接
        facts_block = "\n\n".join(
            _build_entity_fact_block(
                label,
                entity,
                dbg_game.get_agent_context(entity).context,
            )
            for label, entity in entities
        )

        # 3. 以副本本体人设 + 全部事实记忆，驱动一个额外的 agent 做总结压缩
        persona = _build_dungeon_persona(dungeon)
        prompt = _build_archive_prompt(dungeon, facts_block)

        client = DeepSeekClient(
            name=f"dungeon:{dungeon.name}",
            prompt=prompt,
            context=[persona],
            model=MODEL_FLASH,
            thinking=False,
        )
        await client.chat()

        summary = client.response_content
        if not summary:
            logger.warning(f"[archive_dungeon] 副本 {dungeon.name!r} 归档结果为空")
            return None

        logger.info(f"[archive_dungeon] 副本「{dungeon.name}」本体总结:\n{summary}")
        return summary

    except Exception as e:
        logger.error(
            f"[archive_dungeon] 副本 {dungeon.name!r} 归档失败: "
            f"{type(e).__name__}: {e}"
        )
        return None
