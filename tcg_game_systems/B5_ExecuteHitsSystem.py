from overrides import override
from agent.chat_request_handler import ChatRequestHandler
from entitas import ExecuteProcessor, Matcher  # type: ignore
from entitas.entity import Entity
from game.tcg_game_context import TCGGameContext
from game.tcg_game import TCGGame
from typing import Deque, List, final, cast
from tcg_models.v_0_0_1 import ActorInstance, ActiveSkill
from components.components import (
    AttributeCompoment,
    ActorComponent,
    FinalAppearanceComponent,
    StageEnvironmentComponent,
)
from loguru import logger
import json


class B5_ExecuteHitsSystem(ExecuteProcessor):

    def __init__(self, context: TCGGameContext) -> None:
        self._context: TCGGameContext = context
        self._game: TCGGame = cast(TCGGame, context._game)
        assert self._game is not None
