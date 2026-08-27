"""副本导演记忆模块 —— 副本导演（DungeonDirectorComponent）的记忆积累与归档"""

from typing import Final, List, Optional, Sequence, Set, Tuple

from loguru import logger

from ..deepseek import MODEL_FLASH, DeepSeekClient
from ..entitas import Entity, Matcher
from ..game.dbg_game import DBGGame
from ..utils import prompt_builder
from ..models import (
    AnyDungeonRoom,
    BaseMessage,
    Dungeon,
    DungeonDirectorComponent,
    HumanMessage,
    SystemMessage,
    WorldDirectorComponent,
    get_buffer_string,
)

# 实体记忆块之间的长分割线
_SEP: Final[str] = "-" * 100


###################################################################################################################################################################
def _get_dungeon_director_entity(
    dbg_game: DBGGame,
) -> Optional[Entity]:
    """获取副本导演 world system 实体（首个符合条件的实体）。

    找不到实体（或缺少 DungeonDirectorComponent）时返回 None，表示应跳过记录/归档。
    """

    entities = dbg_game.get_group(
        Matcher(all_of=[DungeonDirectorComponent])
    ).entities.copy()

    if not entities:
        return None

    # 取第一个符合条件的实体作为副本导演实体
    entity = next(iter(entities))
    logger.debug(f"[dungeon_director] 找到副本导演实体：{entity.name!r}")
    return entity


###################################################################################################################################################################
def _get_world_director_entity(
    dbg_game: DBGGame,
) -> Optional[Entity]:
    """获取世界导演（桌游 GM）world system 实体（首个符合条件的实体）。"""

    entities = dbg_game.get_group(
        Matcher(all_of=[WorldDirectorComponent])
    ).entities.copy()

    if not entities:
        return None

    entity = next(iter(entities))
    logger.debug(f"[archive_dungeon] 找到世界导演实体：{entity.name!r}")
    return entity


###################################################################################################################################################################
def _notify_world_director(
    dbg_game: DBGGame,
    dungeon: Dungeon,
    summary: str,
) -> Optional[Entity]:
    """将副本归档总结作为「世界变化通知」写入世界导演的记忆。

    只追加消息、不触发 LLM 思考；世界导演后续的决策由未来 action/system 驱动。
    返回世界导演实体（找不到时返回 None）。
    """

    world_director_entity = _get_world_director_entity(dbg_game)
    if world_director_entity is None:
        logger.warning("[archive_dungeon] 未找到世界导演实体，跳过世界变化通知")
        return None

    notification = HumanMessage(
        content=(
            f"# 世界变化通知\n"
            f"\n"
            f"副本「{dungeon.name}」已结束。\n"
            f"设定（profile）：{dungeon.profile or '（无）'}\n"
            f"\n"
            f"副本导演归档总结：\n"
            f"{summary}\n"
            f"\n"
            f"请据此思考：这次副本的结束让世界状态发生了怎样的变化？后续走向应如何推进与演变？"
        )
    )

    dbg_game.add_human_message(world_director_entity, notification)
    logger.info(
        f"[archive_dungeon] 已向世界导演 {world_director_entity.name!r} "
        f"发送世界变化通知（副本：{dungeon.name!r}）"
    )
    return world_director_entity


###################################################################################################################################################################
@prompt_builder
def _build_room_setting_block(room: AnyDungeonRoom) -> str:
    """构建单个房间的设定文本块（场景 + 角色，不含 Round/Combat 等运行时战斗细节）。"""

    stage = room.stage
    lines: List[str] = [
        f"### 房间（类型：{room.type}）",
        f"- 场景：{stage.name}（类型：{stage.type}）",
        f"- 场景设定：{stage.profile}",
    ]

    for actor in stage.actors:
        lines.append(f"- 角色：{actor.name}（类型：{actor.type}）")
        lines.append(f"  - 角色设定：{actor.profile}")
        lines.append(f"  - 外观：{actor.base_body}")

    return "\n".join(lines)


