"""副本怪物生成系统"""

from functools import partial
from typing import Dict, Final, List, final, override
from loguru import logger
from pydantic import BaseModel, Field
from ..deepseek import agent_loop, ToolDefinition, ToolFunction
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    AssembleDungeonAction,
    GenerateDungeonActorsAction,
)
from ..models.dungeon_generation import (
    DungeonActorBlueprint,
    DungeonActorData,
    DungeonBlueprint,
    DungeonRoomBlueprint,
    DungeonRoomData,
)


####################################################################################################################################
def _build_actor_tool(combat_rooms: List[DungeonRoomData]) -> ToolDefinition:
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
                    "character_sheet_name": {
                        "type": "string",
                        "description": "角色英文标识，snake_case 格式（如 bone_crawler、mist_spirit），所有怪物标识不重复",
                    },
                    "profile": {
                        "type": "string",
                        "description": "第一人称 AI 扮演描述，50-100字，描述该角色的性格、行为倾向、与所处房间的关系；禁止出现战斗数值、技能名称、等级等游戏机制词汇",
                    },
                    "base_body": {
                        "type": "string",
                        "description": "第三人称外观描述，30-60字，描述该角色的外观、材质、动态特征；禁止出现战斗数值、技能名称、等级等游戏机制词汇",
                    },
                },
                "required": [
                    "room_name",
                    "actor_name",
                    "character_sheet_name",
                    "profile",
                    "base_body",
                ],
            },
        )
    )


