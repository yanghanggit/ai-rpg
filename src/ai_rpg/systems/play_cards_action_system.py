"""出牌动作系统模块。

处理战斗中角色的出牌动作，向角色的对话上下文添加出牌通知，
包含卡牌名称、目标、描述和卡牌属性（治疗/攻击/防御）。
仅在战斗进行中(ongoing)阶段执行。
"""

from typing import Final, final
from loguru import logger
from overrides import override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    HandComponent,
    DiscardDeckComponent,
    PlayCardsAction,
    ActorComponent,
    AgentEvent,
)
from ..game.tcg_game import TCGGame


#######################################################################################################################################
def _generate_play_card_context_prompt(
    play_cards_action: PlayCardsAction,
    round_number: int,
) -> str:
    """生成出牌上下文消息，注入角色的对话历史，帮助 LLM 感知本回合出牌情况。"""
    card = play_cards_action.card
    targets_str = (
        "、".join(play_cards_action.targets) if play_cards_action.targets else "无目标"
    )
    lines = [
        f"【第 {round_number} 回合 · 出牌】",
        f"你使用了卡牌「{card.name}」。",
        f"目标：{targets_str}",
    ]
    if play_cards_action.action:
        lines.insert(2, f"行动叙述：{play_cards_action.action}")
    stats_parts = []
    if card.damage_dealt > 0:
        hit_info = f"（{card.hit_count} 段）" if card.hit_count > 1 else ""
        stats_parts.append(f"造成伤害 {card.damage_dealt}{hit_info}")
    if card.block_gain > 0:
        stats_parts.append(f"获得格挡 {card.block_gain}")
    if stats_parts:
        lines.append(f"卡牌效果：{'，'.join(stats_parts)}。")
    return "\n".join(lines)


#######################################################################################################################################
def _generate_action_notice_for_others(actor_name: str, round_number: int) -> str:
    """生成出牌行动预告，广播给场景内其他角色，维护观察者视角的上下文连贯性。"""
    actor_short_name = actor_name.split(".")[-1]
    return f"【第 {round_number} 回合】{actor_short_name} 正在出牌。"


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

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

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
            and entity.has(DiscardDeckComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        """处理出牌动作。

        检查战斗是否进行中，如是则为每个出牌的角色生成通知消息并添加到其对话上下文。
        通知包含角色名、卡牌名、目标和卡牌完整数据(JSON)。
        """
        if not self._game.current_dungeon.is_ongoing:
            # 必须是 进行中的阶段！
            logger.debug("PlayCardsActionSystem: 战斗未进行中，跳过出牌处理")
            return

        assert len(entities) == 1, "PlayCardsActionSystem: 一次只能处理一个出牌动作实体"
        logger.debug(
            f"PlayCardsActionSystem: 触发出牌处理，找到 {len(entities)} 个出牌实体"
        )

        # 获取当前回合数
        current_rounds = self._game.current_dungeon.current_rounds
        assert (
            current_rounds is not None
        ), "PlayCardsActionSystem: current_rounds is None"

        last_round = self._game.current_dungeon.latest_round
        assert last_round is not None, "PlayCardsActionSystem: latest_round is None"

        logger.debug(
            f"PlayCardsActionSystem: 当前回合数 {len(current_rounds)}，最新回合状态: {'已完成' if last_round.is_round_completed else '未完成'}"
        )

        for entity in entities:

            # 输出出牌信息日志，包含角色名、卡牌名、卡牌属性（治疗/攻击/防御）和目标
            play_cards_action = entity.get(PlayCardsAction)
            logger.debug(
                f"  [{play_cards_action.name}] 出牌 → 卡牌: {play_cards_action.card.name}"
                f" | damage_dealt={play_cards_action.card.damage_dealt} block_gain={play_cards_action.card.block_gain}"
                f" | 目标: {play_cards_action.targets}"
                f" | 行动叙事: {play_cards_action.action}"
            )

            # 写一个assert 要求 entity.name 必须在 last_round.action_order 中，确保出牌角色在当前回合的行动顺序中
            assert entity.name in last_round.action_order, (
                f"PlayCardsActionSystem: 出牌角色 {entity.name} 不在当前回合的行动顺序中！"
                f" action_order={last_round.action_order}"
            )
            assert entity.name == last_round.current_actor, (
                f"PlayCardsActionSystem: 出牌角色 {entity.name} 不是当前回合的行动者！"
                f" current_actor={last_round.current_actor}"
            )

            # 将出牌角色写入本回合 completed_actors（允许同一角色多次出现）
            last_round.completed_actors.append(play_cards_action.name)
            last_round.play_count[play_cards_action.name] = (
                last_round.play_count.get(play_cards_action.name, 0) + 1
            )
            logger.debug(
                f"  completed_actors: {last_round.completed_actors} / {last_round.action_order}"
            )

            # 从 HandComponent 移除已出的卡牌，并将其归入 DiscardDeckComponent
            hand_comp = entity.get(HandComponent)
            assert hand_comp is not None, f"{entity.name} 缺少 HandComponent"
            assert entity.has(
                DiscardDeckComponent
            ), f"{entity.name} 缺少 DiscardDeckComponent"
            # 这里通过对象身份（is）而非等値比较（==）来确保正确移除特定的卡牌实例，避免同名卡牌导致的误删问题
            played_card = play_cards_action.card
            new_hand_cards = [c for c in hand_comp.cards if c is not played_card]

            hand_comp.cards = new_hand_cards

            # 将已出的卡牌归入 DiscardDeckComponent
            discard_comp = entity.get(DiscardDeckComponent)
            assert discard_comp is not None, f"{entity.name} 缺少 DiscardDeckComponent"

            # 仅归档来源为本角色的卡牌；外来塞入牌（source != actor_name）直接丢弃
            if played_card.source == entity.name:
                discard_comp.cards.append(played_card)
                logger.debug(
                    f"  [{entity.name}] 手牌 {len(hand_comp.cards)} → {len(new_hand_cards)}，"
                    f"DiscardDeck 累计 {len(discard_comp.cards)} 张"
                )
            else:
                logger.debug(
                    f"  [{entity.name}] 外来牌 [{played_card.name}](source={played_card.source!r}) 已打出，source 不匹配，丢弃不归档"
                )

            # 为出牌角色注入本回合出牌上下文，作为其对话历史的一部分
            self._game.add_human_message(
                entity=entity,
                message_content=_generate_play_card_context_prompt(
                    play_cards_action=play_cards_action,
                    round_number=len(current_rounds),
                ),
                play_card_context=play_cards_action.card.model_dump_json(),
            )

            # 向场景内其他角色（排除出牌者自身与场景仲裁实体）广播简短的行动预告，
            # 使观察者上下文在收到仲裁结算之前已感知到出牌事件
            stage_entity = self._game.resolve_stage_entity(entity)
            assert (
                stage_entity is not None
            ), f"PlayCardsActionSystem: 无法找到 {entity.name} 所在的场景实体"
            self._game.broadcast_to_stage(
                entity=entity,
                agent_event=AgentEvent(
                    message=_generate_action_notice_for_others(
                        actor_name=play_cards_action.name,
                        round_number=len(current_rounds),
                    )
                ),
                exclude_entities={entity, stage_entity},
            )
