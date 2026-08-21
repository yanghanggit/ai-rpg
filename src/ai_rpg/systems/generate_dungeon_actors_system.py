"""副本怪物生成系统"""

import asyncio
from collections import defaultdict
from functools import partial
from pathlib import Path
from typing import Dict, Final, List, Optional, Sequence, final, override
from loguru import logger
from ..deepseek import agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.config import DUNGEON_PROCESS_DIR
from ..game.dbg_game import DBGGame
from ..models.messages import BaseMessage
from ..models import (
    AssembleDungeonAction,
    GenerateDungeonActorsAction,
)
from .dungeon_generation import (
    ACTOR_TOOL,
    DungeonActorBlueprint,
    DungeonBlueprint,
    DungeonStageBlueprint,
    DungeonStageData,
    DungeonStagesData,
)


####################################################################################################################################
def _build_dungeon_actor_prompt(
    dungeon_name: str,
    profile: str,
    stage_name: str,
    stage_profile: str,
    actor_index: int = 1,
    total_actors: int = 1,
) -> str:
    """构建副本怪物生成的 LLM 提示词。"""

    multi_actor_note = (
        f"\n该场景共有 {total_actors} 个怪物，当前为第 {actor_index} 个。\n"
        if total_actors > 1
        else ""
    )
    return f"""# 任务：为场景创作一个怪物的设定{multi_actor_note}

## 所在副本

- **副本名称**：{dungeon_name}
- **整体设定**：{profile}

## 当前场景

- **场景名称**：{stage_name}
- **场景环境**：{stage_profile}

工作流程：调用 record_dungeon_actor 写入怪物数据，确认无误后结束本次对话。"""


####################################################################################################################################
def _handle_record_dungeon_actor(
    result: List[Optional[DungeonActorBlueprint]],
    stage_name: str,
    actor_idx: int,
    actor_name: str,
    character_sheet_name: str,
    profile: str,
    base_body: str,
) -> str:
    """处理 record_dungeon_actor 工具调用。result[0] 作为返回值容器。"""
    result[0] = DungeonActorBlueprint(
        actor_name=actor_name,
        character_sheet_name=character_sheet_name,
        profile=profile,
        base_body=base_body,
    )
    logger.info(
        f"[GenerateDungeonActorsSystem] record_dungeon_actor 执行:\n"
        f"  actor_name: {actor_name}\n"
        f"  stage:      {stage_name}[{actor_idx + 1}]"
    )
    return f"已记录怪物「{actor_name}」于场景「{stage_name}」。"


