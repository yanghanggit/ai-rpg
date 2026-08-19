"""副本本体记忆归档模块

在副本退出、实体销毁之前，以「副本本体」的拟人化视角，对本次副本中所有
场景与角色实体的事实记忆（Human/AI/Tool 消息）做一次总结与压缩。

副本本体人设由 world system 实体「世界系统.副本本体」承载（见 demo/blueprints.py），
本模块通过标准 entity 方式 `get_agent_context(entity)` 读取其人设 context。

设计约束（当前阶段）：
  - 只读取实体上下文，绝不修改任何实体上下文、组件或游戏状态；
  - 与 CombatArchiveSystem 完全独立，互不依赖、互不污染；
  - 压缩结果当前不落盘、不写回任何 AgentContext，仅通过日志输出并返回给调用方，
    供观察验证后再决定后续落点。
"""

from typing import List, Optional, Sequence, Set, Tuple
from loguru import logger
from ..deepseek import DeepSeekClient, MODEL_FLASH
from ..entitas import Entity, Matcher
from ..game.dbg_game import DBGGame
from ..models import (
    BaseMessage,
    Dungeon,
    DungeonPersonaComponent,
    SystemMessage,
    get_buffer_string,
)


# 实体记忆块之间的长分割线
_SEP: str = "-" * 86


###################################################################################################################################################################
def _get_dungeon_persona_entity(
    dbg_game: DBGGame,
) -> Optional[Entity]:
    """获取副本本体 world system 实体（首个符合条件的实体）。

    找不到实体（或缺少 DungeonPersonaComponent）时返回 None，表示应跳过归档。
    """

    entities = dbg_game.get_group(
        Matcher(all_of=[DungeonPersonaComponent])
    ).entities.copy()

    if not entities:
        return None

    # 取第一个符合条件的实体作为副本本体实体
    entity = next(iter(entities))
    logger.debug(f"[archive_dungeon] 找到副本本体实体：{entity.name!r}")
    return entity


###################################################################################################################################################################
def _build_dungeon_setting_block(dungeon: Dungeon) -> str:
    """构建副本初始设定文本块（不含 Round/Combat 等运行时战斗细节）。"""

    lines: List[str] = [
        "### 副本",
        f"- 名称：{dungeon.name}",
        f"- 前提（premise）：{dungeon.premise or '（无）'}",
    ]

    for index, room in enumerate(dungeon.rooms, start=1):
        stage = room.stage
        lines.append(f"### 房间 {index}（类型：{room.type}）")
        lines.append(f"- 场景：{stage.name}（类型：{stage.stage_profile.type}）")
        lines.append(f"- 场景设定：{stage.stage_profile.profile}")

        for actor in stage.actors:
            sheet = actor.character_sheet
            lines.append(f"- 角色：{actor.name}（类型：{sheet.type}）")
            lines.append(f"  - 角色设定：{sheet.profile}")
            lines.append(f"  - 外观：{sheet.base_body}")

    return "\n".join(lines)


###################################################################################################################################################################
def _build_entity_fact_block(
    label: str,
    entity: Entity,
    messages: Sequence[BaseMessage],
) -> str:
    """将单个实体的上下文（跳过 SystemMessage）整理为一段事实记忆文本。

    模块标题使用纯文本（不使用 # 标题，避免与消息内容中的多级 # 混淆），
    消息内容沿用 Human / AI(实体名) / Tool(实体名) 的角色标记。
    """

    # 只保留 Human/AI/Tool 的事件内容，跳过首条 SystemMessage（人设/规则）
    facts = [msg for msg in messages if not isinstance(msg, SystemMessage)]

    header = f"{label}：{entity.name}（事实记忆）"

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
    """构建副本本体归档总结提示词（副本初始设定 + 运行时事实记忆）。"""

    setting_block = _build_dungeon_setting_block(dungeon)

    return f"""# 任务：以副本本体的视角，总结并压缩本次副本的全部事实记忆。

## 副本初始设定

{setting_block}

## 运行时事实记忆

{facts_block}

{_SEP}

## 要求

站在副本「{dungeon.name}」这一拟人化本体的第一人称视角，输出一段连贯的中文总结正文。整段不分段不空行，纯文本输出。"""


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

        # 1. 获取副本本体 world system 实体；缺失则跳过归档
        dungeon_persona_entity = _get_dungeon_persona_entity(dbg_game)
        if dungeon_persona_entity is None:
            logger.warning(f"[archive_dungeon] 未找到副本本体实体，归档跳过")
            return None

        # 2. 检索副本中所有 actor/stage 实体（与 teardown 相同的数据来源）
        entities = _collect_dungeon_entities(dbg_game, dungeon)
        if not entities:
            logger.warning(f"[archive_dungeon] 副本 {dungeon.name!r} 没有可归档的实体")
            return None

        # 3. 取出每个实体的 agent context，过滤出事实记忆，用长分割线拼接各实体模块
        facts_block = ("\n" + _SEP + "\n").join(
            _build_entity_fact_block(
                label,
                entity,
                dbg_game.get_agent_context(entity).context,
            )
            for label, entity in entities
        )

        # 4. 以副本本体人设 + 副本初始设定 + 运行时事实，驱动额外 agent 做总结压缩
        prompt = _build_archive_prompt(dungeon, facts_block)

        # 5. 调用 DeepSeekClient 进行归档总结
        client = DeepSeekClient(
            name=f"dungeon:{dungeon.name}",
            prompt=prompt,
            context=dbg_game.get_agent_context(dungeon_persona_entity).context,
            model=MODEL_FLASH,
            thinking=False,
        )
        await client.chat()

        # 6. 获取归档总结结果
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
