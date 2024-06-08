from entitas import ExecuteProcessor, Entity, Matcher #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.player_proxy import PlayerProxy, get_player_proxy, TEST_TERMINAL_NAME, determine_player_input_mode, PLAYER_INPUT_MODE
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import MindVoiceActionComponent, WhisperActionComponent, SpeakActionComponent, \
    BroadcastActionComponent, EnviroNarrateActionComponent, \
    AttackActionComponent, GoToActionComponent
from auxiliary.actor_plan_and_action import ActorAction
from typing import Optional, override
from loguru import logger
from auxiliary.target_and_message_format_handle import parse_target_and_message, conversation_check, ErrorConversationEnable

class UpdateClientMessageSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    @override
    def execute(self) -> None:

        input_mode = determine_player_input_mode(self.context.user_ips)
        
        if input_mode == PLAYER_INPUT_MODE.WEB_HTTP_REQUEST:
        
            for user_ip in self.context.user_ips:
                playername = str(user_ip)
                playerproxy = get_player_proxy(playername)
                player_npc_entity = self.context.get_player_entity(playername)
                if player_npc_entity is None or playerproxy is None:
                    continue
                self._add_message_to_player_proxy_(playerproxy, player_npc_entity)
        
        elif input_mode == PLAYER_INPUT_MODE.TERMINAL:
        
            playerproxy = get_player_proxy(TEST_TERMINAL_NAME)
            player_npc_entity = self.context.get_player_entity(TEST_TERMINAL_NAME)
            if player_npc_entity is None or playerproxy is None:
                    return
            self._add_message_to_player_proxy_(playerproxy, player_npc_entity)

        else:
            logger.error("未知的输入模式!!!!!")         
############################################################################################################
    def _add_message_to_player_proxy_(self, playerproxy: PlayerProxy, player_npc_entity: Entity) -> None:
        self.stage_enviro_narrate_action_2_message(playerproxy, player_npc_entity)
        self.mind_voice_action_2_message(playerproxy, player_npc_entity)
        self.whisper_action_2_message(playerproxy, player_npc_entity)
        self.broadcast_action_2_message(playerproxy, player_npc_entity)
        self.speak_action_2_message(playerproxy, player_npc_entity)
        self.attack_action_2_message(playerproxy, player_npc_entity)
        self.leave_for_action_2_message(playerproxy, player_npc_entity)
############################################################################################################
    def stage_enviro_narrate_action_2_message(self, playerproxy: PlayerProxy, player_npc_entity: Entity) -> None:
        stage = self.context.safe_get_stage_entity(player_npc_entity)
        if stage is None:
            return
        if not stage.has(EnviroNarrateActionComponent):
            return
        envirocomp: EnviroNarrateActionComponent = stage.get(EnviroNarrateActionComponent)
        action: ActorAction = envirocomp.action
        if len(action.values) == 0:
            return
        message = action.single_value()
        playerproxy.add_stage_message(action.name, message)
############################################################################################################
    def whisper_action_2_message(self, playerproxy: PlayerProxy, player_npc_entity: Entity) -> None:
        player_npc_entity_stage = self.context.safe_get_stage_entity(player_npc_entity)
        player_npc_entity_name = self.context.safe_get_entity_name(player_npc_entity) 
        entities = self.context.get_group(Matcher(WhisperActionComponent)).entities
        for entity in entities:

            if entity == player_npc_entity:
                #不能和自己对话
                continue
            
            his_stage_entity = self.context.safe_get_stage_entity(entity)
            if his_stage_entity != player_npc_entity_stage:
                #场景不一样，不能看见
                continue

            whisper_action_component: WhisperActionComponent = entity.get(WhisperActionComponent)
            action: ActorAction = whisper_action_component.action
            for value in action.values:
                parse = parse_target_and_message(value)
                targetname: Optional[str] = parse[0]
                message: Optional[str] = parse[1]
                if targetname is None or message is None:
                    continue
                if conversation_check(self.context, entity, targetname) != ErrorConversationEnable.VALID:
                    continue
                if player_npc_entity_name != targetname:
                    # 不是对你说的不能看见
                    continue

                #最后添加
                playerproxy.add_actor_message(action.name, value)
