from typing import List, final
from loguru import logger
from overrides import override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor

# from .base_action_reactive_system import BaseActionReactiveSystem
from ..models import (
    ArbitrationAction,
    HandComponent,
    PlayCardsAction,
    Round,
)
from ..game.tcg_game import TCGGame


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
        if len(entities) == 0:
            return

        if not self._game.current_engagement.is_ongoing:
            return

        assert self._game.current_engagement.is_ongoing
        await self._handle_actions(entities)

    #######################################################################################################################################
    async def _handle_actions(self, react_entities: List[Entity]) -> None:
        # 处理场景
        current_stage = self._game.safe_get_stage_entity(react_entities[0])
        assert current_stage is not None
        assert not current_stage.has(ArbitrationAction)
        current_stage.replace(
            ArbitrationAction,
            current_stage.name,
            "",
            "",
        )
        logger.debug(
            f"PlayCardsActionSystem: stage_entity: {current_stage.name}, react_entities: {[entity.name for entity in react_entities]}"
        )

        # last_round = self._game.current_engagement.last_round
        self._handle_card_play_action(
            react_entities, self._game.current_engagement.latest_round
        )

    #######################################################################################################################################
    def _handle_card_play_action(
        self, actor_entities: List[Entity], round: Round
    ) -> None:
        for actor_entity2 in actor_entities:

            assert actor_entity2.has(HandComponent)
            play_cards_action = actor_entity2.get(PlayCardsAction)
            assert play_cards_action is not None
            assert play_cards_action.card.name != ""

            message = f""" # 发生事件！你开始行动
使用卡牌 = {play_cards_action.card.name}
目标 = {play_cards_action.target}
卡牌数据
{play_cards_action.card.model_dump_json()}"""

            self._game.append_human_message(actor_entity2, message)

    #######################################################################################################################################
