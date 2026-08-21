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
from ..models.messages import ContextMessage
from ..models import (
    AssembleDungeonAction,
    GenerateDungeonActorsAction,
)
from ..models.dungeon_generation import DungeonRoomData
from .dungeon_generation import (
    ACTOR_TOOL,
    DungeonActorBlueprint,
    DungeonBlueprint,
    DungeonStageBlueprint,
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
        context: Sequence[ContextMessage],
    ) -> None:
        self._dungeon_name: str = dungeon_name
        self._profile: str = profile
        self._context: Sequence[ContextMessage] = context

    async def generate(
        self, room: DungeonRoomData, actor_idx: int
    ) -> Optional[DungeonActorBlueprint]:
        """为指定房间生成第 actor_idx 个怪物。成功返回蓝图，失败返回 None。"""
        result: List[Optional[DungeonActorBlueprint]] = [None]

        success = await agent_loop(
            name=f"{room.room_name}[{actor_idx + 1}]",
            prompt=_build_dungeon_actor_prompt(
                dungeon_name=self._dungeon_name,
                profile=self._profile,
                stage_name=room.room_name,
                stage_profile=room.profile,
                actor_index=actor_idx + 1,
                total_actors=room.actor_count,
            ),
            # 传入副本：并发隔离，且不把生成过程写入共享的 self._context
            context=list(self._context),
            tools=[ACTOR_TOOL],
            handlers={
                "record_dungeon_actor": partial(
                    _handle_record_dungeon_actor,
                    result,
                    room.room_name,
                    actor_idx,
                )
            },
            max_rounds=5,
        )

        if not success or result[0] is None:
            logger.error(
                f"[GenerateDungeonActorsSystem] Room '{room.room_name}' "
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

        # 创建怪物生成器（不变依赖在构造时绑定）
        generator = _SingleActorGenerator(
            dungeon_name=dungeon_name,
            profile=dungeon_profile,
            context=self._game.get_agent_context(entity).context,
        )

        # 展开 (room, actor_idx) 对，仅 combat 房间生成怪物
        client_tasks = [
            (room, actor_idx)
            for room in rooms
            if room.room_type == "combat"
            for actor_idx in range(room.actor_count)
        ]

        # 并发生成所有怪物
        actor_results = await asyncio.gather(
            *[generator.generate(room, actor_idx) for room, actor_idx in client_tasks]
        )

        # 按 room 归组并组装 DungeonBlueprint
        room_actors: Dict[str, List[DungeonActorBlueprint]] = defaultdict(list)
        for (room, _), actor_bp in zip(client_tasks, actor_results):
            if actor_bp is not None:
                room_actors[room.room_name].append(actor_bp)

        blueprint = DungeonBlueprint(
            dungeon_name=dungeon_name,
            profile=dungeon_profile,
        )

        for i, room in enumerate(rooms, start=1):
            actors = room_actors.get(room.room_name, [])

            # entry 房间无怪物，直接纳入 blueprint
            if room.room_type == "entry":
                room_bp = DungeonStageBlueprint(
                    room_type=room.room_type,
                    stage_name=room.room_name,
                    profile_name=room.profile_name,
                    profile=room.profile,
                    actors=[],
                )
                blueprint.stages.append(room_bp)
                logger.info(
                    f"[GenerateDungeonActorsSystem] Entry room {i}/{len(rooms)} 写入 blueprint:\n"
                    f"  room_name: {room_bp.stage_name}"
                )
                continue

            # combat 房间必须有怪物
            if not actors:
                logger.error(
                    f"[GenerateDungeonActorsSystem] combat room '{room.room_name}' 所有 actor 解析均失败，该房间不纳入 blueprint"
                )
                continue

            # 将 combat 房间及其怪物纳入 blueprint
            room_bp = DungeonStageBlueprint(
                room_type=room.room_type,
                stage_name=room.room_name,
                profile_name=room.profile_name,
                profile=room.profile,
                actors=actors,
            )
            blueprint.stages.append(room_bp)
            logger.info(
                f"[GenerateDungeonActorsSystem] Room+Actors {i}/{len(rooms)} 写入 blueprint:\n"
                f"  room_name: {room_bp.stage_name}\n"
                f"  actors ({len(actors)}): " + ", ".join(a.actor_name for a in actors)
            )

        if not blueprint.stages:
            logger.error(
                "[GenerateDungeonActorsSystem] 所有房间怪物解析均失败，blueprint.stages 为空，Step 3 中止"
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
