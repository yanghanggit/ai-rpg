from entitas import ExecuteProcessor, Entity, Matcher #type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from player.player_proxy import PlayerProxy, get_player_proxy
from rpg_game.rpg_entitas_context import RPGEntitasContext
from ecs_systems.action_components import MindVoiceActionComponent, WhisperActionComponent, SpeakActionComponent, \
    BroadcastActionComponent, EnviroNarrateActionComponent, \
    AttackActionComponent, GoToActionComponent
from my_agent.agent_action import AgentAction
from typing import override
from loguru import logger
from gameplay_checks.conversation_check import conversation_check, ErrorConversationEnable
from my_format_string.target_and_message_format_string import make_target_and_message
from rpg_game.rpg_game import RPGGame 
from rpg_game.terminal_rpg_game import TerminalRPGGame
from rpg_game.web_server_multi_players_rpg_game import WebServerMultiplayersRPGGame

# todo: 未完成
class UpdateClientMessageSystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpggame: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._rpggame: RPGGame = rpggame
############################################################################################################
    @override
    def execute(self) -> None:
        assert len(self._rpggame.player_names) > 0
        assert isinstance(self._rpggame, WebServerMultiplayersRPGGame) or isinstance(self._rpggame, TerminalRPGGame)
        for player_name in self._rpggame.player_names:
            player_proxy = get_player_proxy(player_name)
            player_entity = self._context.get_player_entity(player_name)
            if player_entity is None or player_proxy is None:
                logger.error(f"玩家{player_name}不存在，或者玩家未加入游戏")
                continue

            self._add_message_to_player_proxy_(player_proxy, player_entity)
############################################################################################################
    def _add_message_to_player_proxy_(self, playerproxy: PlayerProxy, player_entity: Entity) -> None:
        self.stage_enviro_narrate_action_2_message(playerproxy, player_entity)
        self.mind_voice_action_2_message(playerproxy, player_entity)
        self.whisper_action_2_message(playerproxy, player_entity)
        self.broadcast_action_2_message(playerproxy, player_entity)
        self.speak_action_2_message(playerproxy, player_entity)
        self.attack_action_2_message(playerproxy, player_entity)
        self.go_to_action_2_message(playerproxy, player_entity)
############################################################################################################
    def stage_enviro_narrate_action_2_message(self, playerproxy: PlayerProxy, player_entity: Entity) -> None:
        stage = self._context.safe_get_stage_entity(player_entity)
        if stage is None:
            return
        if not stage.has(EnviroNarrateActionComponent):
            return
        envirocomp: EnviroNarrateActionComponent = stage.get(EnviroNarrateActionComponent)
        action: AgentAction = envirocomp.action
        if len(action._values) == 0:
            return
        message = action.join_values()
        playerproxy.add_stage_message(action._actor_name, message)
############################################################################################################
    def whisper_action_2_message(self, playerproxy: PlayerProxy, player_entity: Entity) -> None:
        player_entity_stage = self._context.safe_get_stage_entity(player_entity)
        player_entity_name = self._context.safe_get_entity_name(player_entity) 
        entities = self._context.get_group(Matcher(WhisperActionComponent)).entities
        for entity in entities:

            if entity == player_entity:
                #不能和自己对话
                continue
            
            his_stage_entity = self._context.safe_get_stage_entity(entity)
            if his_stage_entity != player_entity_stage:
                #场景不一样，不能看见
                continue

            whisper_action_component: WhisperActionComponent = entity.get(WhisperActionComponent)
            action: AgentAction = whisper_action_component.action
            target_and_message = action.target_and_message_values()
            for tp in target_and_message:
                targetname = tp[0]
                message = tp[1]
                if conversation_check(self._context, entity, targetname) != ErrorConversationEnable.VALID:
                    continue
                if player_entity_name != targetname:
                    # 不是对你说的不能看见
                    continue
                #最后添加
                playerproxy.add_actor_message(action._actor_name, make_target_and_message(targetname, message))
