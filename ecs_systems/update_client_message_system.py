from entitas import ExecuteProcessor, Entity, Matcher #type: ignore
from my_entitas.extended_context import ExtendedContext
from player.player_proxy import PlayerProxy, get_player_proxy, determine_player_input_mode, PLAYER_INPUT_MODE
from dev_config import TEST_TERMINAL_NAME
from my_entitas.extended_context import ExtendedContext
from ecs_systems.components import MindVoiceActionComponent, WhisperActionComponent, SpeakActionComponent, \
    BroadcastActionComponent, EnviroNarrateActionComponent, \
    AttackActionComponent, GoToActionComponent
from my_agent.agent_action import AgentAction
from typing import override
from loguru import logger
from gameplay_checks.conversation_check import conversation_check, ErrorConversationEnable
from my_format_string.target_and_message_format_string import make_target_and_message
from rpg_game.rpg_game import RPGGame 

class UpdateClientMessageSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext, rpggame: RPGGame) -> None:
        self.context: ExtendedContext = context
        self.rpggame: RPGGame = rpggame
############################################################################################################
    @override
    def execute(self) -> None:

        # todo
        # 临时的设置，通过IP地址来判断是不是测试的客户端
        user_ips = self.rpggame.user_ips    
        # 判断，user_ips 与 self.context.user_ips 是否一致：元素的顺序和个数，和元素的内容
        # if user_ips != self.context.user_ips:
        #     assert False, "user_ips 与 self.context.user_ips 不一致"

        input_mode = determine_player_input_mode(user_ips)
        
        if input_mode == PLAYER_INPUT_MODE.WEB_HTTP_REQUEST:
        
            for user_ip in user_ips:
                playername = str(user_ip)
                playerproxy = get_player_proxy(playername)
                player_entity = self.context.get_player_entity(playername)
                if player_entity is None or playerproxy is None:
                    continue
                self._add_message_to_player_proxy_(playerproxy, player_entity)
        
        elif input_mode == PLAYER_INPUT_MODE.TERMINAL:
        
            playerproxy = get_player_proxy(TEST_TERMINAL_NAME)
            player_entity = self.context.get_player_entity(TEST_TERMINAL_NAME)
            if player_entity is None or playerproxy is None:
                    return
            self._add_message_to_player_proxy_(playerproxy, player_entity)

        else:
            logger.error("未知的输入模式!!!!!")         
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
        stage = self.context.safe_get_stage_entity(player_entity)
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
        player_entity_stage = self.context.safe_get_stage_entity(player_entity)
        player_entity_name = self.context.safe_get_entity_name(player_entity) 
        entities = self.context.get_group(Matcher(WhisperActionComponent)).entities
        for entity in entities:

            if entity == player_entity:
                #不能和自己对话
                continue
            
            his_stage_entity = self.context.safe_get_stage_entity(entity)
            if his_stage_entity != player_entity_stage:
                #场景不一样，不能看见
                continue

            whisper_action_component: WhisperActionComponent = entity.get(WhisperActionComponent)
            action: AgentAction = whisper_action_component.action
            target_and_message = action.target_and_message_values()
            for tp in target_and_message:
                targetname = tp[0]
                message = tp[1]
                if conversation_check(self.context, entity, targetname) != ErrorConversationEnable.VALID:
                    continue
                if player_entity_name != targetname:
                    # 不是对你说的不能看见
                    continue
                #最后添加
                playerproxy.add_actor_message(action._actor_name, make_target_and_message(targetname, message))
