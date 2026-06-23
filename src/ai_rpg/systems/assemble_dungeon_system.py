"""地下城组装系统"""

from pathlib import Path
from typing import Dict, Final, List, final, override

from loguru import logger

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.config import DEBUG_CACHE_DIR, DUNGEON_PROCESS_DIR, DUNGEONS_DIR
from ..game.tcg_game import TCGGame
from ..models import (
    ActorType,
    AssembleDungeonAction,
    CharacterSheet,
    CharacterStats,
    CombatRoom,
    Dungeon,
    DungeonRoom,
    IllustrateDungeonAction,
    StageProfile,
    StageType,
)
from ..demo.entity_factory import create_actor, create_stage
from ..demo.global_settings import RPG_CAMPAIGN_SETTING
from ..demo.rpg_system_rules import RPG_SYSTEM_RULES
from .generate_dungeon_actors_system import (
    DungeonActorBlueprint,
    DungeonBlueprint,
)


####################################################################################################################################
@final
class AssembleDungeonSystem(ReactiveProcessor):
    """地下城组装系统"""

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

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

        logger.info(f"[AssembleDungeonSystem] Step 4 开始: dungeon={dungeon_name}")

        # 读取 Step 3 中间文件
        blueprint_file_path: Path = (
            DUNGEON_PROCESS_DIR / f"{dungeon_name}_step3_blueprint.json"
        )
        try:
            blueprint = DungeonBlueprint.model_validate_json(
                blueprint_file_path.read_text(encoding="utf-8")
            )
        except Exception as e:
            logger.error(
                f"[AssembleDungeonSystem] 读取 Step 3 文件失败: {e}\n"
                f"  path: {blueprint_file_path}"
            )
            return

        if not blueprint.stages:
            logger.error(
                f"[AssembleDungeonSystem] blueprint.stages 为空，无法构建 Dungeon: {blueprint_file_path}"
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
        debug_path: Path = DEBUG_CACHE_DIR / f"{dungeon_name}.json"
        debug_path.write_text(blueprint.model_dump_json(indent=4), encoding="utf-8")
        logger.info(
            f"[AssembleDungeonSystem] DungeonBlueprint 已保存（调试）: {debug_path}"
        )

        # 触发插图生成
        entity.replace(IllustrateDungeonAction, entity.name, dungeon_name)
        logger.info(
            f"[AssembleDungeonSystem] 添加 IllustrateDungeonAction: dungeon={dungeon_name}"
        )

    ####################################################################################################################################
    def _build_dungeon(self, blueprint: DungeonBlueprint) -> Dungeon | None:
        """将 DungeonBlueprint 组装为完整 Dungeon 实体树（纯数据，无 LLM 调用）。"""
        rooms: List[DungeonRoom] = []
        for i, stage_bp in enumerate(blueprint.stages, start=1):
            stage = create_stage(
                name=stage_bp.stage_name,
                stage_profile=StageProfile(
                    name=stage_bp.profile_name,
                    type=StageType.DUNGEON,
                    profile=stage_bp.profile,
                ),
                campaign_setting=RPG_CAMPAIGN_SETTING,
                system_rules=RPG_SYSTEM_RULES,
            )

            actor_bp: DungeonActorBlueprint = stage_bp.actor
            actor = create_actor(
                name=actor_bp.actor_name,
                character_sheet=CharacterSheet(
                    name=actor_bp.character_sheet_name,
                    type=ActorType.MONSTER.value,
                    profile=actor_bp.profile,
                    base_body=actor_bp.base_body,
                ),
                character_stats=CharacterStats(),
                campaign_setting=RPG_CAMPAIGN_SETTING,
                system_rules=RPG_SYSTEM_RULES,
                keywords=[
                    "纯攻击型：每张卡牌专注于对单个敌人造成直接伤害，不携带任何附加效果或持续状态。骰值 0-30 为失败，攻击乏力、伤害偏低；骰值 31-70 为正常，伤害稳定适中；骰值 71-100 为优质，体现爆发感，伤害显著高于角色基础攻击力。"
                ],
            )

            stage.actors = [actor]
            rooms.append(CombatRoom(stage=stage))
            logger.info(
                f"[AssembleDungeonSystem] Room {i}/{len(blueprint.stages)} 构建完成:\n"
                f"  stage: {stage.name}\n"
                f"  actor: {actor.name}"
            )

        dungeon = Dungeon(
            name=blueprint.dungeon_name,
            ecology=blueprint.ecology,
            rooms=rooms,
        )
        logger.info(
            f"[AssembleDungeonSystem] Step 4 完成: {dungeon.name} ({len(dungeon.rooms)} rooms)"
        )
        return dungeon
