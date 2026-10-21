"""副本怪物生成系统：按房间约束生成怪物及其预置牌库成员。"""

from functools import partial
from typing import Dict, Final, List, Mapping, final, override

from loguru import logger
from pydantic import BaseModel, Field

from ..deepseek import agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..llm import ToolDefinition, ToolFunction
from ..models import (
    DungeonActorDraft,
    DungeonRoomDraft,
    GenerateDungeonAction,
)
from ..utils import prompt_builder

####################################################################################################################################
MOTIF_DESCRIPTION: Final[str] = (
    "该怪物的艺术锚点，供后续为它创作卡牌时取材，四行固定格式：`**母题**: 一句话立意` / `**意象**: 可反复取用的物件、质感、动作（逗号分隔，必须场景中立，不得指向某个会消失的地点或在场者）` / `**禁忌**: 不得出现的意象与语气` / `**口吻**: 命名时的自称、称谓、句子长短`。四行之间用**真实换行**分隔，不要写成 `\\n` 转义。禁止出现战斗数值、技能名称、等级等游戏机制词汇。"
)


####################################################################################################################################
def _build_record_dungeon_actor_tool(
    combat_rooms: List[DungeonRoomDraft],
) -> ToolDefinition:
    """动态构建 record_dungeon_actor 工具定义。

    room_name 用 enum 约束为当前 combat 房间名集合，保证归属合法。
    """
    room_names = [r.room_name for r in combat_rooms]
    return ToolDefinition(
        function=ToolFunction(
            name="record_dungeon_actor",
            description="记录一个怪物的全部设定字段。",
            parameters={
                "type": "object",
                "properties": {
                    "room_name": {
                        "type": "string",
                        "enum": room_names,
                        "description": "怪物所属战斗房间全名，必须为上述房间之一",
                    },
                    "actor_name": {
                        "type": "string",
                        "description": "角色全名，采用「怪物.XXXX」格式，XXXX 体现该角色的特征",
                    },
                    "profile": {
                        "type": "string",
                        "description": "第一人称 AI 扮演描述，50-100字，描述该角色的性格、行为倾向、与所处房间的关系；禁止出现战斗数值、技能名称、等级等游戏机制词汇",
                    },
                    "base_body": {
                        "type": "string",
                        "description": "第三人称外观描述，30-60字，描述该角色的外观、材质、动态特征；禁止出现战斗数值、技能名称、等级等游戏机制词汇",
                    },
                    "motif": {
                        "type": "string",
                        "description": MOTIF_DESCRIPTION,
                    },
                },
                "required": [
                    "room_name",
                    "actor_name",
                    "profile",
                    "base_body",
                    "motif",
                ],
            },
        )
    )


####################################################################################################################################
@prompt_builder
def _build_dungeon_actors_prompt(
    dungeon_name: str, profile: str, combat_rooms: List[DungeonRoomDraft]
) -> str:
    """构建副本怪物批量生成的 LLM 提示词。"""

    total_actor_count = sum(r.actor_count for r in combat_rooms)
    room_lines = "\n".join(
        f"- {r.room_name}（需 {r.actor_count} 个怪物）：{r.profile}"
        for r in combat_rooms
    )
    return f"""# 任务：为副本的全部战斗房间创作所有怪物

## 副本信息

- **副本名称**：{dungeon_name}
- **整体设定**：{profile}

## 战斗房间与怪物数量要求

{room_lines}

共计 {total_actor_count} 个怪物，每个怪物必须用 room_name 指明其归属战斗房间。

工作流程：为每个怪物调用一次 record_dungeon_actor 写入其设定（可在一次回复中并行多次调用），全部写完后结束本次对话。

`motif` 是与 `profile` 同样重要的字段：它是这个怪物的**艺术锚点**，之后会用它来为这只怪物设计卡牌。母题、意象、禁忌、口吻都要只从这只怪物自身的设定里长出来，且必须**场景中立**（不得指向本房间、本副本的地点或在场者）。"""


####################################################################################################################################
class _ActorsResult(BaseModel):
    """record_dungeon_actor handler 的结果容器（跨多次调用累积）。"""

    actors: List[DungeonActorDraft] = Field(default_factory=list)


####################################################################################################################################
def _normalize_motif(motif: str) -> str:
    """规整 motif 文本：把模型偶发的字面 `\\n` 还原为真实换行（双转义是常见失误）。"""
    return motif.replace("\\n", "\n").strip()


