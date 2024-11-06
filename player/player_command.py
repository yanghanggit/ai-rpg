from rpg_game.base_game import BaseGame
from loguru import logger
from my_components.action_components import (
    BroadcastAction,
    SpeakAction,
    GoToAction,
    WhisperAction,
    PickUpPropAction,
    StealPropAction,
    GivePropAction,
    BehaviorAction,
    EquipPropAction,
    DeadAction,
)

from overrides import override
from my_components.components import ActorComponent
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
        player_entity = rpg_game.context.get_player_entity(player_proxy.name)
        if player_entity is None:
            return

        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(GoToAction, actor_comp.name, [self.stage_name])

        self.add_player_planning_message(
            player_entity,
            self.make_simple_message(GoToAction.__name__, [self.stage_name]),
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
        player_entity = rpg_game.context.get_player_entity(player_proxy.name)
        if player_entity is None:
            return

        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            BroadcastAction,
            actor_comp.name,
            [self.broadcast_content],
        )

        self.add_player_planning_message(
            player_entity,
            self.make_simple_message(
                BroadcastAction.__name__, [self.broadcast_content]
            ),
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
        player_entity = rpg_game.context.get_player_entity(player_proxy.name)
        if player_entity is None:
            return

        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(SpeakAction, actor_comp.name, [self.speak_content])

        self.add_player_planning_message(
            player_entity,
            self.make_simple_message(SpeakAction.__name__, [self.speak_content]),
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
        player_entity = rpg_game.context.get_player_entity(player_proxy.name)
        if player_entity is None:
            return

        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            WhisperAction,
            actor_comp.name,
            [self.whisper_content],
        )

        self.add_player_planning_message(
            player_entity,
            self.make_simple_message(WhisperAction.__name__, [self.whisper_content]),
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
        player_entity = rpg_game.context.get_player_entity(player_proxy.name)
        if player_entity is None:
            return

        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            PickUpPropAction,
            actor_comp.name,
            [self.prop_name],
        )

        # 模拟添加一个plan的发起。
        self.add_player_planning_message(
            player_entity,
            self.make_simple_message(PickUpPropAction.__name__, [self.prop_name]),
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
        player_entity = rpg_game.context.get_player_entity(player_proxy.name)
        if player_entity is None:
            return

        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            StealPropAction,
            actor_comp.name,
            [self.format_string],
        )

        self.add_player_planning_message(
            player_entity,
            self.make_simple_message(StealPropAction.__name__, [self.format_string]),
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
        player_entity = rpg_game.context.get_player_entity(player_proxy.name)
        if player_entity is None:
            return

        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            GivePropAction,
            actor_comp.name,
            [self.format_string],
        )

        assert "@" in self.format_string
        assert "/" in self.format_string
        self.add_player_planning_message(
            player_entity,
            self.make_simple_message(GivePropAction.__name__, [self.format_string]),
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
        player_entity = rpg_game.context.get_player_entity(player_proxy.name)
        if player_entity is None:
            return

        logger.debug(f"PlayerBehavior, {player_proxy.name}: {self.behavior_sentence}")
        actor_comp = player_entity.get(ActorComponent)

        player_entity.add(
            BehaviorAction,
            actor_comp.name,
            [self.behavior_sentence],
        )

        self.add_player_planning_message(
            player_entity,
            self.make_simple_message(BehaviorAction.__name__, [self.behavior_sentence]),
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
        player_entity = rpg_game.context.get_player_entity(player_proxy.name)
        if player_entity is None:
            return

        actor_comp = player_entity.get(ActorComponent)
        player_entity.add(
            EquipPropAction,
            actor_comp.name,
            [self.equip_name],
        )

        self.add_player_planning_message(
            player_entity,
            self.make_simple_message(EquipPropAction.__name__, [self.equip_name]),
            rpg_game,
        )


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerKill(PlayerCommand):

    @property
    def target_name(self) -> str:
        return self.split_command(self._input_val, self._name)

    @override
    def execute(self, game: BaseGame, player_proxy: PlayerProxy) -> None:
        from rpg_game.rpg_game import RPGGame

        rpg_game = cast(RPGGame, game)
        player_entity = rpg_game.context.get_player_entity(player_proxy.name)
        if player_entity is None:
            return

        target_entity = rpg_game.context.get_entity_by_name(self.target_name)
        if target_entity is None:
            logger.error(f"没有找到目标:{self.target_name}")
            return

        if not target_entity.has(ActorComponent):
            logger.error(f"目标没有ActorComponent:{self.target_name}， 无法杀死")
            return

        actor_comp = target_entity.get(ActorComponent)
        target_entity.add(DeadAction, actor_comp.name, [])


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