###################################################################################################################################################################
@prompt_builder
def _build_room_sequence_block(dungeon: Dungeon) -> str:
    """构建副本房间序列骨架（仅序号/类型/场景名，不含 profile 与角色细节，细节随各房间结束逐步揭露）。"""

    lines: List[str] = [f"### 房间序列（共 {len(dungeon.rooms)} 个）"]
    for index, room in enumerate(dungeon.rooms, start=1):
        lines.append(f"{index}. [{room.type}] {room.stage.name}")

    return "\n".join(lines)


###################################################################################################################################################################
@prompt_builder
def _build_entity_fact_block(
    label: str,
    entity_name: str,
    messages: Sequence[BaseMessage],
) -> str:
    """将单个实体的记忆（跳过 SystemMessage）整理为一段事实记忆文本。

    模块标题使用纯文本（不使用 # 标题，避免与消息内容中的多级 # 混淆），
    消息内容沿用 Human / AI(实体名) / Tool(实体名) 的角色标记。
    """

    # 只保留 Human/AI/Tool 的事件内容，跳过首条 SystemMessage（人设/规则）
    facts = [msg for msg in messages if not isinstance(msg, SystemMessage)]

    header = f"{label}：{entity_name}（事实记忆）"

    if not facts:
        return f"{header}\n（本次房间中无事实记忆）"

    buffer = get_buffer_string(
        facts,
        human_prefix="Human",
        ai_prefix=f"AI({entity_name})",
        tool_prefix=f"Tool({entity_name})",
    )
    return f"{header}\n{buffer}"


###################################################################################################################################################################
def _collect_room_entities(
    dbg_game: DBGGame,
    room: AnyDungeonRoom,
) -> List[Tuple[str, Entity]]:
    """收集单个房间内的场景与角色实体，去重并保持稳定顺序。

    返回 (label, entity) 列表，label 用于提示词中的分组标题。
    """

    entities: List[Tuple[str, Entity]] = []
    seen: Set[str] = set()

    stage_entity = dbg_game.get_stage_entity(room.stage.name)
    if stage_entity is not None and stage_entity.name not in seen:
        seen.add(stage_entity.name)
        entities.append(("场景", stage_entity))

    for actor in room.stage.actors:
        actor_entity = dbg_game.get_actor_entity(actor.name)
        if actor_entity is not None and actor_entity.name not in seen:
            seen.add(actor_entity.name)
            entities.append(("角色", actor_entity))

    return entities


###################################################################################################################################################################
def notify_dungeon_director_entered(
    dbg_game: DBGGame,
    dungeon: Dungeon,
    room: AnyDungeonRoom,
) -> None:
    """副本开局进入首个房间时，向副本导演记录起始设定，作为其记忆的第一条事实。

    找不到副本导演实体时静默跳过，不阻断副本进入流程。
    """

    director_entity = _get_dungeon_director_entity(dbg_game)
    if director_entity is None:
        logger.warning("[dungeon_director] 未找到副本导演实体，跳过开局记录")
        return

    message = HumanMessage(
        content=(
            f"# 副本开始\n"
            f"\n"
            f"副本「{dungeon.name}」启动。设定（profile）：{dungeon.profile or '（无）'}\n"
            f"\n"
            f"{_build_room_sequence_block(dungeon)}\n"
            f"\n"
            f"## 首个房间详情\n"
            f"{_build_room_setting_block(room)}"
        )
    )
    dbg_game.add_human_message(director_entity, message)
    logger.debug(f"[dungeon_director] 已记录副本开局：{dungeon.name!r}")


