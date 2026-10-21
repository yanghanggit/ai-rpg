"""副本房间生成系统：产出房间序列与各房间的场景描述。"""

from functools import partial
from typing import Any, Dict, Final, List, Optional, final, override

from loguru import logger
from pydantic import BaseModel

from ..deepseek import agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..llm import ToolDefinition, ToolFunction
from ..models import (
    DEFAULT_MONSTERS_PER_COMBAT_ROOM,
    DEFAULT_OPENING_ROOM_COUNT,
    DungeonRoomDraft,
    GenerateDungeonAction,
)
from ..utils import prompt_builder


####################################################################################################################################
def _build_record_dungeon_rooms_tool(
    dungeon_room_count: int, opening_room_count: int
) -> ToolDefinition:
    """动态构建 record_dungeon_rooms 工具定义。

    副本共 dungeon_room_count 个房间：前 opening_room_count 个为开场（opening），
    其余为战斗房间（combat）。开场房间数取自结构常量，不由「总数减一」推断。
    """
    combat_room_count = dungeon_room_count - opening_room_count
    return ToolDefinition(
        function=ToolFunction(
            name="record_dungeon_rooms",
            description=(
                f"记录副本全部 {dungeon_room_count} 个房间：前 {opening_room_count} 个为开场（opening），其余 {combat_room_count} 个为战斗房间（combat）。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "dungeon_name": {
                        "type": "string",
                        "description": "副本全名，与副本设定中的 dungeon_name 一致",
                    },
                    "rooms": {
                        "type": "array",
                        "minItems": dungeon_room_count,
                        "maxItems": dungeon_room_count,
                        "items": {
                            "type": "object",
                            "properties": {
                                "room_type": {
                                    "type": "string",
                                    "enum": ["opening", "combat"],
                                    "description": (
                                        f"房间类型：'opening' = 开场房间（无战斗，纯场景氛围描写），'combat' = 战斗房间。前 {opening_room_count} 个房间必须为 'opening'，其余必须为 'combat'"
                                    ),
                                },
                                "room_name": {
                                    "type": "string",
                                    "description": "房间全名，采用「房间.XXXX」命名格式，体现该局部区域的核心特征，所有房间名称不重复",
                                },
                                "profile": {
                                    "type": "string",
                                    "description": "该房间的感官环境描写，50-100字，只描述「这里有什么」，避免直接点出具体角色身份/阵营名称与威胁评价性词汇",
                                },
                            },
                            "required": [
                                "room_type",
                                "room_name",
                                "profile",
                            ],
                        },
                    },
                },
                "required": ["dungeon_name", "rooms"],
            },
        )
    )


####################################################################################################################################
@prompt_builder
def _build_dungeon_rooms_prompt(
    dungeon_name: str,
    profile: str,
    dungeon_room_count: int,
    opening_room_count: int,
) -> str:
    """构建副本房间生成的 LLM 提示词（房间总数与开场 / 战斗拆分作为输入数据下发）。"""

    combat_room_count = dungeon_room_count - opening_room_count
    return f"""# 任务：为副本创作 {dungeon_room_count} 个房间

## 副本信息

- **副本名称**：{dungeon_name}
- **整体设定**：{profile}

共计 {dungeon_room_count} 个房间，房间类型与顺序必须严格遵守：

- **开场房间（room_type = "opening"）**：共 {opening_room_count} 个，位于序列最前，
  无战斗。描写副本门口的外部氛围——玩家站在副本门口的第一印象。
  不涉及任何怪物，纯粹的场景氛围铺垫。

- **战斗房间（room_type = "combat"）**：共 {combat_room_count} 个，紧随开场房间之后，
  从入口区域逐步深入到副本最深处。

工作流程：调用 record_dungeon_rooms 写入全部房间数据，确认无误后结束本次对话。"""


####################################################################################################################################
class _RoomsResult(BaseModel):
    """record_dungeon_rooms handler 的结果容器。"""

    dungeon_name: Optional[str] = None
    rooms: Optional[List[DungeonRoomDraft]] = None