############################################################################################################
    def broadcast_action_2_message(self, playerproxy: PlayerProxy, player_npc_entity: Entity) -> None:
        player_npc_entity_stage = self.context.safe_get_stage_entity(player_npc_entity)
        entities = self.context.get_group(Matcher(BroadcastActionComponent)).entities
        for entity in entities:
                
            if entity == player_npc_entity:
                #不能和自己对话
                continue
            
            his_stage_entity = self.context.safe_get_stage_entity(entity)
            if his_stage_entity != player_npc_entity_stage:
                #场景不一样，不能看见
                continue

            broadcast_action_component: BroadcastActionComponent = entity.get(BroadcastActionComponent)
            action: ActorAction = broadcast_action_component.action
            single_val = action.single_value()
            playerproxy.add_actor_message(action.name, f"""<@all>{single_val}""") #todo
############################################################################################################
    def speak_action_2_message(self, playerproxy: PlayerProxy, player_npc_entity: Entity) -> None:
        player_npc_entity_stage = self.context.safe_get_stage_entity(player_npc_entity)
        entities = self.context.get_group(Matcher(SpeakActionComponent)).entities
        for entity in entities:

            if entity == player_npc_entity:
                #不能和自己对话
                continue
            
            his_stage_entity = self.context.safe_get_stage_entity(entity)
            if his_stage_entity != player_npc_entity_stage:
                #场景不一样，不能看见
                continue

            speak_action_component: SpeakActionComponent = entity.get(SpeakActionComponent)
            action: ActorAction = speak_action_component.action
            for value in action.values:
                parse = parse_target_and_message(value)
                targetname: Optional[str] = parse[0]
                message: Optional[str] = parse[1]
                if targetname is None or message is None:
                    continue
                if conversation_check(self.context, entity, targetname) != ErrorConversationEnable.VALID:
                    continue
      
                playerproxy.add_actor_message(action.name, value)
############################################################################################################
    def mind_voice_action_2_message(self, playerproxy: PlayerProxy, player_npc_entity: Entity) -> None:
        player_npc_entity_stage = self.context.safe_get_stage_entity(player_npc_entity)
        entities = self.context.get_group(Matcher(MindVoiceActionComponent)).entities
        for entity in entities:

            if entity == player_npc_entity:
                #自己没有mindvoice
                continue
            
            his_stage_entity = self.context.safe_get_stage_entity(entity)
            if his_stage_entity != player_npc_entity_stage:
                #只添加同一个场景的mindvoice
                continue

            mind_voice_action_component: MindVoiceActionComponent = entity.get(MindVoiceActionComponent)
            action: ActorAction = mind_voice_action_component.action
            single_value = action.single_value()
            playerproxy.add_actor_message(action.name, f"""<心理活动>{single_value}""") #todo
############################################################################################################
    def attack_action_2_message(self, playerproxy: PlayerProxy, player_npc_entity: Entity) -> None:
        player_npc_entity_stage = self.context.safe_get_stage_entity(player_npc_entity)
        entities = self.context.get_group(Matcher(AttackActionComponent)).entities
        for entity in entities:

            if entity == player_npc_entity:
                continue
            
            his_stage_entity = self.context.safe_get_stage_entity(entity)
            if his_stage_entity != player_npc_entity_stage:
                continue

            attack_action_component: AttackActionComponent = entity.get(AttackActionComponent)
            action: ActorAction = attack_action_component.action
            if len(action.values) == 0:
                logger.error("attack_action_2_message error")
                continue

            targetname = action.values[0]
            playerproxy.add_actor_message(action.name, f"""准备对{targetname}发起了攻击""") #todo
############################################################################################################
    def leave_for_action_2_message(self, playerproxy: PlayerProxy, player_npc_entity: Entity) -> None:
        player_npc_entity_stage = self.context.safe_get_stage_entity(player_npc_entity)
        entities = self.context.get_group(Matcher(GoToActionComponent)).entities
        for entity in entities:

            if entity == player_npc_entity:
                continue
            
            his_stage_entity = self.context.safe_get_stage_entity(entity)
            if his_stage_entity != player_npc_entity_stage:
                continue

            leave_for_component: GoToActionComponent = entity.get(GoToActionComponent)
            action: ActorAction = leave_for_component.action
            if len(action.values) == 0:
                logger.error("leave_for_action_2_message error")
                continue

            stagename = action.values[0]
            playerproxy.add_actor_message(action.name, f"""准备去往{stagename}""") #todo
############################################################################################################