############################################################################################################
    def broadcast_action_2_message(self, playerproxy: PlayerProxy, player_entity: Entity) -> None:
        player_entity_stage = self.context.safe_get_stage_entity(player_entity)
        entities = self.context.get_group(Matcher(BroadcastActionComponent)).entities
        for entity in entities:
                
            if entity == player_entity:
                #不能和自己对话
                continue
            
            his_stage_entity = self.context.safe_get_stage_entity(entity)
            if his_stage_entity != player_entity_stage:
                #场景不一样，不能看见
                continue

            broadcast_action_component: BroadcastActionComponent = entity.get(BroadcastActionComponent)
            action: AgentAction = broadcast_action_component.action
            single_val = action.join_values()
            playerproxy.add_actor_message(action._actor_name, f"""<@all>{single_val}""") #todo
############################################################################################################
    def speak_action_2_message(self, playerproxy: PlayerProxy, player_entity: Entity) -> None:
        player_entity_stage = self.context.safe_get_stage_entity(player_entity)
        entities = self.context.get_group(Matcher(SpeakActionComponent)).entities
        for entity in entities:

            if entity == player_entity:
                #不能和自己对话
                continue
            
            his_stage_entity = self.context.safe_get_stage_entity(entity)
            if his_stage_entity != player_entity_stage:
                #场景不一样，不能看见
                continue

            speak_action_component: SpeakActionComponent = entity.get(SpeakActionComponent)
            action: AgentAction = speak_action_component.action
            target_and_message = action.target_and_message_values()
            for tp in target_and_message:
                targetname = tp[0]
                message = tp[1]
                if conversation_check(self.context, entity, targetname) != ErrorConversationEnable.VALID:
                    continue
                playerproxy.add_actor_message(action._actor_name, make_target_and_message(targetname, message))
############################################################################################################
    def mind_voice_action_2_message(self, playerproxy: PlayerProxy, player_entity: Entity) -> None:
        player_entity_stage = self.context.safe_get_stage_entity(player_entity)
        entities = self.context.get_group(Matcher(MindVoiceActionComponent)).entities
        for entity in entities:

            if entity == player_entity:
                #自己没有mindvoice
                continue
            
            his_stage_entity = self.context.safe_get_stage_entity(entity)
            if his_stage_entity != player_entity_stage:
                #只添加同一个场景的mindvoice
                continue

            mind_voice_action_component: MindVoiceActionComponent = entity.get(MindVoiceActionComponent)
            action: AgentAction = mind_voice_action_component.action
            single_value = action.join_values()
            playerproxy.add_actor_message(action._actor_name, f"""<心理活动>{single_value}""") #todo
############################################################################################################
    def attack_action_2_message(self, playerproxy: PlayerProxy, player_entity: Entity) -> None:
        player_entity_stage = self.context.safe_get_stage_entity(player_entity)
        entities = self.context.get_group(Matcher(AttackActionComponent)).entities
        for entity in entities:

            if entity == player_entity:
                continue
            
            his_stage_entity = self.context.safe_get_stage_entity(entity)
            if his_stage_entity != player_entity_stage:
                continue

            attack_action_component: AttackActionComponent = entity.get(AttackActionComponent)
            action: AgentAction = attack_action_component.action
            if len(action._values) == 0:
                logger.error("attack_action_2_message error")
                continue

            targetname = action._values[0]
            playerproxy.add_actor_message(action._actor_name, f"""准备对{targetname}发起了攻击""") #todo
############################################################################################################
    def go_to_action_2_message(self, playerproxy: PlayerProxy, player_entity: Entity) -> None:
        player_entity_stage = self.context.safe_get_stage_entity(player_entity)
        entities = self.context.get_group(Matcher(GoToActionComponent)).entities
        for entity in entities:

            if entity == player_entity:
                continue
            
            his_stage_entity = self.context.safe_get_stage_entity(entity)
            if his_stage_entity != player_entity_stage:
                continue

            go_to_action_component: GoToActionComponent = entity.get(GoToActionComponent)
            action: AgentAction = go_to_action_component.action
            if len(action._values) == 0:
                logger.error("go_to_action_2_message error")
                continue

            stagename = action._values[0]
            playerproxy.add_actor_message(action._actor_name, f"""准备去往{stagename}""") #todo
############################################################################################################