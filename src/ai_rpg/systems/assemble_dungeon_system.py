"""副本组装系统"""

from pathlib import Path
from typing import Dict, Final, List, final, override, Optional, Set
from loguru import logger
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.config import DEBUG_CACHE_DIR, DUNGEONS_DIR
from ..game.dbg_game import DBGGame
from ..models import (
    ActorType,
    AssembleDungeonAction,
    CharacterStats,
    CombatRoom,
    Dungeon,
    DungeonRoom,
    EntryRoom,
    IllustrateDungeonAction,
    StageType,
    RPG_SYSTEM_RULES,
    SystemMessage,
)
from ..models.dungeon_generation import DungeonBlueprint
from ..models.entity_factory import create_actor, create_stage


####################################################################################################################################
@final
class AssembleDungeonSystem(ReactiveProcessor):
    """副本组装系统"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(AssembleDungeonAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(AssembleDungeonAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        assert len(entities) == 1, "同时存在多个 AssembleDungeonAction，数据异常"
        entity = entities[0]
        await self._run(entity)

    ####################################################################################################################################
    async def _run(self, entity: Entity) -> None:
        action_comp = entity.get(AssembleDungeonAction)
        dungeon_name = action_comp.dungeon_name
        blueprint = action_comp.blueprint

        logger.info(f"[AssembleDungeonSystem] Step 4 开始: dungeon={dungeon_name}")

        if not blueprint.rooms:
            logger.error(
                "[AssembleDungeonSystem] blueprint.rooms 为空，无法构建 Dungeon"
            )
            return

        # 组装 Dungeon 实体树
        dungeon = self._build_dungeon(blueprint)
        if dungeon is None:
            return

        # 写入最终 Dungeon JSON
        dungeon_path: Path = DUNGEONS_DIR / f"{dungeon.name}.json"
        dungeon_path.write_text(dungeon.model_dump_json(indent=4), encoding="utf-8")
        logger.info(
            f"[AssembleDungeonSystem] Dungeon 已保存: {dungeon_path}\n"
            f"  rooms ({len(dungeon.rooms)}): "
            + ", ".join(
                f"{room.stage.name}({room.stage.actors[0].name if room.stage.actors else 'no actor'})"
                for room in dungeon.rooms
            )
        )

        # 保存 DungeonBlueprint 副本到 DEBUG_CACHE_DIR（便于调试）
        debug_path: Path = DEBUG_CACHE_DIR / f"{dungeon_name}.blueprint.json"
        debug_path.write_text(blueprint.model_dump_json(indent=4), encoding="utf-8")
        logger.info(
            f"[AssembleDungeonSystem] DungeonBlueprint 已保存（调试）: {debug_path}"
        )

        # 触发插图生成
        entity.replace(IllustrateDungeonAction, entity.name, dungeon_name)
        logger.info(
            f"[AssembleDungeonSystem] 添加 IllustrateDungeonAction: dungeon={dungeon_name}"
        )

        # 副本生成完成：重置副本生成系统实体（WorldComponent + DungeonGenerationComponent）
        # 的 agent context，仅保留首条 system prompt，清除其余全部对话
        agent_context = self._game.get_agent_context(entity)
        del agent_context.context[1:]
        logger.info(
            f"[AssembleDungeonSystem] 已重置 agent context，保留 {len(agent_context.context)} 条消息"
        )
        assert isinstance(
            agent_context.context[0], SystemMessage
        ), "首条消息不是 SystemMessage"

    ####################################################################################################################################
    @staticmethod
    def _deduplicate_name(seen: Set[str], name: str) -> str:
        """若 name 已在 seen 中，追加 _2/_3/... 直到唯一；否则直接返回原名。"""
        if name not in seen:
            seen.add(name)
            return name
        counter = 2
        while f"{name}_{counter}" in seen:
            counter += 1
        unique = f"{name}_{counter}"
        seen.add(unique)
        logger.warning(
            f"[AssembleDungeonSystem] 名称重复，已重命名: '{name}' → '{unique}'"
        )
        return unique

    ####################################################################################################################################
    def _build_dungeon(self, blueprint: DungeonBlueprint) -> Optional[Dungeon]:
        """将 DungeonBlueprint 组装为完整 Dungeon 实体树（纯数据，无 LLM 调用）。"""
        seen_room_names: set[str] = set()
        seen_actor_names: set[str] = set()
        rooms: List[DungeonRoom] = []

        # 组装每个 room 对应的房间
        for i, room_bp in enumerate(blueprint.rooms, start=1):

            # 处理 room_name 重复问题
            room_name = self._deduplicate_name(seen_room_names, room_bp.room_name)

            # 创建 Stage 实体
            stage = create_stage(
                name=room_name,
                stage_type=StageType.DUNGEON,
                profile=room_bp.profile,
                campaign_setting=self._game._world.blueprint.campaign_setting,
                system_rules=RPG_SYSTEM_RULES,
            )

            # 根据 room_type 创建对应的房间类型
            if room_bp.room_type == "entry":
                stage.actors = []
                rooms.append(EntryRoom(stage=stage))
                logger.info(
                    f"[AssembleDungeonSystem] Room {i}/{len(blueprint.rooms)} 构建完成:\n"
                    f"  type:   entry\n"
                    f"  stage:  {stage.name}"
                )
            elif room_bp.room_type == "combat":
                actors = [
                    create_actor(
                        name=self._deduplicate_name(
                            seen_actor_names, actor_bp.actor_name
                        ),
                        actor_type=ActorType.MONSTER,
                        profile=actor_bp.profile,
                        base_body=actor_bp.base_body,
                        character_stats=CharacterStats(),
                        campaign_setting=self._game._world.blueprint.campaign_setting,
                        system_rules=RPG_SYSTEM_RULES,
                        keywords=[
                            "纯攻击型：每张卡牌专注于对单个敌人造成直接伤害，不携带任何附加效果或持续状态，伤害稳定适中。",
                        ],
                    )
                    for actor_bp in room_bp.actors
                ]
                stage.actors = actors
                rooms.append(CombatRoom(stage=stage))
                logger.info(
                    f"[AssembleDungeonSystem] Room {i}/{len(blueprint.rooms)} 构建完成:\n"
                    f"  type:   combat\n"
                    f"  stage:  {stage.name}\n"
                    f"  actors ({len(actors)}): " + ", ".join(a.name for a in actors)
                )

        # 组装 Dungeon 实体
        dungeon = Dungeon(
            name=blueprint.dungeon_name,
            profile=blueprint.profile,
            rooms=rooms,
        )
        logger.info(
            f"[AssembleDungeonSystem] Step 4 完成: {dungeon.name} ({len(dungeon.rooms)} rooms)"
        )
        return dungeon
