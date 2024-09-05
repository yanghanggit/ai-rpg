from rpg_game.base_game import BaseGame
from loguru import logger
from gameplay_systems.action_components import (
    BroadcastAction,
    SpeakAction,
    GoToAction,
    WhisperAction,
    PickUpPropAction,
    StealPropAction,
    GivePropAction,
    BehaviorAction,
    EquipPropAction,
)

from overrides import override
from gameplay_systems.components import ActorComponent
from player.player_proxy import PlayerProxy
from typing import cast
from player.base_command import PlayerCommand




####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerGoTo(PlayerCommand):

    @property
    def stage_name(self) -> str:
        return self.split_command(self._input_val, self._name)

    @override
    def execute(self, game: BaseGame, player_proxy: PlayerProxy) -> None:
        from rpg_game.rpg_game import RPGGame

        rpg_game = cast(RPGGame, game)
        player_entity = rpg_game._entitas_context.get_player_entity(player_proxy._name)
        if player_entity is None:
            return

        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            GoToAction, actor_comp.name, GoToAction.__name__, [self.stage_name]
        )

        self.add_player_planning_message(
            player_entity,
            f"""{{"{GoToAction.__name__}": ["{self.stage_name}"]}}""",
            rpg_game,
        )


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerBroadcast(PlayerCommand):

    @property
    def broadcast_content(self) -> str:
        return self.split_command(self._input_val, self._name)

    @override
    def execute(self, game: BaseGame, player_proxy: PlayerProxy) -> None:
        from rpg_game.rpg_game import RPGGame

        rpg_game = cast(RPGGame, game)
        player_entity = rpg_game._entitas_context.get_player_entity(player_proxy._name)
        if player_entity is None:
            return

        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            BroadcastAction,
            actor_comp.name,
            BroadcastAction.__name__,
            [self.broadcast_content],
        )

        self.add_player_planning_message(
            player_entity,
            f"""{{"{BroadcastAction.__name__}": ["{self.broadcast_content}"]}}""",
            rpg_game,
        )


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerSpeak(PlayerCommand):

    @property
    def speak_content(self) -> str:
        return self.split_command(self._input_val, self._name)

    @override
    def execute(self, game: BaseGame, player_proxy: PlayerProxy) -> None:
        from rpg_game.rpg_game import RPGGame

        rpg_game = cast(RPGGame, game)
        player_entity = rpg_game._entitas_context.get_player_entity(player_proxy._name)
        if player_entity is None:
            return

        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            SpeakAction, actor_comp.name, SpeakAction.__name__, [self.speak_content]
        )

        self.add_player_planning_message(
            player_entity,
            f"""{{"{SpeakAction.__name__}": ["{self.speak_content}"]}}""",
            rpg_game,
        )


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerWhisper(PlayerCommand):

    @property
    def whisper_content(self) -> str:
        return self.split_command(self._input_val, self._name)

    @override
    def execute(self, game: BaseGame, player_proxy: PlayerProxy) -> None:
        from rpg_game.rpg_game import RPGGame

        rpg_game = cast(RPGGame, game)
        player_entity = rpg_game._entitas_context.get_player_entity(player_proxy._name)
        if player_entity is None:
            return

        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            WhisperAction,
            actor_comp.name,
            WhisperAction.__name__,
            [self.whisper_content],
        )

        self.add_player_planning_message(
            player_entity,
            f"""{{"{WhisperAction.__name__}": ["{self.whisper_content}"]}}""",
            rpg_game,
        )


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerPickUpProp(PlayerCommand):

    @property
    def prop_name(self) -> str:
        return self.split_command(self._input_val, self._name)

    @override
    def execute(self, game: BaseGame, player_proxy: PlayerProxy) -> None:
        from rpg_game.rpg_game import RPGGame

        rpg_game = cast(RPGGame, game)
        player_entity = rpg_game._entitas_context.get_player_entity(player_proxy._name)
        if player_entity is None:
            return

        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            PickUpPropAction,
            actor_comp.name,
            PickUpPropAction.__name__,
            [self.prop_name],
        )

        # 模拟添加一个plan的发起。
        self.add_player_planning_message(
            player_entity,
            f"""{{"{PickUpPropAction.__name__}": ["{self.prop_name}"]}}""",
            rpg_game,
        )


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerSteal(PlayerCommand):

    @property
    def format_string(self) -> str:
        return self.split_command(self._input_val, self._name)

    @override
    def execute(self, game: BaseGame, player_proxy: PlayerProxy) -> None:
        from rpg_game.rpg_game import RPGGame

        rpg_game = cast(RPGGame, game)
        player_entity = rpg_game._entitas_context.get_player_entity(player_proxy._name)
        if player_entity is None:
            return

        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            StealPropAction,
            actor_comp.name,
            StealPropAction.__name__,
            [self.format_string],
        )

        self.add_player_planning_message(
            player_entity,
            f"""{{"{StealPropAction.__name__}": ["{self.format_string}"]}}""",
            rpg_game,
        )


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerGiveProp(PlayerCommand):

    @property
    def format_string(self) -> str:
        return self.split_command(self._input_val, self._name)

    @override
    def execute(self, game: BaseGame, player_proxy: PlayerProxy) -> None:
        from rpg_game.rpg_game import RPGGame

        rpg_game = cast(RPGGame, game)
        player_entity = rpg_game._entitas_context.get_player_entity(player_proxy._name)
        if player_entity is None:
            return

        # 添加行动
        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            GivePropAction,
            actor_comp.name,
            GivePropAction.__name__,
            [self.format_string],
        )

        assert "@" in self.format_string
        assert "/" in self.format_string
        self.add_player_planning_message(
            player_entity,
            f"""{{"{GivePropAction.__name__}": ["{self.format_string}"]}}""",
            rpg_game,
        )


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerBehavior(PlayerCommand):

    @property
    def behavior_sentence(self) -> str:
        return self.split_command(self._input_val, self._name)

    @override
    def execute(self, game: BaseGame, player_proxy: PlayerProxy) -> None:
        from rpg_game.rpg_game import RPGGame

        rpg_game = cast(RPGGame, game)
        player_entity = rpg_game._entitas_context.get_player_entity(player_proxy._name)
        if player_entity is None:
            return

        logger.debug(f"PlayerBehavior, {player_proxy._name}: {self.behavior_sentence}")
        actor_comp = player_entity.get(ActorComponent)

        player_entity.add(
            BehaviorAction,
            actor_comp.name,
            BehaviorAction.__name__,
            [self.behavior_sentence],
        )

        self.add_player_planning_message(
            player_entity,
            f"""{{"{BehaviorAction.__name__}": ["{self.behavior_sentence}"]}}""",
            rpg_game,
        )


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerEquip(PlayerCommand):

    @property
    def equip_name(self) -> str:
        return self.split_command(self._input_val, self._name)

    @override
    def execute(self, game: BaseGame, player_proxy: PlayerProxy) -> None:
        from rpg_game.rpg_game import RPGGame

        rpg_game = cast(RPGGame, game)
        player_entity = rpg_game._entitas_context.get_player_entity(player_proxy._name)
        if player_entity is None:
            return

        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            EquipPropAction,
            actor_comp.name,
            EquipPropAction.__name__,
            [self.equip_name],
        )

        self.add_player_planning_message(
            player_entity,
            f"""{{"{EquipPropAction.__name__}": ["{self.equip_name}"]}}""",
            rpg_game,
        )


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
