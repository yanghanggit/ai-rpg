"""出牌动作系统模块。

处理战斗中角色的出牌动作，向角色的对话上下文添加出牌通知，
包含卡牌名称、目标、描述和卡牌属性（治疗/攻击/防御）。
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
    """生成出牌通知消息。

    Args:
        actor_name: 出牌角色名称（当前未使用）
        card: 卡牌对象，包含名称、描述、属性和目标
        target_names: 系统指定的目标名称列表

    Returns:
        格式化的出牌通知字符串，包含卡牌名、目标、描述和属性
    """

    # 格式化目标显示
    if len(target_names) == 0:
        target_display = "无目标"
    elif len(target_names) == 1:
        target_display = target_names[0]
    else:
        target_display = f"[{', '.join(target_names)}]"

    # 获取卡牌属性
    card_stats = card.stats

    return f"""使用卡牌: {card.name}

目标: 
{target_display}

描述: 
{card.description}"""


#######################################################################################################################################
@final
class PlayCardsActionSystem(ReactiveProcessor):
    """出牌动作系统。

    响应 PlayCardsAction 组件的添加事件，向角色发送出牌通知消息。
    通知包含卡牌的完整信息：名称、目标、描述和属性（治疗/攻击/防御）。

    触发条件：
    - 实体添加 PlayCardsAction 组件
    - 战斗序列处于进行中(ongoing)状态

    执行流程：
    1. 发送出牌指令（第N回合使用卡牌）
    2. 添加AI出牌执行消息（卡牌详情）
    3. 为场景实体添加仲裁动作标记
    """

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

        # 获取当前回合数
        current_round_number = len(self._game.current_combat_sequence.current_rounds)

        for actor_entity in entities:

            play_cards_action = actor_entity.get(PlayCardsAction)

            # 添加出牌通知到角色对话上下文(模拟的)
            self._game.add_human_message(
                actor_entity,
                f"""# 指令！这是第 {current_round_number} 回合，使用卡牌！""",
                action_type="play_card_command",
            )

            self._game.add_ai_message(
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
            current_stage = self._game.resolve_stage_entity(actor_entity)
            assert current_stage is not None, "无法获取角色所在场景实体！"
            if not current_stage.has(ArbitrationAction):
                current_stage.replace(
                    ArbitrationAction,
                    current_stage.name,
                    "",
                    "",
                )
