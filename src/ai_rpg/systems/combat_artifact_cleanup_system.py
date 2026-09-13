"""战斗结束神器清理系统。

战斗结果确定后，把本场战斗中参战怪物与副本场景实体所持有的神器实体标记为待销毁
（`DestroyComponent`），并由 `DestroyEntitySystem` 统一回收，避免上一场战斗的敌人/场景神器
在推进到后续关卡后继续产生影响。

同时从持有者的 `ReliquaryComponent` 中移除相应声明，保证 `ArtifactInitializationSystem`
不会在后续帧把已销毁的神器重新物化。
"""

from typing import Final, List, final

from loguru import logger
from overrides import override

from ..entitas import ExecuteProcessor, Matcher
from ..game.dbg_game import DBGGame
from ..models import (
    CombatResult,
    DestroyComponent,
    MonsterComponent,
    ReliquaryComponent,
)


#######################################################################################################################################
@final
class CombatArtifactCleanupSystem(ExecuteProcessor):
    """战斗结果确定后，清理参战怪物与副本场景所持有的神器实体（幂等）。"""

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    #######################################################################################################################################
    @override
    async def execute(self) -> None:
        combat = self._game.current_dungeon_combat_room.combat

        # 战斗结果尚未出现时不做任何事
        if combat.result == CombatResult.NONE:
            return

        stage_entity = self._game.get_stage_entity(
            self._game.current_dungeon_combat_room.stage.name
        )
        assert stage_entity is not None, "战斗场景实体不存在"

        # 收敛清理范围：本场参战怪物 + 副本场景本身
        monster_entities = self._game.get_actors_in_stage(
            stage_entity, Matcher(all_of=[MonsterComponent])
        )
        holder_entities = {stage_entity, *monster_entities}

        marked_names: List[str] = []
        for holder_entity in holder_entities:
            if not holder_entity.has(ReliquaryComponent):
                continue

            reliquary = holder_entity.get(ReliquaryComponent)
            for artifact in reliquary.artifacts:
                artifact_entity = self._game.get_entity_by_name(artifact.name)

                # 已销毁 / 从未物化的神器直接忽略
                if artifact_entity is None or artifact_entity.has(DestroyComponent):
                    continue

                # 标记待销毁（幂等）
                artifact_entity.add(DestroyComponent, artifact_entity.name)
                marked_names.append(artifact_entity.name)

            # 清空持有者的神器声明，保证 ArtifactInitializationSystem 不会重新物化已销毁的神器
            if reliquary.artifacts:
                holder_entity.replace(ReliquaryComponent, holder_entity.name, [])

        if marked_names:
            logger.debug(
                "CombatArtifactCleanupSystem: 标记待销毁神器实体: "
                + "、".join(marked_names)
            )
