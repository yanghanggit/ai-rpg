"""副本房间生成系统"""

from functools import partial
from typing import Any, Dict, Final, List, Optional, final, override
from loguru import logger
from pydantic import BaseModel
from ..deepseek import agent_loop, ToolDefinition, ToolFunction
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..utils import prompt_builder
from ..models import (
    GenerateDungeonActorsAction,
    GenerateDungeonRoomsAction,
)
from ..models.dungeon_generation import DungeonRoomData


####################################################################################################################################
def _validate_room_code_names(rooms: List[DungeonRoomData]) -> Optional[str]:
    """校验房间 code_name：非空、合法 Python 标识符、全副本唯一。

    返回错误描述；全部合法时返回 None。
    """
    seen: set[str] = set()
    for room in rooms:
        code_name = room.code_name.strip()
        if not code_name:
            return f"房间 '{room.room_name}' 的 code_name 为空"
        if not code_name.isidentifier():
            return f"房间 '{room.room_name}' 的 code_name 不是合法标识符: '{room.code_name}'"
        if code_name in seen:
            return f"房间 '{room.room_name}' 的 code_name 重复: '{code_name}'"
        seen.add(code_name)
    return None


####################################################################################################################################
def _build_rooms_tool(dungeon_room_count: int) -> ToolDefinition:
    """动态构建 record_dungeon_rooms 工具定义。

    副本共 dungeon_room_count 个房间：首个为开场（opening），
    其余 dungeon_room_count - 1 个为战斗房间（combat）。
    """
    combat_room_count = dungeon_room_count - 1
    return ToolDefinition(
        function=ToolFunction(
            name="record_dungeon_rooms",
            description=(
                f"记录副本全部 {dungeon_room_count} 个房间：首个为开场（opening），"
                f"其余 {combat_room_count} 个为战斗房间（combat）。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "dungeon_name": {
                        "type": "string",
                        "description": "副本全名，与 Step 1 中的 dungeon_name 一致",
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
                                        "房间类型：'opening' = 开场房间（无战斗，纯场景氛围描写），"
                                        "'combat' = 战斗房间。第一个房间必须为 'opening'，其余必须为 'combat'"
                                    ),
                                },
                                "room_name": {
                                    "type": "string",
                                    "description": "房间全名，采用「房间.XXXX」命名格式，体现该局部区域的核心特征，所有房间名称不重复",
                                },
                                "code_name": {
                                    "type": "string",
                                    "description": "房间英文代号，采用 snake_case（如 shrine_entrance），仅小写字母/数字/下划线，全副本唯一，用于程序内部标识",
                                },
                                "profile": {
                                    "type": "string",
                                    "description": "该房间的感官环境描写，50-100字，只描述「这里有什么」，避免直接点出具体角色身份/阵营名称与威胁评价性词汇",
                                },
                                "actor_count": {
                                    "type": "integer",
                                    "enum": [0, 1, 2],
                                    "description": "角色种类数量。opening 房间填 0；combat 房间为 1，深处可为 2",
                                },
                            },
                            "required": [
                                "room_type",
                                "room_name",
                                "code_name",
                                "profile",
                                "actor_count",
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
    dungeon_name: str, profile: str, dungeon_room_count: int
) -> str:
    """构建副本房间生成的 LLM 提示词。"""

    combat_room_count = dungeon_room_count - 1
    return f"""# 任务：为副本创作 {dungeon_room_count} 个房间

## 副本信息

- **副本名称**：{dungeon_name}
- **整体设定**：{profile}

共计 {dungeon_room_count} 个房间，房间类型与顺序必须严格遵守：

- **第 1 个房间**：开场房间（room_type = "opening"），无战斗，actor_count = 0。
  描写副本门口的外部氛围——玩家站在副本门口的第一印象。
  不涉及任何怪物，纯粹的场景氛围铺垫。

- **第 2 ~ {dungeon_room_count} 个房间**：战斗房间（room_type = "combat"），共 {combat_room_count} 个，
  从入口区域逐步深入到副本最深处，actor_count = 1 或 2。

- **每个房间的 code_name**：一个可读的英文 snake_case 代号（仅小写字母/数字/下划线，如 shrine_entrance、shrine_courtyard），全副本内不重复，用于程序内部标识，禁止中文、空格、点号或连字符。

工作流程：调用 record_dungeon_rooms 写入全部房间数据，确认无误后结束本次对话。"""


####################################################################################################################################
class _RoomsResult(BaseModel):
    """record_dungeon_rooms handler 的结果容器。"""

    dungeon_name: Optional[str] = None
    rooms: Optional[List[DungeonRoomData]] = None


