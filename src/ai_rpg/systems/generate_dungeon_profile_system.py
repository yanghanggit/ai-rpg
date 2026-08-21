"""副本设定生成系统"""

from functools import partial
from pathlib import Path
from typing import Dict, Final, List, Optional, final, override
from loguru import logger
from ..deepseek import agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.config import DUNGEON_PROCESS_DIR
from ..game.dbg_game import DBGGame
from ..models import (
    GenerateDungeonDirectiveAction,
    GenerateDungeonStagesAction,
)
from .dungeon_generation import (
    DungeonProfileData,
    PROFILE_TOOL,
    READ_PROFILE_FILE_TOOL,
)


####################################################################################################################################
class _ProfileResult:
    """record_dungeon_profile handler 的结果容器。"""

    def __init__(self) -> None:
        self.data: Optional[DungeonProfileData] = None


####################################################################################################################################
def _handle_record_dungeon_profile(
    result: _ProfileResult, name: str, profile: str, stage_count: int
) -> str:
    """处理 record_dungeon_profile 工具调用。"""
    result.data = DungeonProfileData(
        dungeon_name=name,
        profile=profile,
        stage_count=stage_count,
    )
    file_path: Path = DUNGEON_PROCESS_DIR / f"{name}_profile.json"
    file_path.write_text(result.data.model_dump_json(indent=4), encoding="utf-8")
    logger.info(
        f"[GenerateDungeonProfileSystem] record_dungeon_profile 执行:\n"
        f"  dungeon_name: {name}\n"
        f"  stage_count:  {stage_count}\n"
        f"  → {file_path}"
    )
    return (
        f"已记录副本「{name}」，共 {stage_count} 个战斗场景。"
        f"中间文件已写入: {file_path}"
    )


####################################################################################################################################
def _handle_read_profile_file(dungeon_name: str) -> str:
    """处理 read_profile_file 工具调用。"""
    file_path: Path = DUNGEON_PROCESS_DIR / f"{dungeon_name}_profile.json"
    if not file_path.exists():
        return f"错误：文件不存在 {file_path}"
    return file_path.read_text(encoding="utf-8")


####################################################################################################################################
def _build_dungeon_profile_prompt(directive: str = "") -> str:
    """构建副本设定生成提示词。

    无需任何种子数据，完全由世界观框架驱动创作。
    世界观已通过调用方的 SystemMessage 提供给 LLM。
    若世界导演已下达创作指令，则在首轮 prompt 中注入以引导创作方向。
    """
    directive = directive.strip()
    directive_section = f"# 世界导演的创作指令\n\n{directive}\n\n" if directive else ""
    return f"""{directive_section}# 任务：创作一个副本的整体设定

请在当前世界观框架内，为本次副本生成名称与整体设定写照。


工作流程：调用 record_dungeon_profile 写入设定数据，确认无误后结束本次对话。
如需核查已写入内容，可先调用 read_profile_file，再决定是否结束。"""


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
            context=self._game.get_agent_context(entity).context,
            tools=[PROFILE_TOOL, READ_PROFILE_FILE_TOOL],
            handlers={
                "record_dungeon_profile": partial(
                    _handle_record_dungeon_profile, result
                ),
                "read_profile_file": _handle_read_profile_file,
            },
            max_rounds=5,
        )

        if not success:
            logger.error("[GenerateDungeonProfileSystem] Step 1 agent_loop 失败，中止")
            return

        if result.data is None:
            logger.error(
                "[GenerateDungeonProfileSystem] Step 1 LLM 已 stop "
                "但未调用 record_dungeon_profile，中止"
            )
            return

        profile_file = result.data
        logger.info(
            f"[GenerateDungeonProfileSystem] Step 1 完成:\n"
            f"  dungeon_name: {profile_file.dungeon_name}\n"
            f"  profile:      {profile_file.profile}"
        )
        entity.replace(
            GenerateDungeonStagesAction, entity.name, profile_file.dungeon_name
        )
        logger.info(
            f"[GenerateDungeonProfileSystem] 添加 GenerateDungeonStagesAction: "
            f"dungeon={profile_file.dungeon_name}"
        )
