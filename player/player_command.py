from rpg_game.base_game import BaseGame
from loguru import logger
from my_components.action_components import (
    AnnounceAction,
    SpeakAction,
    GoToAction,
    WhisperAction,
    StealPropAction,
    GivePropAction,
    SkillAction,
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

        self.add_ai_message_as_planning(
            player_entity,
            self.generate_action_message(GoToAction.__name__, [self.stage_name]),
            rpg_game,
        )


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerAnnounce(PlayerCommand):

    @property
    def announce_content(self) -> str:
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
            AnnounceAction,
            actor_comp.name,
            [self.announce_content],
        )

        self.add_ai_message_as_planning(
            player_entity,
            self.generate_action_message(
                AnnounceAction.__name__, [self.announce_content]
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

        self.add_ai_message_as_planning(
            player_entity,
            self.generate_action_message(SpeakAction.__name__, [self.speak_content]),
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

        self.add_ai_message_as_planning(
            player_entity,
            self.generate_action_message(
                WhisperAction.__name__, [self.whisper_content]
            ),
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

        self.add_ai_message_as_planning(
            player_entity,
            self.generate_action_message(
                StealPropAction.__name__, [self.format_string]
            ),
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
        self.add_ai_message_as_planning(
            player_entity,
            self.generate_action_message(GivePropAction.__name__, [self.format_string]),
            rpg_game,
        )


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class PlayerSkill(PlayerCommand):

    @property
    def command(self) -> str:
        return self.split_command(self._input_val, self._name)

    @override
    def execute(self, game: BaseGame, player_proxy: PlayerProxy) -> None:
        from rpg_game.rpg_game import RPGGame

        rpg_game = cast(RPGGame, game)
        player_entity = rpg_game.context.get_player_entity(player_proxy.name)
        if player_entity is None:
            return

        logger.debug(f"PlayerSkillInvocation, {player_proxy.name}: {self.command}")
        actor_comp = player_entity.get(ActorComponent)

        player_entity.add(
            SkillAction,
            actor_comp.name,
            [self.command],
        )

        self.add_ai_message_as_planning(
            player_entity,
            self.generate_action_message(SkillAction.__name__, [self.command]),
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

        self.add_ai_message_as_planning(
            player_entity,
            self.generate_action_message(EquipPropAction.__name__, [self.equip_name]),
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
