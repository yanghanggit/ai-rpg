"""出牌动作系统模块。

处理战斗中角色的出牌动作，当角色使用卡牌时，向该角色的对话上下文中
添加出牌通知消息，包含卡牌名称、目标和完整的卡牌数据。
仅在战斗进行中(ongoing)阶段执行。
"""

from typing import final
from overrides import override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    HandComponent,
    PlayCardsAction,
)
from ..game.tcg_game import TCGGame


#######################################################################################################################################
def _generate_play_card_notification(
    actor_name: str, card_name: str, target_name: str, card_json: str
) -> str:
    """生成出牌通知消息。"""
    return f"""# 通知！{actor_name} 使用卡牌 {card_name}, 目标 {target_name}

{card_json}"""


#######################################################################################################################################
@final
class PlayCardsActionSystem(ReactiveProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: TCGGame = game_context

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(PlayCardsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(PlayCardsAction) and entity.has(HandComponent)

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        """处理出牌动作。

        检查战斗是否进行中，如是则为每个出牌的角色生成通知消息并添加到其对话上下文。
        通知包含角色名、卡牌名、目标和卡牌完整数据(JSON)。
        """
        if not self._game.current_combat_sequence.is_ongoing:
            # 必须是 进行中的阶段！
            return

        for actor_entity in entities:

            play_cards_action = actor_entity.get(PlayCardsAction)

            message = _generate_play_card_notification(
                actor_name=actor_entity.name,
                card_name=play_cards_action.card.name,
                target_name=play_cards_action.target,
                card_json=play_cards_action.card.model_dump_json(),
            )

            self._game.append_human_message(actor_entity, message)
