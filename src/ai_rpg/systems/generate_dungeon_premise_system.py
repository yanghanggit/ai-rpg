"""副本前提设定生成系统"""

from pathlib import Path
from typing import Dict, Final, List, Optional, final, override
from loguru import logger
from ..deepseek import agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.config import DUNGEON_PROCESS_DIR
from ..game.dbg_game import DBGGame
from ..models import (
    GenerateDungeonAction,
    GenerateDungeonStagesAction,
)
from .dungeon_generation import (
    DungeonPremiseData,
    PREMISE_TOOL,
    READ_PREMISE_FILE_TOOL,
)


####################################################################################################################################
def _build_dungeon_premise_prompt() -> str:
    """构建副本前提设定生成提示词。

    无需任何种子数据，完全由世界观框架驱动创作。
    世界观已通过调用方的 SystemMessage 提供给 LLM。
    """
    return """# 任务：创作一个副本的整体前提

请在当前世界观框架内，为本次副本生成名称与整体前提写照。


工作流程：调用 record_dungeon_premise 写入前提数据，确认无误后结束本次对话。
如需核查已写入内容，可先调用 read_premise_file，再决定是否结束。"""


####################################################################################################################################
@final
class GenerateDungeonPremiseSystem(ReactiveProcessor):
    """副本前提设定生成系统

    Note:
        - GenerateDungeonAction 由 home_actions.activate_generate_dungeon() 在家园状态下添加
    """

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
        logger.info(f"[GenerateDungeonPremiseSystem] Step 1 开始: entity={entity.name}")

        premise_file: Optional[DungeonPremiseData] = None

        def _handle_record_dungeon_premise(
            name: str, premise: str, stage_count: int
        ) -> str:
            nonlocal premise_file
            premise_file = DungeonPremiseData(
                dungeon_name=name,
                premise=premise,
                stage_count=stage_count,
            )
            file_path: Path = DUNGEON_PROCESS_DIR / f"{name}_premise.json"
            file_path.write_text(
                premise_file.model_dump_json(indent=4), encoding="utf-8"
            )
            logger.info(
                f"[GenerateDungeonPremiseSystem] record_dungeon_premise 执行:\n"
                f"  dungeon_name: {name}\n"
                f"  stage_count:  {stage_count}\n"
                f"  → {file_path}"
            )
            return (
                f"已记录副本「{name}」，共 {stage_count} 个战斗场景。"
                f"中间文件已写入: {file_path}"
            )

        def _handle_read_premise_file(dungeon_name: str) -> str:
            file_path: Path = DUNGEON_PROCESS_DIR / f"{dungeon_name}_premise.json"
            if not file_path.exists():
                return f"错误：文件不存在 {file_path}"
            return file_path.read_text(encoding="utf-8")

        success = await agent_loop(
            name=entity.name,
            prompt=_build_dungeon_premise_prompt(),
            context=self._game.get_agent_context(entity).context,
            tools=[PREMISE_TOOL, READ_PREMISE_FILE_TOOL],
            handlers={
                "record_dungeon_premise": _handle_record_dungeon_premise,
                "read_premise_file": _handle_read_premise_file,
            },
            max_rounds=5,
        )

        if not success:
            logger.error("[GenerateDungeonPremiseSystem] Step 1 agent_loop 失败，中止")
            return

        if premise_file is None:
            logger.error(
                "[GenerateDungeonPremiseSystem] Step 1 LLM 已 stop "
                "但未调用 record_dungeon_premise，中止"
            )
            return

        logger.info(
            f"[GenerateDungeonPremiseSystem] Step 1 完成:\n"
            f"  dungeon_name: {premise_file.dungeon_name}\n"
            f"  premise:      {premise_file.premise}"
        )
        entity.replace(
            GenerateDungeonStagesAction, entity.name, premise_file.dungeon_name
        )
        logger.info(
            f"[GenerateDungeonPremiseSystem] 添加 GenerateDungeonStagesAction: "
            f"dungeon={premise_file.dungeon_name}"
        )