###################################################################################################################################################################
def notify_dungeon_director_room_ended(
    dbg_game: DBGGame,
    dungeon: Dungeon,
    room: AnyDungeonRoom,
) -> None:
    """房间结束时（任意房间类型，含入口房间），向副本导演追加该房间的事实记忆。

    找不到副本导演实体、或房间没有可记录实体时静默跳过，不阻断副本推进/退出流程。
    """

    director_entity = _get_dungeon_director_entity(dbg_game)
    if director_entity is None:
        logger.warning("[dungeon_director] 未找到副本导演实体，跳过房间结束记录")
        return

    room_entities = _collect_room_entities(dbg_game, room)
    if not room_entities:
        logger.warning(f"[dungeon_director] 房间 {room.stage.name!r} 没有可记录的实体")
        return

    facts_block = ("\n" + _SEP + "\n").join(
        _build_entity_fact_block(
            label,
            entity.name,
            dbg_game.get_agent_memory(entity).messages,
        )
        for label, entity in room_entities
    )

    message = HumanMessage(
        content=f"# 房间结束：{room.stage.name}（类型：{room.type}）\n\n{facts_block}"
    )
    dbg_game.add_human_message(director_entity, message)
    logger.debug(f"[dungeon_director] 已记录房间结束：{room.stage.name!r}")


###################################################################################################################################################################
async def debug_probe_dungeon_director_reasoning(
    dbg_game: DBGGame,
    dungeon: Dungeon,
) -> None:
    """调试探针：让副本导演基于当前已积累的记忆做一次通用推理问答。

    仅用于人工核对记忆管理是否符合预期（结果打印在 DeepSeekClient 的日志中），
    只读取记忆不追加消息，不影响副本导演的正式记忆。
    """

    director_entity = _get_dungeon_director_entity(dbg_game)
    if director_entity is None:
        logger.warning("[dungeon_director] 未找到副本导演实体，跳过调试探针")
        return

    agent_memory = dbg_game.get_agent_memory(director_entity)

    prompt = "调试探针：到目前为止都发生了什么？你后续希望发生什么？"

    client = DeepSeekClient(
        name=dungeon.name,
        full_prompt=prompt,
        messages=agent_memory.messages,
        model=MODEL_FLASH,
    )
    await client.chat()


###################################################################################################################################################################
async def archive_dungeon(
    dbg_game: DBGGame,
    dungeon: Dungeon,
) -> None:
    """副本结束时，让副本导演基于其已积累的记忆输出总结，转交世界导演；随后重置其记忆。

    副本导演的记忆生命周期限定于当前副本：无论总结是否成功，归档流程结束后都会重置回
    仅剩 system prompt 的初始状态，供下一个副本从零开始积累。
    任何异常都会被捕获并记录，绝不向上抛出以阻断副本退出流程。
    """

    director_entity = _get_dungeon_director_entity(dbg_game)
    if director_entity is None:
        logger.warning("[archive_dungeon] 未找到副本导演实体，归档跳过")
        return None

    agent_memory = dbg_game.get_agent_memory(director_entity)

    try:

        # 基于副本导演已积累的记忆（开局记录 + 各房间结束记录），驱动其输出总结
        prompt = (
            f"# 任务：基于你已积累的记忆，总结并压缩本次副本「{dungeon.name}」的全部经历。\n"
            f"\n"
            f"站在你（副本导演）亲历本次副本的第一人称视角，输出一段连贯的中文总结正文。"
            f"整段不分段不空行，纯文本输出。"
        )

        client = DeepSeekClient(
            name=f"dungeon:{dungeon.name}",
            full_prompt=prompt,
            messages=agent_memory.messages,
            model=MODEL_FLASH,
        )
        await client.chat()

        summary = client.response_content
        if not summary:
            logger.warning(f"[archive_dungeon] 副本 {dungeon.name!r} 归档结果为空")
            return None

        logger.info(f"[archive_dungeon] 副本「{dungeon.name}」导演总结:\n{summary}")

        # 将总结作为「世界变化通知」写入世界导演（GM）的记忆
        _notify_world_director(dbg_game, dungeon, summary)

    except Exception as e:
        logger.error(
            f"[archive_dungeon] 副本 {dungeon.name!r} 归档失败: "
            f"{type(e).__name__}: {e}"
        )
    finally:

        # 副本导演记忆生命周期限定于当前副本：归档后重置，仅保留首条 system prompt
        assert isinstance(
            agent_memory.messages[0], SystemMessage
        ), "副本导演 agent memory 首条消息必须是 SystemMessage"
        del agent_memory.messages[1:]
        logger.info(
            f"[archive_dungeon] 已重置副本导演记忆，保留 {len(agent_memory.messages)} 条消息"
        )
