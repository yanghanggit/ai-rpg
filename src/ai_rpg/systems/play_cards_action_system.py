"""出牌动作系统模块。"""

from typing import Final, final, Dict, List
from loguru import logger
from overrides import override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    HandComponent,
    HumanMessage,
    PlayCardsAction,
    ActorComponent,
    AgentEvent,
)
from ..game.dbg_game import DBGGame
from ..game.dbg_entity_ops import consume_energy
from ..game.dbg_combat_processor import get_current_turn_actor


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
    stats_parts = []
    if card.damage_dealt > 0:
        hit_info = f"（{card.hit_count} 段）" if card.hit_count > 1 else ""
        stats_parts.append(f"造成伤害 {card.damage_dealt}{hit_info}")
    if card.energy_delta != 0:
        stats_parts.append(f"改变目标行动 {card.energy_delta:+d} 次")
    if stats_parts:
        lines.append(f"卡牌效果：{'，'.join(stats_parts)}。")
    return "\n".join(lines)


#######################################################################################################################################
def _generate_action_notice_for_others(actor_name: str, round_number: int) -> str:
    """生成出牌行动预告，广播给场景内其他角色，维护观察者视角的上下文连贯性。"""
    return f"【第 {round_number} 回合】{actor_name} 正在出牌。"


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
    @override
    async def react(self, entities: List[Entity]) -> None:
        """处理出牌动作。"""
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
            f"PlayCardsActionSystem: 当前回合数 {len(current_rounds)}，最新回合状态: {'已完成' if last_round.is_completed else '未完成'}"
        )

        for entity in entities:

            # 输出出牌信息日志，包含角色名、卡牌名、卡牌属性（治疗/攻击/防御）和目标
            play_cards_action = entity.get(PlayCardsAction)
            logger.debug(
                f"  [{play_cards_action.name}] 出牌 → 卡牌: {play_cards_action.card.name}"
                f" | damage_dealt={play_cards_action.card.damage_dealt}"
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

            logger.debug(
                f"  completed_actors: {last_round.completed_actors} / current_turn_actor_name={last_round.current_turn_actor_name}"
            )

            # 为出牌角色注入本回合出牌上下文，作为其对话历史的一部分
            self._game.add_human_message(
                entity=entity,
                human_message=HumanMessage(
                    content=_generate_play_card_context_prompt(
                        play_cards_action=play_cards_action,
                        round_number=len(current_rounds),
                    ),
                    play_card_context=play_cards_action.card.model_dump_json(),
                ),
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
