"""出牌动作系统模块。"""

from typing import Dict, Final, List, Sequence, final
from uuid import uuid4

from loguru import logger
from overrides import override

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_combat_processor import (
    consume_energy,
    get_current_turn_actor,
)
from ..game.dbg_game import DBGGame
from ..models import (
    ActorComponent,
    AgentEvent,
    Card,
    DeathComponent,
    EquippedGearComponent,
    HandComponent,
    HumanMessage,
    PlayCardsAction,
)
from ..utils import prompt_builder


#######################################################################################################################################
@prompt_builder
def _build_play_card_record_prompt(
    play_cards_action: PlayCardsAction,
    round_number: int,
) -> str:
    """生成出牌记录消息，注入角色的对话历史，帮助 LLM 感知本回合出牌情况。"""
    card = play_cards_action.card
    targets_str = (
        "、".join(play_cards_action.targets) if play_cards_action.targets else "无目标"
    )
    lines = [
        f"【第 {round_number} 回合 · 出牌】",
        f"你使用了卡牌「{card.name}」。",
        f"目标：{targets_str}",
    ]
    stats_parts = []
    if card.damage > 0:
        hit_info = f"（{card.hit_count} 段）" if card.hit_count > 1 else ""
        stats_parts.append(f"造成伤害 {card.damage}{hit_info}")
    if stats_parts:
        lines.append(f"卡牌效果：{'，'.join(stats_parts)}。")
    return "\n".join(lines)


#######################################################################################################################################
@prompt_builder
def _build_action_notice_for_others(actor_name: str, round_number: int) -> str:
    """生成出牌行动预告，广播给场景内其他角色，维护观察者视角的叙事连贯性。"""
    return f"【第 {round_number} 回合】{actor_name} 正在出牌。"


#######################################################################################################################################
@prompt_builder
def _build_unplayable_card_error_message(actor_name: str, card_name: str) -> str:
    """构建不可出牌卡牌的拦截提示（写入出牌者上下文，供 LLM 下次决策参考）。"""
    return f"""# 提示！{actor_name} 试图打出「{card_name}」，但该卡牌不可出牌（playable=False）。

**提示：** playable=False 的卡牌不能出牌，只能留在手牌中（如带回合结束词缀的卡牌），下一次决策时请不要选择它。"""


