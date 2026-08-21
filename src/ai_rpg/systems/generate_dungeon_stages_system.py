"""副本场景生成系统"""

from functools import partial
from pathlib import Path
from typing import Any, Dict, Final, List, Optional, final, override
from loguru import logger
from ..deepseek import agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.config import DUNGEON_PROCESS_DIR
from ..game.dbg_game import DBGGame
from ..models import (
    GenerateDungeonActorsAction,
    GenerateDungeonStagesAction,
)
from .dungeon_generation import (
    DungeonStageData,
    DungeonStagesData,
    READ_STAGES_FILE_TOOL,
    build_stages_tool,
)


####################################################################################################################################
def _build_dungeon_stages_prompt(
    dungeon_name: str, profile: str, dungeon_room_count: int
) -> str:
    """构建副本场景生成的 LLM 提示词。"""

    total_stages = 1 + dungeon_room_count
    return f"""# 任务：为副本创作 {total_stages} 个场景

## 副本信息

- **副本名称**：{dungeon_name}
- **整体设定**：{profile}

共计 {total_stages} 个场景，房间类型与顺序必须严格遵守：

- **第 1 个场景**：叙事入口房间（room_type = "entry"），无战斗，actor_count = 0。
  描写副本入口处的外部氛围——玩家站在副本门口的第一印象。
  不涉及任何怪物，纯粹的场景氛围铺垫。
  
- **第 2 ~ {total_stages} 个场景**：战斗房间（room_type = "combat"），共 {dungeon_room_count} 个，
  从入口区域逐步深入到副本最深处，actor_count = 1 或 2。

工作流程：调用 record_dungeon_stages 写入全部场景数据，确认无误后结束本次对话。
如需核查已写入内容，可先调用 read_stages_file，再决定是否结束。"""


####################################################################################################################################
class _StagesResult:
    """record_dungeon_stages handler 的结果容器。"""

    def __init__(self, profile: str) -> None:
        self.profile = profile
        self.data: Optional[DungeonStagesData] = None


####################################################################################################################################
def _handle_record_dungeon_stages(
    result: _StagesResult, dungeon_name: str, stages: List[Any]
) -> str:
    """处理 record_dungeon_stages 工具调用。"""
    stage_items = [DungeonStageData(**s) for s in stages]
    result.data = DungeonStagesData(
        dungeon_name=dungeon_name,
        profile=result.profile,
        stages=stage_items,
    )
    file_path: Path = DUNGEON_PROCESS_DIR / f"{dungeon_name}_stages.json"
    file_path.write_text(result.data.model_dump_json(indent=4), encoding="utf-8")
    for i, stage in enumerate(stage_items, start=1):
        logger.info(
            f"[GenerateDungeonStagesSystem] Stage {i}/{len(stage_items)}:\n"
            f"  room_type:    {stage.room_type}\n"
            f"  stage_name:   {stage.stage_name}\n"
            f"  profile_name: {stage.profile_name}\n"
            f"  actor_count:  {stage.actor_count}\n"
            f"  profile:      {stage.profile}"
        )
    logger.info(
        f"[GenerateDungeonStagesSystem] record_dungeon_stages 执行:\n"
        f"  dungeon_name: {dungeon_name}\n"
        f"  stage_count:  {len(stage_items)}\n"
        f"  → {file_path}"
    )
    return (
        f"已记录副本「{dungeon_name}」的 {len(stage_items)} 个场景。"
        f"中间文件已写入: {file_path}"
    )


####################################################################################################################################
def _handle_read_stages_file(dungeon_name: str) -> str:
    """处理 read_stages_file 工具调用。"""
    file_path: Path = DUNGEON_PROCESS_DIR / f"{dungeon_name}_stages.json"
    if not file_path.exists():
        return f"错误：文件不存在 {file_path}"
    return file_path.read_text(encoding="utf-8")


####################################################################################################################################
@final
class GenerateDungeonStagesSystem(ReactiveProcessor):
    """副本场景生成系统"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(GenerateDungeonStagesAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(GenerateDungeonStagesAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        assert len(entities) == 1, "同时存在多个 GenerateDungeonStagesAction，数据异常"
        entity = entities[0]
        await self._run(entity)

    ####################################################################################################################################
    async def _run(self, entity: Entity) -> None:
        action_comp = entity.get(GenerateDungeonStagesAction)
        dungeon_name = action_comp.dungeon_name
        profile = action_comp.dungeon_profile
        dungeon_room_count = action_comp.dungeon_room_count

        logger.info(
            f"[GenerateDungeonStagesSystem] Step 2 开始: dungeon={dungeon_name}, "
            f"dungeon_room_count={dungeon_room_count}"
        )

        result = _StagesResult(profile=profile)

        success = await agent_loop(
            name=entity.name,
            prompt=_build_dungeon_stages_prompt(
                dungeon_name=dungeon_name,
                profile=profile,
                dungeon_room_count=dungeon_room_count,
            ),
            # 传入副本：保持与旧行为一致，不把生成过程写入实体的持久化上下文
            context=list(self._game.get_agent_context(entity).context),
            tools=[
                build_stages_tool(dungeon_room_count),
                READ_STAGES_FILE_TOOL,
            ],
            handlers={
                "record_dungeon_stages": partial(_handle_record_dungeon_stages, result),
                "read_stages_file": _handle_read_stages_file,
            },
            max_rounds=5,
        )

        if not success:
            logger.error("[GenerateDungeonStagesSystem] Step 2 agent_loop 失败，中止")
            return

        if result.data is None:
            logger.error(
                "[GenerateDungeonStagesSystem] Step 2 LLM 已 stop "
                "但未调用 record_dungeon_stages，中止"
            )
            return

        stages_file = result.data

        # 验证房间类型约束：第 1 个必须为 entry，其余必须为 combat
        if stages_file.stages:
            first = stages_file.stages[0]
            if first.room_type != "entry":
                logger.error(
                    f"[GenerateDungeonStagesSystem] 第一个场景 room_type 必须为 'entry'，"
                    f"实际为 '{first.room_type}'，中止"
                )
                return
            for i, stage in enumerate(stages_file.stages[1:], start=2):
                if stage.room_type != "combat":
                    logger.error(
                        f"[GenerateDungeonStagesSystem] 第 {i} 个场景 room_type 必须为 'combat'，"
                        f"实际为 '{stage.room_type}'，中止"
                    )
                    return

        logger.info(
            f"[GenerateDungeonStagesSystem] Step 2 完成:\n"
            f"  stages ({len(stages_file.stages)}): "
            + ", ".join(s.stage_name for s in stages_file.stages)
            + f"\n  → {DUNGEON_PROCESS_DIR / f'{dungeon_name}_stages.json'}"
        )

        # Step 3: 添加 GenerateDungeonActorsAction
        entity.replace(GenerateDungeonActorsAction, entity.name, dungeon_name)
        logger.info(
            f"[GenerateDungeonStagesSystem] 添加 GenerateDungeonActorsAction: dungeon={dungeon_name}"
        )
