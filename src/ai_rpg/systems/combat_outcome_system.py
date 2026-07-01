"""战斗结果判定系统：检测阵营全灭条件，结束战斗并广播结果。"""

from typing import Final, final, override, Set
from ..entitas import ExecuteProcessor, Entity
from ..game.dbg_game import DBGGame
from ..models import (
    DeathComponent,
    CombatResult,
    PartyMemberComponent,
    MonsterComponent,
)
from loguru import logger


########################################################################################################################################################################
def _get_combat_result_notification(stage_name: str, is_victory: bool) -> str:
    """生成写入 agent 上下文的战斗胜/败通知文本。"""
    result_text = "胜利" if is_victory else "失败"
    return f"# {stage_name}的战斗{result_text}！"


########################################################################################################################################################################


@final
class CombatOutcomeSystem(ExecuteProcessor):
    """
    战斗结果判定系统。

    目标：在每次 pipeline 执行时检测阵营全灭条件，一旦达成即结束战斗
          并向全体远征队成员广播胜/败通知。

    Pipeline 位置：PlayCardsArbitrationSystem（后）→ 本系统 → CombatRoundCleanupSystem（前）

    依赖：DeathComponent 由上游系统写入，本系统只读不写角色状态。
    仅在战斗 ONGOING 阶段生效，否则静默跳过。
    """

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ########################################################################################################################################################################
    @override
    async def execute(self) -> None:
        """检测阵营全灭条件，调用 complete_combat() 结束战斗并广播结果；战斗未 ONGOING 时静默跳过。"""
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("当前不在战斗阶段，无需判定战斗胜负")
            return  # 不是本阶段就直接返回

        logger.debug("判定战斗胜负：检查双方阵营存活情况")

        if self._is_player_side_eliminated():
            logger.info("ally side eliminated!!!")
            self._game.current_dungeon.complete_combat(CombatResult.LOSE)
            self._game.clear_round_state()
            self._broadcast_result_to_party_members(CombatResult.LOSE)
        elif self._is_enemy_side_eliminated():
            logger.info("enemy side eliminated!!!")
            self._game.current_dungeon.complete_combat(CombatResult.WIN)
            self._game.clear_round_state()
            self._broadcast_result_to_party_members(CombatResult.WIN)
        else:
            logger.debug("双方均未全灭，战斗继续进行")

    ########################################################################################################################################################################
    def _is_enemy_side_eliminated(self) -> bool:
        """返回敌方阵营（MonsterComponent）是否已全员带有 DeathComponent。"""
        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        actors_in_stage = self._game.get_actors_in_stage(player_entity)
        assert len(actors_in_stage) > 0, f"entities with actions: {actors_in_stage}"

        active_enemies: Set[Entity] = set()
        defeated_enemies: Set[Entity] = set()

        for entity in actors_in_stage:

            if not entity.has(MonsterComponent):
                continue

            # 激活的敌人
            active_enemies.add(entity)

            if entity.has(DeathComponent):
                # 已被击败的敌人
                defeated_enemies.add(entity)

        # 判断是否所有敌人都已被击败
        return len(active_enemies) > 0 and len(defeated_enemies) >= len(active_enemies)

    ########################################################################################################################################################################
    def _is_player_side_eliminated(self) -> bool:
        """返回友方阵营（PartyMemberComponent）是否已全员带有 DeathComponent。"""

        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "Player entity should not be None."

        actors_in_stage = self._game.get_actors_in_stage(player_entity)
        assert len(actors_in_stage) > 0, f"entities with actions: {actors_in_stage}"

        current_allies: Set[Entity] = set()
        defeated_allies: Set[Entity] = set()

        for entity in actors_in_stage:

            if not entity.has(PartyMemberComponent):
                continue

            # 当前存活的友方单位
            current_allies.add(entity)

            if entity.has(DeathComponent):
                # 已被击败的友方单位
                defeated_allies.add(entity)

        # 判断是否所有友方单位都已被击败
        return len(current_allies) > 0 and len(defeated_allies) >= len(current_allies)

    ########################################################################################################################################################################
    def _broadcast_result_to_party_members(self, result: CombatResult) -> None:
        """向当前场景内所有 PartyMemberComponent 实体写入胜/败通知，并附带 combat_outcome 参数。"""

        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "Player entity should not be None."

        combat_stage_entity = self._game.resolve_stage_entity(player_entity)
        assert (
            combat_stage_entity is not None
        ), "Player's stage entity should not be None."

        actors_in_stage = self._game.get_actors_in_stage(player_entity)
        assert len(actors_in_stage) > 0, f"entities with actions: {actors_in_stage}"

        for entity in actors_in_stage:

            # 仅向远征队成员广播结果消息，非远征队成员（如敌人）不发送
            if not entity.has(PartyMemberComponent):
                continue

            # 根据战斗结果发送不同的消息内容，附带当前战斗场景名称作为 combat_outcome 参数
            if result == CombatResult.WIN:
                self._game.add_human_message(
                    entity,
                    _get_combat_result_notification(combat_stage_entity.name, True),
                    combat_outcome=combat_stage_entity.name,
                )
            elif result == CombatResult.LOSE:
                self._game.add_human_message(
                    entity,
                    _get_combat_result_notification(combat_stage_entity.name, False),
                    combat_outcome=combat_stage_entity.name,
                )

    ########################################################################################################################################################################