####################################################################################################################################
def _handle_record_dungeon_rooms(
    result: _RoomsResult, dungeon_name: str, rooms: List[Any]
) -> str:
    """处理 record_dungeon_rooms 工具调用。"""
    room_items = [DungeonRoomData(**r) for r in rooms]
    result.dungeon_name = dungeon_name
    result.rooms = room_items
    for i, room in enumerate(room_items, start=1):
        logger.info(
            f"[GenerateDungeonRoomsSystem] Room {i}/{len(room_items)}:\n"
            f"  room_type:    {room.room_type}\n"
            f"  room_name:    {room.room_name}\n"
            f"  code_name:    {room.code_name}\n"
            f"  actor_count:  {room.actor_count}\n"
            f"  profile:      {room.profile}"
        )
    logger.info(
        f"[GenerateDungeonRoomsSystem] record_dungeon_rooms 执行:\n"
        f"  dungeon_name: {dungeon_name}\n"
        f"  room_count:   {len(room_items)}"
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
        return {Matcher(GenerateDungeonRoomsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(GenerateDungeonRoomsAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        assert len(entities) == 1, "同时存在多个 GenerateDungeonRoomsAction，数据异常"
        entity = entities[0]
        await self._run(entity)

    ####################################################################################################################################
    async def _run(self, entity: Entity) -> None:
        action_comp = entity.get(GenerateDungeonRoomsAction)
        dungeon_name = action_comp.dungeon_name
        dungeon_profile = action_comp.dungeon_profile
        dungeon_room_count = action_comp.dungeon_room_count

        logger.info(
            f"[GenerateDungeonRoomsSystem] Step 2 开始: dungeon={dungeon_name}, "
            f"dungeon_room_count={dungeon_room_count}"
        )

        result = _RoomsResult()

        success = await agent_loop(
            name=entity.name,
            prompt=_build_dungeon_rooms_prompt(
                dungeon_name=dungeon_name,
                profile=dungeon_profile,
                dungeon_room_count=dungeon_room_count,
            ),
            # 直接传入实体的持久化 agent memory：agent_loop 原地追加
            messages=self._game.get_agent_memory(entity).messages,
            tools=[_build_rooms_tool(dungeon_room_count)],
            handlers={
                "record_dungeon_rooms": partial(_handle_record_dungeon_rooms, result),
            },
            max_rounds=5,
        )

        if not success:
            logger.error("[GenerateDungeonRoomsSystem] Step 2 agent_loop 失败，中止")
            return

        if result.dungeon_name is None or result.rooms is None:
            logger.error(
                "[GenerateDungeonRoomsSystem] Step 2 LLM 已 stop "
                "但未调用 record_dungeon_rooms，中止"
            )
            return

        rooms = result.rooms

        # 校验房间数量与类型顺序：总数必须匹配，第 1 个 opening，其余 combat
        if len(rooms) != dungeon_room_count:
            logger.error(
                f"[GenerateDungeonRoomsSystem] 房间数量不符：期望 {dungeon_room_count}，"
                f"实际 {len(rooms)}，中止"
            )
            return
        if rooms and rooms[0].room_type != "opening":
            logger.error(
                f"[GenerateDungeonRoomsSystem] 第一个房间 room_type 必须为 'opening'，"
                f"实际为 '{rooms[0].room_type}'，中止"
            )
            return
        for i, room in enumerate(rooms[1:], start=2):
            if room.room_type != "combat":
                logger.error(
                    f"[GenerateDungeonRoomsSystem] 第 {i} 个房间 room_type 必须为 'combat'，"
                    f"实际为 '{room.room_type}'，中止"
                )
                return

        # 校验 code_name：非空、合法标识符、全副本唯一
        code_name_error = _validate_room_code_names(rooms)
        if code_name_error is not None:
            logger.error(
                f"[GenerateDungeonRoomsSystem] code_name 校验失败: {code_name_error}，中止"
            )
            return

        logger.info(
            f"[GenerateDungeonRoomsSystem] Step 2 完成:\n"
            f"  rooms ({len(rooms)}): " + ", ".join(r.room_name for r in rooms)
        )

        # Step 3: 添加 GenerateDungeonActorsAction，携带房间列表产物
        entity.replace(
            GenerateDungeonActorsAction,
            entity.name,
            dungeon_name,
            dungeon_profile,
            rooms,
        )
        logger.info(
            f"[GenerateDungeonRoomsSystem] 添加 GenerateDungeonActorsAction: dungeon={dungeon_name}"
        )
