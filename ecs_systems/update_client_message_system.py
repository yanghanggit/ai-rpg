from entitas import ExecuteProcessor, Entity, Matcher  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from player.player_proxy import PlayerProxy
import player.utils
from rpg_game.rpg_entitas_context import RPGEntitasContext
from ecs_systems.action_components import (
    MindVoiceAction,
    WhisperAction,
    SpeakAction,
    BroadcastAction,
    StageNarrateAction,
    # AttackAction,
    GoToAction,
)

# from my_agent.agent_action import AgentAction
from typing import override
from loguru import logger
import gameplay.conversation_helper
import my_format_string.target_and_message_format_string
from rpg_game.rpg_game import RPGGame
from rpg_game.terminal_rpg_game import TerminalRPGGame
from rpg_game.web_server_multi_players_rpg_game import WebServerMultiplayersRPGGame
import my_format_string.target_and_message_format_string


# todo: 未完成
class UpdateClientMessageSystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._rpg_game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:
        assert len(self._rpg_game.player_names) > 0
        assert isinstance(self._rpg_game, WebServerMultiplayersRPGGame) or isinstance(
            self._rpg_game, TerminalRPGGame
        )
        for player_name in self._rpg_game.player_names:
            player_proxy = player.utils.get_player_proxy(player_name)
            player_entity = self._context.get_player_entity(player_name)
            if player_entity is None or player_proxy is None:
                logger.error(f"玩家{player_name}不存在，或者玩家未加入游戏")
                continue

            self.add_message_to_player_proxy(player_proxy, player_entity)

    ############################################################################################################
    def add_message_to_player_proxy(
        self, player_proxy: PlayerProxy, player_entity: Entity
    ) -> None:

        player_proxy.add_system_message(f"游戏回合:{self._context._execute_count}")

        self.stage_enviro_narrate_action_2_message(player_proxy, player_entity)
        self.handle_login_messages(
            player_proxy, player_entity
        )  # 先把缓存的消息推送出去，在场景描述之后

        self.mind_voice_action_2_message(player_proxy, player_entity)
        self.whisper_action_2_message(player_proxy, player_entity)
        self.broadcast_action_2_message(player_proxy, player_entity)
        self.speak_action_2_message(player_proxy, player_entity)
        # self.attack_action_2_message(player_proxy, player_entity)
        self.go_to_action_2_message(player_proxy, player_entity)

    ############################################################################################################
    def stage_enviro_narrate_action_2_message(
        self, player_proxy: PlayerProxy, player_entity: Entity
    ) -> None:
        stage = self._context.safe_get_stage_entity(player_entity)
        if stage is None:
            return
        if not stage.has(StageNarrateAction):
            return

        stage_narrate_action = stage.get(StageNarrateAction)
        # stage_narrate_action: AgentAction = enviro_comp.action
        if len(stage_narrate_action.values) == 0:
            return

        message = " ".join(stage_narrate_action.values)
        # action.join_values()
        player_proxy.add_stage_message(stage_narrate_action.name, message)

    ############################################################################################################
    def whisper_action_2_message(
        self, player_proxy: PlayerProxy, player_entity: Entity
    ) -> None:
        player_entity_stage = self._context.safe_get_stage_entity(player_entity)
        player_entity_name = self._context.safe_get_entity_name(player_entity)
        entities = self._context.get_group(Matcher(WhisperAction)).entities
        for entity in entities:

            if entity == player_entity:
                # 不能和自己对话
                continue

            his_stage_entity = self._context.safe_get_stage_entity(entity)
            if his_stage_entity != player_entity_stage:
                # 场景不一样，不能看见
                continue

            whisper_action_action = entity.get(WhisperAction)
            target_and_message = my_format_string.target_and_message_format_string.target_and_message_values(
                whisper_action_action.values
            )
            for tp in target_and_message:
                targetname = tp[0]
                message = tp[1]
                if (
                    gameplay.conversation_helper.check_conversation_enable(
                        self._context, entity, targetname
                    )
                    != gameplay.conversation_helper.ErrorConversationEnable.VALID
                ):
                    continue
                if player_entity_name != targetname:
                    continue
                # 最后添加
                mm = my_format_string.target_and_message_format_string.make_target_and_message(
                    targetname, message
                )
                player_proxy.add_actor_message(
                    whisper_action_action.name, f"""<client>{mm}"""
                )

    ############################################################################################################
    def broadcast_action_2_message(
        self, player_proxy: PlayerProxy, player_entity: Entity
    ) -> None:
        player_entity_stage = self._context.safe_get_stage_entity(player_entity)
        entities = self._context.get_group(Matcher(BroadcastAction)).entities
        for entity in entities:

            if entity == player_entity:
                # 不能和自己对话
                continue

            his_stage_entity = self._context.safe_get_stage_entity(entity)
            if his_stage_entity != player_entity_stage:
                # 场景不一样，不能看见
                continue

            broadcast_action = entity.get(BroadcastAction)
            single_val = " ".join(broadcast_action.values)
            player_proxy.add_actor_message(
                broadcast_action.name, f"""<client><@all>{single_val}"""
            )

    ############################################################################################################
    def speak_action_2_message(
        self, player_proxy: PlayerProxy, player_entity: Entity
    ) -> None:
        player_entity_stage = self._context.safe_get_stage_entity(player_entity)
        entities = self._context.get_group(Matcher(SpeakAction)).entities
        for entity in entities:

            if entity == player_entity:
                # 不能和自己对话
                continue

            his_stage_entity = self._context.safe_get_stage_entity(entity)
            if his_stage_entity != player_entity_stage:
                # 场景不一样，不能看见
                continue

            speak_action = entity.get(SpeakAction)
            target_and_message = my_format_string.target_and_message_format_string.target_and_message_values(
                speak_action.values
            )
            for tp in target_and_message:
                targetname = tp[0]
                message = tp[1]
                if (
                    gameplay.conversation_helper.check_conversation_enable(
                        self._context, entity, targetname
                    )
                    != gameplay.conversation_helper.ErrorConversationEnable.VALID
                ):
                    continue

                mm = my_format_string.target_and_message_format_string.make_target_and_message(
                    targetname, message
                )
                player_proxy.add_actor_message(speak_action.name, f"""<client>{mm}""")

    ############################################################################################################
    def mind_voice_action_2_message(
        self, player_proxy: PlayerProxy, player_entity: Entity
    ) -> None:
        player_entity_stage = self._context.safe_get_stage_entity(player_entity)
        entities = self._context.get_group(Matcher(MindVoiceAction)).entities
        for entity in entities:

            if entity == player_entity:
                # 自己没有mindvoice
                continue

            his_stage_entity = self._context.safe_get_stage_entity(entity)
            if his_stage_entity != player_entity_stage:
                # 只添加同一个场景的mindvoice
                continue

            mind_voice_action = entity.get(MindVoiceAction)
            single_value = " ".join(mind_voice_action.values)
            player_proxy.add_actor_message(
                mind_voice_action.name, f"""<client><心理活动>{single_value}"""
            )

    ############################################################################################################
    # def attack_action_2_message(
    #     self, player_proxy: PlayerProxy, player_entity: Entity
    # ) -> None:
    #     player_entity_stage = self._context.safe_get_stage_entity(player_entity)
    #     entities = self._context.get_group(Matcher(AttackAction)).entities
    #     for entity in entities:

    #         if entity == player_entity:
    #             continue

    #         his_stage_entity = self._context.safe_get_stage_entity(entity)
    #         if his_stage_entity != player_entity_stage:
    #             continue

    #         attack_action = entity.get(AttackAction)
    #         # attack_action: AgentAction = attack_action_component.action
    #         if len(attack_action.values) == 0:
    #             logger.error("attack_action_2_message error")
    #             continue

    #         targetname = attack_action.values[0]
    #         player_proxy.add_actor_message(
    #             attack_action.name, f"""准备对{targetname}发起了攻击"""
    #         )

    ############################################################################################################
    def go_to_action_2_message(
        self, player_proxy: PlayerProxy, player_entity: Entity
    ) -> None:
        player_entity_stage = self._context.safe_get_stage_entity(player_entity)
        entities = self._context.get_group(Matcher(GoToAction)).entities
        for entity in entities:

            if entity == player_entity:
                continue

            his_stage_entity = self._context.safe_get_stage_entity(entity)
            if his_stage_entity != player_entity_stage:
                continue

            go_to_action = entity.get(GoToAction)
            # go_to_action: AgentAction = go_to_action_component.action
            if len(go_to_action.values) == 0:
                logger.error("go_to_action_2_message error")
                continue

            stage_name = go_to_action.values[0]
            player_proxy.add_actor_message(
                go_to_action.name, f"""<client>准备去往{stage_name}"""
            )

    ############################################################################################################
    def handle_login_messages(
        self, player_proxy: PlayerProxy, player_entity: Entity
    ) -> None:
        for message in player_proxy._login_messages:
            player_proxy.add_actor_message(message[0], f"""<client>{message[1]}""")
        player_proxy._login_messages.clear()


############################################################################################################