####################################################################################################################################
def _handle_record_dungeon_actor(
    result: _ActorsResult,
    quotas: Mapping[str, int],
    room_name: str,
    actor_name: str,
    profile: str,
    base_body: str,
    motif: str = "",
) -> str:
    """处理 record_dungeon_actor 工具调用，累积到结果容器。

    `quotas`（战斗房间 → 怪物数）在这里就把关：未知房间、开场房间、以及**超过配额**
    都只返回错误文本而不入账，让 LLM 在同一轮内自行纠正（而不是等 loop 结束后整体中止）。
    """
    quota = quotas.get(room_name)
    if quota is None:
        return f"错误：{room_name!r} 不是本次需要怪物的战斗房间（可选：{'、'.join(quotas)}）。请改用正确的房间名。"

    recorded = sum(1 for actor in result.actors if actor.room_name == room_name)
    if recorded >= quota:
        return f"错误：{room_name} 只需要 {quota} 个怪物，已满额。请不要再为该房间记录怪物。"

    record = DungeonActorDraft(
        room_name=room_name,
        actor_name=actor_name,
        profile=profile,
        base_body=base_body,
        motif=_normalize_motif(motif),
    )
    result.actors.append(record)
    logger.info(
        f"[GenerateDungeonActorsSystem] record_dungeon_actor 执行:\n  actor_name: {actor_name}\n  room_name:  {room_name}\n  累计: {len(result.actors)} 个"
    )
    # 返回结构化 JSON 文本，作为 ToolMessage 进入 agent memory，供后续步骤的 LLM 记忆使用
    return record.model_dump_json(ensure_ascii=False)


####################################################################################################################################
@final
class GenerateDungeonActorsSystem(ReactiveProcessor):
    """副本怪物生成系统"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(GenerateDungeonAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(GenerateDungeonAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        assert len(entities) == 1, "同时存在多个 GenerateDungeonAction，数据异常"
        entity = entities[0]
        await self._run(entity)

    ####################################################################################################################################
    async def _run(self, entity: Entity) -> None:
        draft = self._game._dungeon_draft
        if draft is None:
            logger.error("[GenerateDungeonActorsSystem] 中间过程数据缺失，跳过")
            return

        dungeon_name = draft.dungeon_name
        dungeon_profile = draft.profile
        rooms = draft.rooms

        logger.info(
            f"[GenerateDungeonActorsSystem] 开始: dungeon={dungeon_name}, rooms={len(rooms)}"
        )

        if not rooms:
            logger.error("[GenerateDungeonActorsSystem] rooms 为空，无法生成怪物")
            return

        combat_rooms = [r for r in rooms if r.room_type == "combat"]
        if not combat_rooms:
            logger.error("[GenerateDungeonActorsSystem] 没有 combat 房间，无法生成怪物")
            return

        result = _ActorsResult()
        actor_tool = _build_record_dungeon_actor_tool(combat_rooms)
        quotas = {room.room_name: room.actor_count for room in combat_rooms}

        success = await agent_loop(
            name=entity.name,
            input_message=_build_dungeon_actors_prompt(
                dungeon_name=dungeon_name,
                profile=dungeon_profile,
                combat_rooms=combat_rooms,
            ),
            # 直接传入实体的持久化 agent memory：agent_loop 原地追加
            messages=self._game.get_agent_memory(entity).messages,
            tools=[actor_tool],
            handlers={
                actor_tool.function.name: partial(
                    _handle_record_dungeon_actor, result, quotas
                ),
            },
            max_rounds=5,
        )

        if not success:
            logger.error("[GenerateDungeonActorsSystem] agent_loop 失败，中止")
            return

        if not result.actors:
            logger.error(
                "[GenerateDungeonActorsSystem] LLM 已 stop 但未调用 record_dungeon_actor，中止"
            )
            return

        # 校验归属与数量：房间必须合法，每个 combat 房间数量必须匹配
        room_name_set = {r.room_name for r in rooms}
        combat_name_set = {r.room_name for r in combat_rooms}
        actors_by_room: Dict[str, List[DungeonActorDraft]] = {}
        for record in result.actors:
            if record.room_name not in room_name_set:
                logger.error(
                    f"[GenerateDungeonActorsSystem] actor '{record.actor_name}' 归属未知房间 '{record.room_name}'，中止"
                )
                return
            if record.room_name not in combat_name_set:
                logger.error(
                    f"[GenerateDungeonActorsSystem] actor '{record.actor_name}' 归属 opening 房间 '{record.room_name}'，中止"
                )
                return
            actors_by_room.setdefault(record.room_name, []).append(record)

        for room in combat_rooms:
            actual = len(actors_by_room.get(room.room_name, []))
            if actual != room.actor_count:
                logger.error(
                    f"[GenerateDungeonActorsSystem] combat 房间 '{room.room_name}' 期望 {room.actor_count} 个怪物，实际 {actual} 个，中止"
                )
                return

        draft.actors = result.actors
        logger.info(
            f"[GenerateDungeonActorsSystem] 完成:\n  dungeon_name: {dungeon_name}\n  actors ({len(draft.actors)}): "
            + ", ".join(a.actor_name for a in draft.actors)
        )