#######################################################################################################################################
@final
class PlayCardsActionSystem(ReactiveProcessor):
    """出牌动作系统。"""

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
        )

    #######################################################################################################################################
    def _transfer_card_copy(self, card: Card, target_names: Sequence[str]) -> int:
        """将可传递卡牌 copy 一份到每个存活目标的手牌；返回实际 copy 数量。

        复制时 source 保持原卡，uuid 重新生成；重复目标名去重，只 copy 一次。
        """
        copied_count = 0
        for target_name in dict.fromkeys(target_names):
            target = self._game.get_actor_entity(target_name)
            if (
                target is None
                or target.has(DeathComponent)
                or not target.has(HandComponent)
            ):
                continue
            copied = card.model_copy(deep=True)
            copied.uuid = str(uuid4())
            target.get(HandComponent).cards.append(copied)
            copied_count += 1
            logger.debug(
                f"transfer_card_copy: 「{card.name}」已 copy 到 {target_name} 的手牌"
            )
        return copied_count

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        """处理出牌动作。"""
        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            # 必须是 进行中的阶段！
            logger.debug("PlayCardsActionSystem: 战斗未进行中，跳过出牌处理")
            return

        assert len(entities) == 1, "PlayCardsActionSystem: 一次只能处理一个出牌动作实体"
        logger.debug(
            f"PlayCardsActionSystem: 触发出牌处理，找到 {len(entities)} 个出牌实体"
        )

        # 获取当前回合数
        current_rounds = self._game.current_dungeon_combat_room.combat.rounds
        assert (
            current_rounds is not None
        ), "PlayCardsActionSystem: current_rounds is None"

        last_round = self._game.current_dungeon_combat_room.combat.latest_round
        assert last_round is not None, "PlayCardsActionSystem: latest_round is None"

        logger.debug(
            f"PlayCardsActionSystem: 当前回合数 {len(current_rounds)}，最新回合状态: {'已完成' if last_round.is_completed else '未完成'}"
        )

        for entity in entities:

            # 输出出牌信息日志，包含角色名、卡牌名、卡牌属性（治疗/攻击/防御）和目标
            play_cards_action = entity.get(PlayCardsAction)

            # 计算端拦截：不可出牌的卡（playable=False）不进入出牌流程，防止 LLM 决策误选
            if not play_cards_action.card.playable:
                logger.error(
                    f"PlayCardsActionSystem: 卡牌 '{play_cards_action.card.name}' "
                    f"不可出牌（playable=False），拦截出牌"
                )
                # 将拦截原因写入出牌者上下文，让 LLM 下次决策时理解
                self._game.add_human_message(
                    entity=entity,
                    human_message=HumanMessage(
                        content=_build_unplayable_card_error_message(
                            play_cards_action.name,
                            play_cards_action.card.name,
                        )
                    ),
                )
                entity.remove(PlayCardsAction)
                continue

            # 组装填充 gear_item：从出牌者当前装备组件读取，供 PlayCardsArbitrationSystem 直接使用
            play_cards_action.gear_item = (
                entity.get(EquippedGearComponent).item
                if entity.has(EquippedGearComponent)
                else None
            )

            logger.debug(
                f"  [{play_cards_action.name}] 出牌 → 卡牌: {play_cards_action.card.name}"
                f" | damage={play_cards_action.card.damage}"
                f" | 目标: {play_cards_action.targets}"
            )

            # 写一个assert 要求 entity.name 必须是当前回合的行动者
            assert entity.name == get_current_turn_actor(self._game, last_round), (
                f"PlayCardsActionSystem: 出牌角色 {entity.name} 不是当前 turn 的行动者！"
                f" current_turn_actor={get_current_turn_actor(self._game, last_round)}"
            )

            # 每出一张牌消耗卡牌费用对应的 energy 点数（出牌本身不视为"完成行动"，
            # 仅 pass turn 才会写入 completed_actors 并真正交出行动权，见 PassTurnActionSystem；
            # 因此这里不调用 advance_turn ——是否轮到下一角色完全由 completed_actors 决定）
            consume_energy(entity, play_cards_action.card.cost)

            # 可传递卡牌：出牌时 copy 一份到每个解析目标的手牌（source 保持原卡）
            if play_cards_action.card.transferable:
                self._transfer_card_copy(
                    play_cards_action.card,
                    play_cards_action.targets,
                )

            logger.debug(
                f"  completed_actors: {last_round.completed_actors} / current_turn_actor_name={last_round.current_actor}"
            )

            # 为出牌角色注入本回合出牌记录，作为其对话历史的一部分
            self._game.add_human_message(
                entity=entity,
                human_message=HumanMessage(
                    content=_build_play_card_record_prompt(
                        play_cards_action=play_cards_action,
                        round_number=len(current_rounds),
                    ),
                    play_card_record=play_cards_action.card.model_dump_json(),
                ),
            )

            # 向场景内其他角色（排除出牌者自身与场景仲裁实体）广播简短的行动预告，
            # 使观察者在收到仲裁结算之前已感知到出牌事件
            stage_entity = self._game.resolve_stage_entity(entity)
            assert (
                stage_entity is not None
            ), f"PlayCardsActionSystem: 无法找到 {entity.name} 所在的场景实体"
            self._game.broadcast_to_stage(
                entity=entity,
                agent_event=AgentEvent(
                    message=_build_action_notice_for_others(
                        actor_name=play_cards_action.name,
                        round_number=len(current_rounds),
                    )
                ),
                exclude_entities={entity, stage_entity},
            )
