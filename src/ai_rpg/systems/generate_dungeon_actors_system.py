"""地下城怪物生成系统"""

import asyncio
from collections import defaultdict
from pathlib import Path
from typing import Dict, Final, List, Optional, final, override
from loguru import logger
from ..deepseek import agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.config import DUNGEON_PROCESS_DIR
from ..game.tcg_game import TCGGame
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
    ecology: str,
    stage_name: str,
    stage_profile: str,
    actor_index: int = 1,
    total_actors: int = 1,
) -> str:
    multi_actor_note = (
        f"\n该场景共有 {total_actors} 种标居生物，当前为第 {actor_index} 个。\n"
        if total_actors > 1
        else ""
    )
    return f"""# 任务：为场景创作一个标居怪物的设定{multi_actor_note}

## 所在地下城

- **地下城名称**：{dungeon_name}
- **整体生态**：{ecology}

## 当前场景

- **场景名称**：{stage_name}
- **场景环境**：{stage_profile}

工作流程：调用 record_dungeon_actor 写入怪物数据，确认无误后结束本次对话。"""


####################################################################################################################################
@final
class GenerateDungeonActorsSystem(ReactiveProcessor):
    """地下城怪物生成系统"""

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

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
        stages_file_path: Path = (
            DUNGEON_PROCESS_DIR / f"{dungeon_name}_step2_stages.json"
        )
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

        if not stages_file.stages:
            logger.error(
                f"[GenerateDungeonActorsSystem] Step 2 文件中 stages 为空: {stages_file_path}"
            )
            return

        context = self._game.get_agent_context(entity).context

        # 展开 (stage, actor_index) 对，每对对应一个并发 agent_loop
        client_tasks = [
            (stage, actor_idx)
            for stage in stages_file.stages
            for actor_idx in range(stage.actor_count)
        ]
        actor_results: List[Optional[DungeonActorBlueprint]] = [None] * len(
            client_tasks
        )

        async def _run_single_actor(
            stage: DungeonStageData,
            actor_idx: int,
            result_idx: int,
        ) -> None:
            actor_bp: Optional[DungeonActorBlueprint] = None

            def _handle_record_dungeon_actor(
                actor_name: str,
                character_sheet_name: str,
                profile: str,
                base_body: str,
            ) -> str:
                nonlocal actor_bp
                actor_bp = DungeonActorBlueprint(
                    actor_name=actor_name,
                    character_sheet_name=character_sheet_name,
                    profile=profile,
                    base_body=base_body,
                )
                logger.info(
                    f"[GenerateDungeonActorsSystem] record_dungeon_actor 执行:\n"
                    f"  actor_name: {actor_name}\n"
                    f"  stage:      {stage.stage_name}[{actor_idx + 1}]"
                )
                return f"已记录怪物「{actor_name}」于场景「{stage.stage_name}」。"

            success = await agent_loop(
                name=f"{stage.stage_name}[{actor_idx + 1}]",
                prompt=_build_dungeon_actor_prompt(
                    dungeon_name=stages_file.dungeon_name,
                    ecology=stages_file.ecology,
                    stage_name=stage.stage_name,
                    stage_profile=stage.profile,
                    actor_index=actor_idx + 1,
                    total_actors=stage.actor_count,
                ),
                context=context,
                tools=[ACTOR_TOOL],
                handlers={"record_dungeon_actor": _handle_record_dungeon_actor},
                max_rounds=5,
            )

            if not success or actor_bp is None:
                logger.error(
                    f"[GenerateDungeonActorsSystem] Stage '{stage.stage_name}' "
                    f"actor[{actor_idx + 1}] 生成失败，该条跳过"
                )
                return

            actor_results[result_idx] = actor_bp

        await asyncio.gather(
            *[
                _run_single_actor(stage, actor_idx, i)
                for i, (stage, actor_idx) in enumerate(client_tasks)
            ]
        )

        # 按 stage 归组并组装 DungeonBlueprint
        stage_actors: dict[str, List[DungeonActorBlueprint]] = defaultdict(list)
        for (stage, _), actor_bp in zip(client_tasks, actor_results):
            if actor_bp is not None:
                stage_actors[stage.stage_name].append(actor_bp)

        blueprint = DungeonBlueprint(
            dungeon_name=stages_file.dungeon_name,
            ecology=stages_file.ecology,
        )

        for i, stage in enumerate(stages_file.stages, start=1):
            actors = stage_actors.get(stage.stage_name, [])
            if not actors:
                logger.error(
                    f"[GenerateDungeonActorsSystem] Stage '{stage.stage_name}' 所有 actor 解析均失败，该场景不纳入 blueprint"
                )
                continue

            stage_bp = DungeonStageBlueprint(
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
        file_path: Path = DUNGEON_PROCESS_DIR / f"{dungeon_name}_step3_blueprint.json"
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