####################################################################################################################################
def _build_dungeon_actors_prompt(
    dungeon_name: str, profile: str, combat_rooms: List[DungeonRoomData]
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

工作流程：为每个怪物调用一次 record_dungeon_actor 写入其设定（可在一次回复中并行多次调用），全部写完后结束本次对话。"""


####################################################################################################################################
class _ActorsResult(BaseModel):
    """record_dungeon_actor handler 的结果容器（跨多次调用累积）。"""

    actors: List[DungeonActorData] = Field(default_factory=list)


####################################################################################################################################
def _handle_record_dungeon_actor(
    result: _ActorsResult,
    room_name: str,
    actor_name: str,
    character_sheet_name: str,
    profile: str,
    base_body: str,
) -> str:
    """处理 record_dungeon_actor 工具调用，累积到结果容器。"""
    record = DungeonActorData(
        room_name=room_name,
        actor_name=actor_name,
        character_sheet_name=character_sheet_name,
        profile=profile,
        base_body=base_body,
    )
    result.actors.append(record)
    logger.info(
        f"[GenerateDungeonActorsSystem] record_dungeon_actor 执行:\n"
        f"  actor_name:           {actor_name}\n"
        f"  room_name:            {room_name}\n"
        f"  character_sheet_name: {character_sheet_name}\n"
        f"  累计: {len(result.actors)} 个"
    )
    # 返回结构化 JSON 文本，作为 ToolMessage 进入 agent context，供后续步骤的 LLM 记忆使用
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
        return {Matcher(GenerateDungeonActorsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(GenerateDungeonActorsAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        assert len(entities) == 1, "同时存在多个 GenerateDungeonActorsAction，数据异常"
        entity = entities[0]
        await self._run(entity)

    ####################################################################################################################################
    async def _run(self, entity: Entity) -> None:
        action_comp = entity.get(GenerateDungeonActorsAction)
        dungeon_name = action_comp.dungeon_name
        dungeon_profile = action_comp.dungeon_profile
        rooms = action_comp.rooms

        logger.info(
            f"[GenerateDungeonActorsSystem] Step 3 开始: dungeon={dungeon_name}, rooms={len(rooms)}"
        )

        if not rooms:
            logger.error(
                "[GenerateDungeonActorsSystem] Step 2 产物 rooms 为空，无法生成怪物"
            )
            return

        combat_rooms = [r for r in rooms if r.room_type == "combat"]
        if not combat_rooms:
            logger.error("[GenerateDungeonActorsSystem] 没有 combat 房间，无法生成怪物")
            return

        result = _ActorsResult()

        success = await agent_loop(
            name=entity.name,
            prompt=_build_dungeon_actors_prompt(
                dungeon_name=dungeon_name,
                profile=dungeon_profile,
                combat_rooms=combat_rooms,
            ),
            # 直接传入实体的持久化 agent context：agent_loop 原地追加
            context=self._game.get_agent_context(entity).context,
            tools=[_build_actor_tool(combat_rooms)],
            handlers={
                "record_dungeon_actor": partial(_handle_record_dungeon_actor, result),
            },
            max_rounds=5,
        )

        if not success:
            logger.error("[GenerateDungeonActorsSystem] Step 3 agent_loop 失败，中止")
            return

        if not result.actors:
            logger.error(
                "[GenerateDungeonActorsSystem] Step 3 LLM 已 stop "
                "但未调用 record_dungeon_actor，中止"
            )
            return

        # 校验归属与数量：房间必须合法，每个 combat 房间数量必须匹配
        room_name_set = {r.room_name for r in rooms}
        combat_name_set = {r.room_name for r in combat_rooms}
        actors_by_room: Dict[str, List[DungeonActorBlueprint]] = {}
        for record in result.actors:
            if record.room_name not in room_name_set:
                logger.error(
                    f"[GenerateDungeonActorsSystem] actor '{record.actor_name}' "
                    f"归属未知房间 '{record.room_name}'，中止"
                )
                return
            if record.room_name not in combat_name_set:
                logger.error(
                    f"[GenerateDungeonActorsSystem] actor '{record.actor_name}' "
                    f"归属 entry 房间 '{record.room_name}'，中止"
                )
                return
            actors_by_room.setdefault(record.room_name, []).append(
                DungeonActorBlueprint(
                    actor_name=record.actor_name,
                    character_sheet_name=record.character_sheet_name,
                    profile=record.profile,
                    base_body=record.base_body,
                )
            )

        for room in combat_rooms:
            actual = len(actors_by_room.get(room.room_name, []))
            if actual != room.actor_count:
                logger.error(
                    f"[GenerateDungeonActorsSystem] combat 房间 '{room.room_name}' "
                    f"期望 {room.actor_count} 个怪物，实际 {actual} 个，中止"
                )
                return

        # 组装 DungeonBlueprint
        blueprint = DungeonBlueprint(
            dungeon_name=dungeon_name,
            profile=dungeon_profile,
        )
        for i, room in enumerate(rooms, start=1):
            if room.room_type == "entry":
                room_bp = DungeonRoomBlueprint(
                    room_type=room.room_type,
                    room_name=room.room_name,
                    profile_name=room.profile_name,
                    profile=room.profile,
                    actors=[],
                )
                blueprint.rooms.append(room_bp)
                logger.info(
                    f"[GenerateDungeonActorsSystem] Entry room {i}/{len(rooms)} 写入 blueprint:\n"
                    f"  room_name: {room_bp.room_name}"
                )
                continue

            room_bp = DungeonRoomBlueprint(
                room_type=room.room_type,
                room_name=room.room_name,
                profile_name=room.profile_name,
                profile=room.profile,
                actors=actors_by_room[room.room_name],
            )
            blueprint.rooms.append(room_bp)
            logger.info(
                f"[GenerateDungeonActorsSystem] Room+Actors {i}/{len(rooms)} 写入 blueprint:\n"
                f"  room_name: {room_bp.room_name}\n"
                f"  actors ({len(room_bp.actors)}): "
                + ", ".join(a.actor_name for a in room_bp.actors)
            )

        logger.info(
            f"[GenerateDungeonActorsSystem] Step 3 完成:\n"
            f"  dungeon_name: {blueprint.dungeon_name}\n"
            f"  rooms ({len(blueprint.rooms)}): "
            + ", ".join(
                f"{r.room_name}({len(r.actors)} actors)" for r in blueprint.rooms
            )
        )

        entity.replace(AssembleDungeonAction, entity.name, dungeon_name, blueprint)
        logger.info(
            f"[GenerateDungeonActorsSystem] 添加 AssembleDungeonAction: dungeon={dungeon_name}"
        )
