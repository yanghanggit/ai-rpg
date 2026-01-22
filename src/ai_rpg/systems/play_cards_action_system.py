"""出牌动作系统模块。

处理战斗中角色的出牌动作，向角色的对话上下文添加出牌通知，
包含卡牌名称、目标、描述和卡牌属性（治疗/攻击/防御）。
仅在战斗进行中(ongoing)阶段执行。
"""

from typing import Final, List, final
from loguru import logger
from overrides import override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    HandComponent,
    PlayCardsAction,
    Card,
    ActorComponent,
)
from ..game.tcg_game import TCGGame
from langchain_core.messages import AIMessage


#######################################################################################################################################
def _generate_play_card_command(current_round_number: int) -> str:
    """生成出牌指令消息。

    模拟系统发出的战斗指令，提示角色当前回合需要使用卡牌。
    此消息作为 Human Message 添加到角色上下文，引导角色进入出牌阶段。

    Args:
        current_round_number: 当前回合数

    Returns:
        格式化的出牌指令字符串
    """
    return f"""# 指令！第 {current_round_number} 回合：使用卡牌"""


#######################################################################################################################################
def _generate_play_card_notification(
    actor_name: str, card: Card, target_names: List[str]
) -> str:
    """生成出牌通知消息。

    模拟角色自主决策后使用卡牌的输出，作为 AI Message 添加到角色上下文。
    通过第一人称描述强化角色的自主性，让角色认为这是自己的选择。
    此消息将成为角色对话历史的一部分，影响后续交互的连贯性。

    Args:
        actor_name: 出牌角色名称（当前未使用）
        card: 卡牌对象，包含名称、描述和属性
        target_names: 系统指定的目标名称列表

    Returns:
        格式化的出牌通知字符串，包含卡牌名、目标和第一人称描述
    """

    # 格式化目标显示
    if len(target_names) == 0:
        target_display = "无目标"
    elif len(target_names) == 1:
        target_display = target_names[0]
    else:
        target_display = f"[{', '.join(target_names)}]"

    return f"""# 使用卡牌：{card.name}

目标：{target_display}

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
            logger.debug("PlayCardsActionSystem: 战斗未进行中，跳过出牌处理")
            return

        # 获取当前回合数
        current_round_number = len(self._game.current_combat_sequence.current_rounds)
        logger.debug(
            f"PlayCardsActionSystem: 处理第 {current_round_number} 回合，共 {len(entities)} 个角色出牌"
        )

        for actor_entity in entities:

            play_cards_action = actor_entity.get(PlayCardsAction)
            assert (
                play_cards_action is not None
            ), f"{actor_entity.name} 缺少 PlayCardsAction"

            # 生成出牌指令
            play_card_command = _generate_play_card_command(current_round_number)
            logger.debug(f"PlayCardsActionSystem: 生成出牌指令: \n{play_card_command}")

            # 添加出牌指令到角色对话上下文
            self._game.add_human_message(
                actor_entity,
                play_card_command,
                action_type="play_card_command",
            )

            # 生成卡牌详情通知
            play_card_notification = _generate_play_card_notification(
                actor_name=actor_entity.name,
                card=play_cards_action.card,
                target_names=play_cards_action.targets,
            )
            logger.debug(
                f"PlayCardsActionSystem: 生成出牌通知: \n{play_card_notification}"
            )

            # 添加AI出牌执行消息
            self._game.add_ai_message(
                actor_entity,
                [
                    AIMessage(
                        content=play_card_notification,
                        action_type="play_card_execution",
                    )
                ],
            )
