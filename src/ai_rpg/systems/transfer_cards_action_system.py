"""传递卡牌系统：按命中分配投递副本，只传一跳、落地即失去传递性。"""

import json
from typing import Dict, Final, List, Tuple, final
from uuid import uuid4

from loguru import logger
from overrides import override

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    ActorComponent,
    Card,
    DeathComponent,
    HandComponent,
    HumanMessage,
    PlayCardsAction,
)
from ..utils import prompt_builder
from .card_common import build_received_card_tag


#######################################################################################################################################
def _build_transfer_outcome_tag(card: Card, deliveries: List[Tuple[str, int]]) -> str:
    """生成 `transfer_outcome` 标记值：本次传递的牌名 + 每个接收方的份数。"""
    return json.dumps(
        {"card": card.name, "deliveries": dict(deliveries)}, ensure_ascii=False
    )


#######################################################################################################################################
@prompt_builder
def _build_transfer_outcome_prompt(
    card_name: str,
    deliveries: List[Tuple[str, int]],
    giver_name: str,
    round_number: int,
) -> str:
    """生成传递结果消息（写给传递者）：每个角色收到几份副本。

    副本数按解析目标列表的出现次数计（`SPREAD` 一击一项、同一角色可被多击命中），
    所以消息必须带上每人的份数，否则出牌者无法区分「散射三击全打中一人」与「各中一击」。
    """
    parts = [
        (f"你自己 {count} 份" if name == giver_name else f"{name} {count} 份")
        for name, count in deliveries
    ]
    return "\n".join(
        [
            f"【第 {round_number} 回合 · 传递卡牌】",
            f"「{card_name}」的副本已进入：{'、'.join(parts)}。",
            "副本落地即不可再传递；你打出的这一张仍按普通出牌流程处理。",
        ]
    )


#######################################################################################################################################
@prompt_builder
def _build_received_card_prompt(
    giver_name: str,
    card_name: str,
    round_number: int,
    self_transfer: bool,
    count: int,
) -> str:
    """生成获得卡牌消息（写给接收方）：手牌里多了几份、从哪里来的副本。"""
    if self_transfer:
        body = f"你打出的「{card_name}」复制出 {count} 份副本，已回到你的手牌。"
    else:
        body = f"{giver_name} 把「{card_name}」的副本放进了你的手牌，共 {count} 份。"
    return "\n".join(
        [
            f"【第 {round_number} 回合 · 获得卡牌】",
            body,
            "传递只有一跳：这些副本不可再转手给别人。",
        ]
    )


#######################################################################################################################################
@final
class TransferCardsActionSystem(ReactiveProcessor):
    """可传递卡牌转移系统。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(PlayCardsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(PlayCardsAction)
            and entity.has(HandComponent)
            and entity.has(ActorComponent)
            and entity.get(PlayCardsAction).card.transferable
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        """将可传递卡牌从源手牌移除，并按命中分配把副本投递给目标。

        副本数 = 该角色在解析目标列表中的出现次数：`SPREAD` 的目标列表就是命中分配
        （一击一项，同一角色可被多击命中，只剩一个目标时全部命中都落在它身上），
        因此 5 击散射全打中同一只怪就投 5 份副本；`SINGLE` / `ALL` / `SELF` 的列表里
        每名角色各一项，所以各拿一份。

        副本落地即把 `transferable` 置为 False——传递只有一跳：收到副本的目标不能再次转手。
        本系统负责「副本进入谁的手牌」这一数据流转，因此也负责把这笔流转告知双方：
        每个接收方一条「获得卡牌」，传递者一条「传递卡牌」结果。
        """
        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("TransferCardsActionSystem: 战斗未进行中，跳过卡牌转移")
            return

        for entity in entities:
            play_cards_action = entity.get(PlayCardsAction)
            card = play_cards_action.card

            # 防御性断言：filter 已保证只有 transferable 的牌进入；此处兜底防止旁路调用
            # 把非传递牌误当传递牌处理（那会错误地把它移出源手牌）。
            assert (
                card.transferable
            ), f"TransferCardsActionSystem: 非传递牌「{card.name}」不应进入转移流程"

            source_hand = entity.get(HandComponent)

            # 本回合编号（消息标注用），取法与出牌记录一致。
            round_number = len(self._game.current_dungeon_combat_room.combat.rounds)

            # 从源手牌移除本体（原卡后续由 DiscardCardsActionSystem 归入弃牌堆）。
            source_hand.cards = [c for c in source_hand.cards if c is not card]

            # 命中统计：角色 → 命中次数（dict 保持首次出现顺序），即该角色应收的副本数。
            counts: Dict[str, int] = {}
            for target_name in play_cards_action.targets:
                counts[target_name] = counts.get(target_name, 0) + 1
            deliveries: List[Tuple[str, int]] = list(counts.items())

            for target_name, count in deliveries:

                # 获取目标实体并进行基本校验
                target = self._game.get_actor_entity(target_name)
                assert target is not None, f"目标 {target_name} 不存在"
                assert target.has(HandComponent), f"目标 {target_name} 不存在手牌组件"
                assert not target.has(DeathComponent), f"目标 {target_name} 已死亡"

                # 自传递：目标即出牌者本人（target_type=SELF，或显式把自身选为目标）时，
                # 同样按其命中次数把副本留在其手牌。
                if target_name == play_cards_action.name:
                    logger.debug(
                        f"transfer_card: 自传递，复制 {count} 份「{card.name}」回 {target_name} 手牌"
                    )

                # 一击一份：每次命中各 copy 一份（新 uuid）；副本落地即失去传递性。
                target_hand = target.get(HandComponent)
                copied: Card = card
                for _ in range(count):
                    copied = card.model_copy(deep=True)
                    copied.uuid = str(uuid4())
                    copied.transferable = False
                    target_hand.cards.append(copied)
                logger.debug(
                    f"transfer_card: 「{card.name}」已 copy {count} 份到 {target_name} 的手牌（source={copied.source!r}，末份 uuid={copied.uuid}，transferable={copied.transferable}）"
                )

                # 副本已落地就必须告知持有者，否则目标（如怪物）下一回合会在决策提示词的
                # 「手牌」里凭空多出牌却无从解释来源，只能自行编造归因。
                self._game.add_human_message(
                    entity=target,
                    human_message=HumanMessage(
                        content=_build_received_card_prompt(
                            giver_name=play_cards_action.name,
                            card_name=copied.name,
                            round_number=round_number,
                            self_transfer=target_name == play_cards_action.name,
                            count=count,
                        ),
                        received_card=build_received_card_tag(copied),
                    ),
                )

            # 传递者同样需要知道副本落到谁手里、每人几份：出牌记录只说明「打出了哪张牌」，
            # 副本流向属于本系统的职责，不由出牌层代述。
            if deliveries:
                self._game.add_human_message(
                    entity=entity,
                    human_message=HumanMessage(
                        content=_build_transfer_outcome_prompt(
                            card_name=card.name,
                            deliveries=deliveries,
                            giver_name=play_cards_action.name,
                            round_number=round_number,
                        ),
                        transfer_outcome=_build_transfer_outcome_tag(card, deliveries),
                    ),
                )
