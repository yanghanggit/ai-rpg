from entitas import ExecuteProcessor, Entity, Matcher #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.player_proxy import PlayerProxy, get_player_proxy, TEST_PLAYER_NAME
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import MindVoiceActionComponent, WhisperActionComponent, SpeakActionComponent, BroadcastActionComponent, EnviroNarrateActionComponent
from auxiliary.actor_action import ActorAction
from typing import Optional
from auxiliary.dialogue_rule import parse_target_and_message, dialogue_enable, ErrorDialogueEnable

class TestPlayerUpdateClientMessageSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    def execute(self) -> None:
        playername = TEST_PLAYER_NAME
        playerproxy = get_player_proxy(playername)
        player_npc_entity = self.context.getplayer(playername)
        if player_npc_entity is None or playerproxy is None:
            return
        
        self.stage_enviro_narrate_action_2_message(playerproxy, player_npc_entity)
        self.mind_voice_action_2_message(playerproxy, player_npc_entity)
        self.whisper_action_2_message(playerproxy, player_npc_entity)
        self.broadcast_action_2_message(playerproxy, player_npc_entity)
        self.speak_action_2_message(playerproxy, player_npc_entity)
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
        playerproxy.add_npc_message(action.name, message)
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
                if dialogue_enable(self.context, entity, targetname) != ErrorDialogueEnable.VALID:
                    continue
                if player_npc_entity_name != targetname:
                    # 不是对你说的不能看见
                    continue

                #最后添加
                playerproxy.add_npc_message(action.name, value)
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
            playerproxy.add_npc_message(action.name, f"""<@all>{single_val}""")
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
                if dialogue_enable(self.context, entity, targetname) != ErrorDialogueEnable.VALID:
                    continue
      
                playerproxy.add_npc_message(action.name, value)
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
            playerproxy.add_npc_message(action.name, f"""<心理活动>{single_value}""")
############################################################################################################