"""出牌动作系统模块。

处理战斗中角色的出牌动作，当角色使用卡牌时，向该角色的对话上下文中
添加出牌通知消息，包含卡牌名称、目标和完整的卡牌数据。
仅在战斗进行中(ongoing)阶段执行。
"""

from typing import Final, final
from overrides import override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    HandComponent,
    PlayCardsAction,
    ArbitrationAction,
    Card,
)
from ..game.tcg_game import TCGGame
from langchain_core.messages import AIMessage


#######################################################################################################################################
def _generate_play_card_notification(
    actor_name: str, card: Card, target_name: str
) -> str:
    """生成出牌通知消息。"""
    message = f"""使用卡牌: {card.name}
目标: {target_name}
描述: {card.description}"""

    return message


#######################################################################################################################################
@final
class PlayCardsActionSystem(ReactiveProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: Final[TCGGame] = game_context

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

            # 添加出牌通知到角色对话上下文(模拟的)
            self._game.append_human_message(
                actor_entity, f"""# 指令！使用卡牌！""", action_type="play_card_command"
            )

            self._game.append_ai_message(
                actor_entity,
                [
                    AIMessage(
                        content=_generate_play_card_notification(
                            actor_name=actor_entity.name,
                            card=play_cards_action.card,
                            target_name=play_cards_action.target,
                        ),
                        action_type="play_card_execution",
                    )
                ],
            )

            # 添加仲裁动作标记
            current_stage = self._game.safe_get_stage_entity(actor_entity)
            assert current_stage is not None, "无法获取角色所在场景实体！"
            if not current_stage.has(ArbitrationAction):
                current_stage.replace(
                    ArbitrationAction,
                    current_stage.name,
                    "",
                    "",
                )
