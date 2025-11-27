"""出牌动作系统模块。

处理战斗中角色的出牌动作，当角色使用卡牌时，向该角色的对话上下文中
添加出牌通知消息，包含卡牌名称、目标和完整的卡牌数据。
仅在战斗进行中(ongoing)阶段执行。
"""

from typing import Final, List, final
from overrides import override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    HandComponent,
    PlayCardsAction,
    ArbitrationAction,
    Card,
    ActorComponent,
)
from ..game.tcg_game import TCGGame
from langchain_core.messages import AIMessage


#######################################################################################################################################
def _generate_play_card_notification(
    actor_name: str, card: Card, target_names: List[str]
) -> str:
    """生成出牌通知消息。"""

    # 格式化目标显示
    if len(target_names) == 0:
        actual_target_display = "无目标"
    elif len(target_names) == 1:
        actual_target_display = target_names[0]
    else:
        actual_target_display = f"[{', '.join(target_names)}]"

    # 格式化原定目标显示
    if len(card.targets) == 0:
        original_target_display = "无目标"
    elif len(card.targets) == 1:
        original_target_display = card.targets[0]
    else:
        original_target_display = f"[{', '.join(card.targets)}]"

    # 比较时忽略顺序，只关心目标集合是否相同
    if set(target_names) == set(card.targets):
        # 没有修改，直接显示预期目标
        return f"""使用卡牌: {card.name}
目标: {actual_target_display}
描述: {card.description}"""

    # 可能有修改，所以要显示预期目标和实际目标
    return f"""使用卡牌: {card.name}
原定目标: {original_target_display}
实际目标: {actual_target_display}
描述: {card.description}"""


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
        return (
            entity.has(PlayCardsAction)
            and entity.has(HandComponent)
            and entity.has(ActorComponent)
        )

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
                            target_names=play_cards_action.targets,
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