####################################################################################################################################
@final
class _SingleActorGenerator:
    """单个怪物的 LLM 生成器。"""

    def __init__(
        self,
        dungeon_name: str,
        profile: str,
        context: Sequence[BaseMessage],
    ) -> None:
        self._dungeon_name: str = dungeon_name
        self._profile: str = profile
        self._context: Sequence[BaseMessage] = context

    async def generate(
        self, stage: DungeonStageData, actor_idx: int
    ) -> Optional[DungeonActorBlueprint]:
        """为指定场景生成第 actor_idx 个怪物。成功返回蓝图，失败返回 None。"""
        result: List[Optional[DungeonActorBlueprint]] = [None]

        success = await agent_loop(
            name=f"{stage.stage_name}[{actor_idx + 1}]",
            prompt=_build_dungeon_actor_prompt(
                dungeon_name=self._dungeon_name,
                profile=self._profile,
                stage_name=stage.stage_name,
                stage_profile=stage.profile,
                actor_index=actor_idx + 1,
                total_actors=stage.actor_count,
            ),
            context=self._context,
            tools=[ACTOR_TOOL],
            handlers={
                "record_dungeon_actor": partial(
                    _handle_record_dungeon_actor,
                    result,
                    stage.stage_name,
                    actor_idx,
                )
            },
            max_rounds=5,
        )

        if not success or result[0] is None:
            logger.error(
                f"[GenerateDungeonActorsSystem] Stage '{stage.stage_name}' "
                f"actor[{actor_idx + 1}] 生成失败，该条跳过"
            )
            return None

        return result[0]


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

        logger.info(
            f"[GenerateDungeonActorsSystem] Step 3 开始: dungeon={dungeon_name}"
        )

        # 读取 Step 2 中间文件
        stages_file_path: Path = DUNGEON_PROCESS_DIR / f"{dungeon_name}_stages.json"
        try:
            stages_file = DungeonStagesData.model_validate_json(
                stages_file_path.read_text(encoding="utf-8")
            )
        except Exception as e:
            logger.error(
                f"[GenerateDungeonActorsSystem] 读取 Step 2 文件失败: {e}\n"
                f"  path: {stages_file_path}"
            )
            return

        # Step 2 中间文件中 stages 为空，无法生成怪物
        if not stages_file.stages:
            logger.error(
                f"[GenerateDungeonActorsSystem] Step 2 文件中 stages 为空: {stages_file_path}"
            )
            return

        # 创建怪物生成器（不变依赖在构造时绑定）
        generator = _SingleActorGenerator(
            dungeon_name=stages_file.dungeon_name,
            profile=stages_file.profile,
            context=self._game.get_agent_context(entity).context,
        )

        # 展开 (stage, actor_idx) 对，仅 combat 房间生成怪物
        client_tasks = [
            (stage, actor_idx)
            for stage in stages_file.stages
            if stage.room_type == "combat"
            for actor_idx in range(stage.actor_count)
        ]

        # 并发生成所有怪物
        actor_results = await asyncio.gather(
            *[generator.generate(stage, actor_idx) for stage, actor_idx in client_tasks]
        )

        # 按 stage 归组并组装 DungeonBlueprint
        stage_actors: Dict[str, List[DungeonActorBlueprint]] = defaultdict(list)
        for (stage, _), actor_bp in zip(client_tasks, actor_results):
            if actor_bp is not None:
                stage_actors[stage.stage_name].append(actor_bp)

        # Step 3 中间文件中 stages 全部为 entry 房间，无法生成怪物
        blueprint = DungeonBlueprint(
            dungeon_name=stages_file.dungeon_name,
            profile=stages_file.profile,
        )

        # Step 2 中间文件中 stages 全部为 entry 房间，无法生成怪物
        for i, stage in enumerate(stages_file.stages, start=1):
            actors = stage_actors.get(stage.stage_name, [])

            # entry 房间无怪物，直接纳入 blueprint
            if stage.room_type == "entry":
                stage_bp = DungeonStageBlueprint(
                    room_type=stage.room_type,
                    stage_name=stage.stage_name,
                    profile_name=stage.profile_name,
                    profile=stage.profile,
                    actors=[],
                )
                blueprint.stages.append(stage_bp)
                logger.info(
                    f"[GenerateDungeonActorsSystem] Entry stage {i}/{len(stages_file.stages)} 写入 blueprint:\n"
                    f"  stage_name: {stage_bp.stage_name}"
                )
                continue

            # combat 房间必须有怪物
            if not actors:
                logger.error(
                    f"[GenerateDungeonActorsSystem] combat stage '{stage.stage_name}' 所有 actor 解析均失败，该场景不纳入 blueprint"
                )
                continue

            # 将 combat 房间及其怪物纳入 blueprint
            stage_bp = DungeonStageBlueprint(
                room_type=stage.room_type,
                stage_name=stage.stage_name,
                profile_name=stage.profile_name,
                profile=stage.profile,
                actors=actors,
            )
            blueprint.stages.append(stage_bp)
            logger.info(
                f"[GenerateDungeonActorsSystem] Stage+Actors {i}/{len(stages_file.stages)} 写入 blueprint:\n"
                f"  stage_name: {stage_bp.stage_name}\n"
                f"  actors ({len(actors)}): " + ", ".join(a.actor_name for a in actors)
            )

        if not blueprint.stages:
            logger.error(
                "[GenerateDungeonActorsSystem] 所有场景怪物解析均失败，blueprint.stages 为空，Step 3 中止"
            )
            return

        # 写入 Step 3 中间文件
        file_path: Path = DUNGEON_PROCESS_DIR / f"{dungeon_name}_blueprint.json"
        file_path.write_text(blueprint.model_dump_json(indent=4), encoding="utf-8")

        logger.info(
            f"[GenerateDungeonActorsSystem] Step 3 完成:\n"
            f"  dungeon_name: {blueprint.dungeon_name}\n"
            f"  stages ({len(blueprint.stages)}): "
            + ", ".join(
                f"{s.stage_name}({len(s.actors)} actors)" for s in blueprint.stages
            )
            + f"\n  → {file_path}"
        )

        entity.replace(AssembleDungeonAction, entity.name, dungeon_name)
        logger.info(
            f"[GenerateDungeonActorsSystem] 添加 AssembleDungeonAction: dungeon={dungeon_name}"
        )