####################################################################################################################################
def _handle_record_dungeon_rooms(
    result: _RoomsResult,
    monsters_per_combat_room: int,
    dungeon_name: str,
    rooms: List[Any],
) -> str:
    """处理 record_dungeon_rooms 工具调用。

    `monsters_per_combat_room` 由调用方按「显式规格 → 默认值」解析后传入；
    怪物数量不交给 LLM 填写。
    """
    room_items: List[DungeonRoomDraft] = []
    for r in rooms:
        room = DungeonRoomDraft(**r)
        room.actor_count = (
            0 if room.room_type == "opening" else (monsters_per_combat_room)
        )
        room_items.append(room)
    result.dungeon_name = dungeon_name
    result.rooms = room_items
    for i, room in enumerate(room_items, start=1):
        logger.info(
            f"[GenerateDungeonRoomsSystem] Room {i}/{len(room_items)}:\n  room_type:    {room.room_type}\n  room_name:    {room.room_name}\n  actor_count:  {room.actor_count}\n  profile:      {room.profile}"
        )
    logger.info(
        f"[GenerateDungeonRoomsSystem] record_dungeon_rooms 执行:\n  dungeon_name: {dungeon_name}\n  room_count:   {len(room_items)}"
    )
    # 返回结构化 JSON 文本，作为 ToolMessage 进入 agent memory，供后续步骤的 LLM 记忆使用
    return result.model_dump_json(ensure_ascii=False)


####################################################################################################################################
@final
class GenerateDungeonRoomsSystem(ReactiveProcessor):
    """副本房间生成系统"""

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
            logger.error("[GenerateDungeonRoomsSystem] 中间过程数据缺失，跳过")
            return

        dungeon_name = draft.dungeon_name
        dungeon_profile = draft.profile
        dungeon_room_count = draft.room_count

        # 开场房间数与每房间怪物数：显式规格优先，其次默认值
        action = entity.get(GenerateDungeonAction)
        opening_room_count = (
            action.spec.resolved_opening_room_count()
            if action is not None
            else DEFAULT_OPENING_ROOM_COUNT
        )
        monsters_per_combat_room = (
            action.spec.resolved_monsters_per_combat_room()
            if action is not None
            else DEFAULT_MONSTERS_PER_COMBAT_ROOM
        )

        logger.info(
            f"[GenerateDungeonRoomsSystem] 开始: dungeon={dungeon_name}, room_count={dungeon_room_count}, opening_room_count={opening_room_count}"
        )

        result = _RoomsResult()
        rooms_tool = _build_record_dungeon_rooms_tool(
            dungeon_room_count, opening_room_count
        )

        success = await agent_loop(
            name=entity.name,
            input_message=_build_dungeon_rooms_prompt(
                dungeon_name=dungeon_name,
                profile=dungeon_profile,
                dungeon_room_count=dungeon_room_count,
                opening_room_count=opening_room_count,
            ),
            # 直接传入实体的持久化 agent memory：agent_loop 原地追加
            messages=self._game.get_agent_memory(entity).messages,
            tools=[rooms_tool],
            handlers={
                rooms_tool.function.name: partial(
                    _handle_record_dungeon_rooms, result, monsters_per_combat_room
                ),
            },
            max_rounds=5,
        )

        if not success:
            logger.error("[GenerateDungeonRoomsSystem] agent_loop 失败，中止")
            return

        if result.dungeon_name is None or result.rooms is None:
            logger.error(
                "[GenerateDungeonRoomsSystem] LLM 已 stop 但未调用 record_dungeon_rooms，中止"
            )
            return

        rooms = result.rooms

        # 校验房间数量与类型顺序：总数必须匹配，第 1 个 opening，其余 combat
        if len(rooms) != dungeon_room_count:
            logger.error(
                f"[GenerateDungeonRoomsSystem] 房间数量不符：期望 {dungeon_room_count}，实际 {len(rooms)}，中止"
            )
            return
        # 前 opening_room_count 个必须是 opening，其余必须是 combat
        for i, room in enumerate(rooms, start=1):
            expected = "opening" if i <= opening_room_count else "combat"
            if room.room_type != expected:
                logger.error(
                    f"[GenerateDungeonRoomsSystem] 第 {i} 个房间 room_type 必须为 {expected!r}，实际为 {room.room_type!r}，中止"
                )
                return

        logger.info(
            f"[GenerateDungeonRoomsSystem] 完成:\n  rooms ({len(rooms)}): "
            + ", ".join(r.room_name for r in rooms)
        )

        draft.rooms = rooms
        logger.info(
            f"[GenerateDungeonRoomsSystem] 已写入 rooms: dungeon={dungeon_name}"
        )