############################################################################################################
    def broadcast_action_2_message(self, playerproxy: PlayerProxy, player_entity: Entity) -> None:
        player_entity_stage = self._context.safe_get_stage_entity(player_entity)
        entities = self._context.get_group(Matcher(BroadcastActionComponent)).entities
        for entity in entities:
                
            if entity == player_entity:
                #不能和自己对话
                continue
            
            his_stage_entity = self._context.safe_get_stage_entity(entity)
            if his_stage_entity != player_entity_stage:
                #场景不一样，不能看见
                continue

            broadcast_action_component: BroadcastActionComponent = entity.get(BroadcastActionComponent)
            action: AgentAction = broadcast_action_component.action
            single_val = action.join_values()
            playerproxy.add_actor_message(action._actor_name, f"""<@all>{single_val}""")
############################################################################################################
    def speak_action_2_message(self, playerproxy: PlayerProxy, player_entity: Entity) -> None:
        player_entity_stage = self._context.safe_get_stage_entity(player_entity)
        entities = self._context.get_group(Matcher(SpeakActionComponent)).entities
        for entity in entities:

            if entity == player_entity:
                #不能和自己对话
                continue
            
            his_stage_entity = self._context.safe_get_stage_entity(entity)
            if his_stage_entity != player_entity_stage:
                #场景不一样，不能看见
                continue

            speak_action_component: SpeakActionComponent = entity.get(SpeakActionComponent)
            action: AgentAction = speak_action_component.action
            target_and_message = action.target_and_message_values()
            for tp in target_and_message:
                targetname = tp[0]
                message = tp[1]
                if conversation_check(self._context, entity, targetname) != ErrorConversationEnable.VALID:
                    continue
                playerproxy.add_actor_message(action._actor_name, make_target_and_message(targetname, message))
############################################################################################################
    def mind_voice_action_2_message(self, playerproxy: PlayerProxy, player_entity: Entity) -> None:
        player_entity_stage = self._context.safe_get_stage_entity(player_entity)
        entities = self._context.get_group(Matcher(MindVoiceActionComponent)).entities
        for entity in entities:

            if entity == player_entity:
                #自己没有mindvoice
                continue
            
            his_stage_entity = self._context.safe_get_stage_entity(entity)
            if his_stage_entity != player_entity_stage:
                #只添加同一个场景的mindvoice
                continue

            mind_voice_action_component: MindVoiceActionComponent = entity.get(MindVoiceActionComponent)
            action: AgentAction = mind_voice_action_component.action
            single_value = action.join_values()
            playerproxy.add_actor_message(action._actor_name, f"""<心理活动>{single_value}""")
############################################################################################################
    def attack_action_2_message(self, playerproxy: PlayerProxy, player_entity: Entity) -> None:
        player_entity_stage = self._context.safe_get_stage_entity(player_entity)
        entities = self._context.get_group(Matcher(AttackActionComponent)).entities
        for entity in entities:

            if entity == player_entity:
                continue
            
            his_stage_entity = self._context.safe_get_stage_entity(entity)
            if his_stage_entity != player_entity_stage:
                continue

            attack_action_component: AttackActionComponent = entity.get(AttackActionComponent)
            action: AgentAction = attack_action_component.action
            if len(action._values) == 0:
                logger.error("attack_action_2_message error")
                continue

            targetname = action._values[0]
            playerproxy.add_actor_message(action._actor_name, f"""准备对{targetname}发起了攻击""")
############################################################################################################
    def go_to_action_2_message(self, playerproxy: PlayerProxy, player_entity: Entity) -> None:
        player_entity_stage = self._context.safe_get_stage_entity(player_entity)
        entities = self._context.get_group(Matcher(GoToActionComponent)).entities
        for entity in entities:

            if entity == player_entity:
                continue
            
            his_stage_entity = self._context.safe_get_stage_entity(entity)
            if his_stage_entity != player_entity_stage:
                continue

            go_to_action_component: GoToActionComponent = entity.get(GoToActionComponent)
            action: AgentAction = go_to_action_component.action
            if len(action._values) == 0:
                logger.error("go_to_action_2_message error")
                continue

            stagename = action._values[0]
            playerproxy.add_actor_message(action._actor_name, f"""准备去往{stagename}""")
############################################################################################################