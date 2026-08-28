"""战斗结果判定系统：检测阵营全灭条件，结束战斗并广播结果。"""

from typing import Final, final, override, Set, Type
from ..entitas import Component, ExecuteProcessor, Entity
from ..game.dbg_game import DBGGame
from ..utils import prompt_builder
from ..models import (
    DeathComponent,
    CombatResult,
    HumanMessage,
    PartyMemberComponent,
    MonsterComponent,
    DrawPileComponent,
    DiscardPileComponent,
    HandComponent,
)
from loguru import logger
from ..game.dbg_combat_processor import clear_round_state


########################################################################################################################################################################
@prompt_builder
def _build_combat_result_notification(stage_name: str, is_victory: bool) -> str:
    """生成写入 agent 记忆的战斗胜/败通知文本。"""
    result_text = "胜利" if is_victory else "失败"
    return f"# {stage_name}的战斗{result_text}！"


########################################################################################################################################################################


@final
class CombatOutcomeSystem(ExecuteProcessor):
    """
    战斗结果判定系统。
    """

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ########################################################################################################################################################################
    @override
    async def execute(self) -> None:
        """检测阵营全灭条件，调用 complete_combat() 结束战斗并广播结果；战斗未 ONGOING 时静默跳过。"""
        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("当前不在战斗阶段，无需判定战斗胜负")
            return  # 不是本阶段就直接返回

        logger.debug("判定战斗胜负：检查双方阵营存活情况")

        if self._is_player_side_eliminated():

            # 如果玩家阵营全灭，则判定为战斗失败
            logger.info("ally side eliminated!!!")
            self._game.current_dungeon_combat_room.combat.complete_combat(
                CombatResult.LOSE
            )
            clear_round_state(self._game)
            self._broadcast_result_to_party_members(CombatResult.LOSE)

        elif self._is_enemy_side_eliminated():

            # 如果敌方阵营全灭，则判定为战斗胜利
            logger.info("enemy side eliminated!!!")
            self._game.current_dungeon_combat_room.combat.complete_combat(
                CombatResult.WIN
            )
            clear_round_state(self._game)
            self._broadcast_result_to_party_members(CombatResult.WIN)

        elif self._is_both_sides_cardless():

            # 双方均无可用卡牌（DrawPile / Hand / DiscardPile 均为空）时，判定敌人获胜
            logger.info("both sides out of cards!!! enemy wins")
            self._game.current_dungeon_combat_room.combat.complete_combat(
                CombatResult.LOSE
            )
            clear_round_state(self._game)
            self._broadcast_result_to_party_members(CombatResult.LOSE)

        else:
            logger.debug("双方均未全灭，战斗继续进行")

    ########################################################################################################################################################################
    def _get_actors_in_stage(self) -> Set[Entity]:
        """返回当前场景内所有参战角色实体（含已死亡角色）。"""
        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "Player entity should not be None."

        actors_in_stage = self._game.get_actors_in_stage(player_entity)
        assert len(actors_in_stage) > 0, f"entities with actions: {actors_in_stage}"
        return actors_in_stage

    ########################################################################################################################################################################
    def _is_side_eliminated(self, component_cls: Type[Component]) -> bool:
        """返回指定阵营（由 component_cls 标记）是否已全员带有 DeathComponent。"""
        actors_in_stage = self._get_actors_in_stage()

        members: Set[Entity] = set()
        defeated_members: Set[Entity] = set()

        for entity in actors_in_stage:

            if not entity.has(component_cls):
                continue

            members.add(entity)

            if entity.has(DeathComponent):
                defeated_members.add(entity)

        # 判断该阵营是否所有成员都已被击败（无成员时返回 False）
        return len(members) > 0 and len(defeated_members) >= len(members)

    ########################################################################################################################################################################
    def _is_player_side_eliminated(self) -> bool:
        """返回友方阵营（PartyMemberComponent）是否已全员带有 DeathComponent。"""
        return self._is_side_eliminated(PartyMemberComponent)

    ########################################################################################################################################################################
    def _is_enemy_side_eliminated(self) -> bool:
        """返回敌方阵营（MonsterComponent）是否已全员带有 DeathComponent。"""
        return self._is_side_eliminated(MonsterComponent)

    ########################################################################################################################################################################
    def _is_side_cardless(self, members: Set[Entity]) -> bool:
        """返回指定成员集合是否均无可用卡牌（DrawPile / Hand / DiscardPile 均为空）。"""
        if not members:
            return False
        return all(self._count_available_cards(entity) == 0 for entity in members)

    ########################################################################################################################################################################
    def _is_both_sides_cardless(self) -> bool:
        """返回双方阵营存活成员是否均无可用卡牌（平局破局条件）。"""
        actors_in_stage = self._get_actors_in_stage()

        alive_allies: Set[Entity] = set()
        alive_enemies: Set[Entity] = set()

        for entity in actors_in_stage:

            if entity.has(DeathComponent):
                continue

            if entity.has(PartyMemberComponent):
                alive_allies.add(entity)
            elif entity.has(MonsterComponent):
                alive_enemies.add(entity)

        return self._is_side_cardless(alive_allies) and self._is_side_cardless(
            alive_enemies
        )

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
                    HumanMessage(
                        content=_build_combat_result_notification(
                            combat_stage_entity.name, True
                        ),
                        combat_outcome=combat_stage_entity.name,
                    ),
                )
            elif result == CombatResult.LOSE:
                self._game.add_human_message(
                    entity,
                    HumanMessage(
                        content=_build_combat_result_notification(
                            combat_stage_entity.name, False
                        ),
                        combat_outcome=combat_stage_entity.name,
                    ),
                )

    ########################################################################################################################################################################
    def _count_available_cards(self, entity: Entity) -> int:
        """统计实体 DrawPile + Hand + DiscardPile 三堆卡牌总数（不含 ExhaustPile）。"""
        total = 0
        if entity.has(DrawPileComponent):
            draw_pile = entity.get(DrawPileComponent)
            total += len(draw_pile.cards) + len(draw_pile.retained_cards)
        if entity.has(HandComponent):
            total += len(entity.get(HandComponent).cards)
        if entity.has(DiscardPileComponent):
            total += len(entity.get(DiscardPileComponent).cards)
        return total

    ########################################################################################################################################################################
