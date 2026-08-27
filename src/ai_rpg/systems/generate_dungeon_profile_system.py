"""副本设定生成系统"""

from functools import partial
from typing import Dict, Final, List, Optional, final, override
from ..deepseek import ToolDefinition, ToolFunction
from loguru import logger
from ..deepseek import agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..utils import prompt_builder
from ..models import (
    GenerateDungeonDirectiveAction,
    GenerateDungeonRoomsAction,
)
from pydantic import BaseModel


PROFILE_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="record_dungeon_profile",
        description="记录副本的名称、整体设定写照与房间总数。",
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "副本全名，采用「副本.XXXX」命名格式，体现其核心特征",
                },
                "profile": {
                    "type": "string",
                    "description": "该副本的整体设定写照，100-200字，聚焦感官与情境层面的直观细节，避免直接点出具体角色身份/阵营名称与威胁评价性词汇",
                },
                "dungeon_room_count": {
                    "type": "integer",
                    "enum": [3, 4],
                    "description": "副本房间总数（含 1 个入口房间），依规模与层次丰富程度选择",
                },
            },
            "required": ["name", "profile", "dungeon_room_count"],
        },
    )
)


####################################################################################################################################
class _ProfileResult(BaseModel):
    """record_dungeon_profile handler 的结果容器。"""

    dungeon_name: Optional[str] = None
    dungeon_profile: Optional[str] = None
    dungeon_room_count: Optional[int] = None


####################################################################################################################################
def _handle_record_dungeon_profile(
    result: _ProfileResult, name: str, profile: str, dungeon_room_count: int
) -> str:
    """处理 record_dungeon_profile 工具调用。"""
    result.dungeon_name = name
    result.dungeon_profile = profile
    result.dungeon_room_count = dungeon_room_count
    logger.info(
        f"[GenerateDungeonProfileSystem] record_dungeon_profile 执行:\n"
        f"  dungeon_name: {name}\n"
        f"  dungeon_room_count: {dungeon_room_count}"
    )
    return result.model_dump_json(ensure_ascii=False)


####################################################################################################################################
@prompt_builder
def _build_dungeon_profile_prompt(directive: str = "") -> str:
    """构建副本设定生成提示词。"""
    directive = directive.strip()
    directive_section = f"# 世界导演的创作指令\n\n{directive}\n\n" if directive else ""
    return f"""{directive_section}# 任务：创作一个副本的整体设定

请在当前世界观框架内，为本次副本生成名称与整体设定写照。

工作流程：调用 record_dungeon_profile 写入设定数据，确认无误后结束本次对话。"""


####################################################################################################################################
@final
class GenerateDungeonProfileSystem(ReactiveProcessor):
    """副本设定生成系统

    Note:
        - GenerateDungeonDirectiveAction 由 GenerateDungeonDirectiveSystem（Step 0）添加
    """

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(GenerateDungeonDirectiveAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(GenerateDungeonDirectiveAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        assert (
            len(entities) == 1
        ), "同时存在多个 GenerateDungeonDirectiveAction，数据异常"
        entity = entities[0]
        await self._run(entity)

    ####################################################################################################################################
    async def _run(self, entity: Entity) -> None:
        logger.info(f"[GenerateDungeonProfileSystem] Step 1 开始: entity={entity.name}")

        # 从 GenerateDungeonDirectiveAction 读取世界导演指令（可能为空）
        directive = entity.get(GenerateDungeonDirectiveAction).directive
        if directive.strip():
            logger.info(
                "[GenerateDungeonProfileSystem] 检测到世界导演指令，将注入首轮 prompt"
            )
        else:
            logger.info(
                "[GenerateDungeonProfileSystem] 未检测到世界导演指令，按纯世界观框架生成"
            )

        result = _ProfileResult()

        success = await agent_loop(
            name=entity.name,
            prompt=_build_dungeon_profile_prompt(directive),
            # 直接传入实体的持久化 agent memory：agent_loop 原地追加，
            # 本步完整对话即成为后续步骤的记忆
            messages=self._game.get_agent_memory(entity).messages,
            tools=[PROFILE_TOOL],
            handlers={
                "record_dungeon_profile": partial(
                    _handle_record_dungeon_profile, result
                ),
            },
            max_rounds=5,
        )

        if not success:
            logger.error("[GenerateDungeonProfileSystem] Step 1 agent_loop 失败，中止")
            return

        if (
            result.dungeon_name is None
            or result.dungeon_profile is None
            or result.dungeon_room_count is None
        ):
            logger.error(
                "[GenerateDungeonProfileSystem] Step 1 LLM 已 stop "
                "但未调用 record_dungeon_profile，中止"
            )
            return

        logger.info(
            f"[GenerateDungeonProfileSystem] Step 1 完成:\n"
            f"  dungeon_name: {result.dungeon_name}\n"
            f"  dungeon_profile: {result.dungeon_profile}"
        )
        entity.replace(
            GenerateDungeonRoomsAction,
            entity.name,
            result.dungeon_name,
            result.dungeon_profile,
            result.dungeon_room_count,
        )
        logger.info(
            f"[GenerateDungeonProfileSystem] 添加 GenerateDungeonRoomsAction: "
            f"dungeon={result.dungeon_name}, dungeon_room_count={result.dungeon_room_count}"
        )
