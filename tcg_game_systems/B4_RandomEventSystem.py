from overrides import override
from agent.chat_request_handler import ChatRequestHandler
from entitas import ExecuteProcessor, Matcher  # type: ignore
from entitas.entity import Entity
from game.tcg_game import TCGGame
from typing import Deque, List, Optional
from rpg_models.event_models import AnnounceEvent
from tcg_models.v_0_0_1 import (
    # ActorInstance,
    # ActiveSkill,
    TriggerType,
    HitInfo,
    HitType,
    DamageType,
)
from components.components import (
    AttributeCompoment,
    ActorComponent,
    FinalAppearanceComponent,
    StageEnvironmentComponent,
)


class B4_RandomEventSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    @override
    def execute(self) -> None:
        pass

    async def a_execute1(self) -> None:
        pass