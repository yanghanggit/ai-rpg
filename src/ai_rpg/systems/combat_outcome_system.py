from typing import Final, List, final, override, Set
from ..entitas import ExecuteProcessor, Entity
from ..game.tcg_game import TCGGame
from ..models import (
    DeathComponent,
    CombatResult,
    ExpeditionMemberComponent,
    EnemyComponent,
)
from loguru import logger


########################################################################################################################################################################
def _get_combat_result_notification(stage_name: str, is_victory: bool) -> str:
    """获取战斗结果通知消息。

    Args:
        stage_name: 战斗场景名称
        is_victory: True表示胜利，False表示失败

    Returns:
        战斗结果通知字符串，包含场景名称和胜负结果
    """
    result_text = "胜利" if is_victory else "失败"
    return f"# {stage_name}的战斗{result_text}！"


########################################################################################################################################################################


@final
class CombatOutcomeSystem(ExecuteProcessor):
    """战斗结果判定系统。

    负责监测战斗中的生命值变化，判定角色死亡状态，
    检查双方阵营的全灭情况，并在战斗结束时广播胜负结果。

    主要职责:
    - 检测并标记生命值归零的实体为死亡状态
    - 判断敌方或友方是否全员阵亡
    - 确定战斗胜负并通知所有友方单位
    """

    def __init__(self, game: TCGGame) -> None:
        self._game: Final[TCGGame] = game

    ########################################################################################################################################################################
    @override
    async def execute(self) -> None:

        # step1: 判定战斗胜负
        self._determine_combat_winner()

    ########################################################################################################################################################################
    def _determine_combat_winner(self) -> None:
        """根据双方阵营的存活情况判定战斗胜负。

        仅在战斗进行中时执行判定。检查顺序:
        1. 若友方全灭，标记战斗失败并广播失败消息
        2. 若敌方全灭，标记战斗胜利并广播胜利消息
        3. 若双方均有存活单位，战斗继续

        战斗结果会通过current_dungeon记录，
        并向所有友方单位广播相应的胜负消息。
        """
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("当前不在战斗阶段，无需判定战斗胜负")
            return  # 不是本阶段就直接返回

        logger.debug("判定战斗胜负：检查双方阵营存活情况")

        if self._is_ally_side_eliminated():
            logger.info("ally side eliminated!!!")
            self._flush_incomplete_round()
            self._game.current_dungeon.complete_combat(CombatResult.LOSE)
            self._broadcast_result_to_allies(CombatResult.LOSE)
        elif self._is_enemy_side_eliminated():
            logger.info("enemy side eliminated!!!")
            self._flush_incomplete_round()
            self._game.current_dungeon.complete_combat(CombatResult.WIN)
            self._broadcast_result_to_allies(CombatResult.WIN)
        else:
            logger.debug("双方均未全灭，战斗继续进行")

    ########################################################################################################################################################################
    def _flush_incomplete_round(self) -> None:
        """将最新回合中未完成出手的角色补全为空占位。

        当战斗在回合中途结束（如一击必杀）时，latest_round 的 completed_actors
        可能尚未包含全部 action_order 成员，导致 is_round_completed 为 False。
        本方法将剩余角色依序追加至 completed_actors，并在 combat_log / narrative
        中各追加一个空字符串占位，使三个列表长度保持一致。
        """
        latest_round = self._game.current_dungeon.latest_round
        if latest_round is None or latest_round.is_round_completed:
            return

        remaining: List[str] = latest_round.action_order[
            len(latest_round.completed_actors) :
        ]
        for actor in remaining:
            latest_round.completed_actors.append(actor)
            latest_round.combat_log.append("")
            latest_round.narrative.append("")

    ########################################################################################################################################################################
    def _is_enemy_side_eliminated(self) -> bool:
        """检查敌方阵营是否已全员阵亡。

        遍历当前场景中的所有角色，统计敌方单位(带EnemyComponent)的总数
        和已阵亡敌方单位(带DeathComponent)的数量。

        Returns:
            bool: 当存在敌方单位且所有敌方单位都已阵亡时返回True，否则返回False
        """
        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        actors_in_stage = self._game.get_actors_in_stage(player_entity)
        assert len(actors_in_stage) > 0, f"entities with actions: {actors_in_stage}"

        active_enemies: Set[Entity] = set()
        defeated_enemies: Set[Entity] = set()

        for entity in actors_in_stage:

            if not entity.has(EnemyComponent):
                continue

            # 激活的敌人
            active_enemies.add(entity)

            if entity.has(DeathComponent):
                # 已被击败的敌人
                defeated_enemies.add(entity)

        # 判断是否所有敌人都已被击败
        return len(active_enemies) > 0 and len(defeated_enemies) >= len(active_enemies)

    ########################################################################################################################################################################
    def _is_ally_side_eliminated(self) -> bool:
        """检查友方阵营是否已全员阵亡。

        遍历当前场景中的所有角色，统计远征队成员(带ExpeditionMemberComponent)的总数
        和已阵亡远征队成员(带DeathComponent)的数量。

        Returns:
            bool: 当存在远征队成员且所有远征队成员都已阵亡时返回True，否则返回False
        """

        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "Player entity should not be None."

        actors_in_stage = self._game.get_actors_in_stage(player_entity)
        assert len(actors_in_stage) > 0, f"entities with actions: {actors_in_stage}"

        current_allies: Set[Entity] = set()
        defeated_allies: Set[Entity] = set()

        for entity in actors_in_stage:

            if not entity.has(ExpeditionMemberComponent):
                continue

            # 当前存活的友方单位
            current_allies.add(entity)

            if entity.has(DeathComponent):
                # 已被击败的友方单位
                defeated_allies.add(entity)

        # 判断是否所有友方单位都已被击败
        return len(current_allies) > 0 and len(defeated_allies) >= len(current_allies)

    ########################################################################################################################################################################
    def _broadcast_result_to_allies(self, result: CombatResult) -> None:
        """向当前场景中的所有远征队成员广播战斗结果消息。

        遍历场景中的所有角色，向每个远征队成员(带ExpeditionMemberComponent)发送:
        - 胜利消息: 当result为CombatResult.WIN时
        - 失败消息: 当result为CombatResult.LOSE时

        消息中会附带当前战斗场景的名称作为combat_outcome参数。

        Args:
            result: 战斗结果枚举值，指示胜利或失败
        """

        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "Player entity should not be None."

        combat_stage_entity = self._game.resolve_stage_entity(player_entity)
        assert (
            combat_stage_entity is not None
        ), "Player's stage entity should not be None."

        actors_in_stage = self._game.get_actors_in_stage(player_entity)
        assert len(actors_in_stage) > 0, f"entities with actions: {actors_in_stage}"

        for entity in actors_in_stage:
            if not entity.has(ExpeditionMemberComponent):
                continue

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
