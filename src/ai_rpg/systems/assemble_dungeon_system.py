"""副本组装系统"""

from pathlib import Path
from typing import Dict, Final, List, final, override, Optional, Set
from loguru import logger
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.config import DEBUG_CACHE_DIR
from ..game.dbg_game import DBGGame
from ..models import (
    ActorType,
    AssembleDungeonAction,
    AssembleDeckAction,
    CharacterStats,
    CombatRoom,
    Dungeon,
    DungeonRoom,
    OpeningRoom,
    StageType,
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

        # 组装 Dungeon 实体树（牌库由后置的 AssembleDeckSystem 负责填充）
        dungeon = self._build_dungeon(blueprint)
        if dungeon is None:
            return

        # 保存 DungeonBlueprint 副本到 DEBUG_CACHE_DIR（便于调试）
        debug_path: Path = DEBUG_CACHE_DIR / f"{dungeon_name}.blueprint.json"
        debug_path.write_text(blueprint.model_dump_json(indent=4), encoding="utf-8")
        logger.info(
            f"[AssembleDungeonSystem] DungeonBlueprint 已保存（调试）: {debug_path}"
        )

        # 衔接 Step 4.5：怪物牌库组建（随后由其写 Dungeon JSON / 发插图 / 重置 memory）
        entity.replace(AssembleDeckAction, entity.name, dungeon)
        logger.info(
            f"[AssembleDungeonSystem] 添加 AssembleDeckAction: dungeon={dungeon_name}"
        )

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
        seen_code_names: set[str] = set()
        rooms: List[DungeonRoom] = []

        # 组装每个 room 对应的房间
        for i, room_bp in enumerate(blueprint.rooms, start=1):

            # 处理 room_name 重复问题
            room_name = self._deduplicate_name(seen_room_names, room_bp.room_name)
            # 防御：code_name 同样去重，防止手搓蓝图绕过 Step 2 校验
            code_name = self._deduplicate_name(seen_code_names, room_bp.code_name)

            # 创建 Stage 实体
            stage = create_stage(
                name=room_name,
                code_name=code_name,
                stage_type=StageType.DUNGEON,
                profile=room_bp.profile,
                campaign_setting=self._game._world.blueprint.campaign_setting,
                system_rules=self._game._world.blueprint.system_rules,
            )

            # 根据 room_type 创建对应的房间类型
            if room_bp.room_type == "opening":
                stage.actors = []
                rooms.append(OpeningRoom(stage=stage))
                logger.info(
                    f"[AssembleDungeonSystem] Room {i}/{len(blueprint.rooms)} 构建完成:\n"
                    f"  type:   opening\n"
                    f"  stage:  {stage.name}"
                )
            elif room_bp.room_type == "combat":
                actors = []
                for actor_bp in room_bp.actors:
                    actor = create_actor(
                        name=self._deduplicate_name(
                            seen_actor_names, actor_bp.actor_name
                        ),
                        actor_type=ActorType.MONSTER,
                        profile=actor_bp.profile,
                        base_body=actor_bp.base_body,
                        character_stats=CharacterStats(),
                        campaign_setting=self._game._world.blueprint.campaign_setting,
                        system_rules=self._game._world.blueprint.system_rules,
                    )
                    # 牌库由 AssembleDeckSystem 后续从卡牌原型库组建并润色
                    actors.append(actor)
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
