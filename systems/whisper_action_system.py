from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import WhisperActionComponent
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from auxiliary.print_in_color import Color
from auxiliary.prompt_maker import whisper_action_prompt
from typing import Optional
from loguru import logger
from auxiliary.dialogue_rule import parse_target_and_message, check_speak_enable

####################################################################################################
class WhisperActionSystem(ReactiveProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
####################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(WhisperActionComponent): GroupEvent.ADDED}
####################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(WhisperActionComponent)
####################################################################################################
    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  WhisperActionSystem  >>>>>>>>>>>>>>>>>")
        for entity in entities:
            self.whisper(entity)  # 核心处理 
####################################################################################################
    def whisper(self, entity: Entity) -> None:

        whispercomp: WhisperActionComponent = entity.get(WhisperActionComponent)
        action: ActorAction = whispercomp.action

        for value in action.values:
            target_message_pair = parse_target_and_message(value)
            targetname: Optional[str] = target_message_pair[0]
            message: Optional[str] = target_message_pair[1]
            if targetname is None or message is None:
                logger.warning(f"WhisperActionSystem: targetname or message is None.")
                continue

            if not check_speak_enable(self.context, entity, targetname):
                # 如果检查不过就能继续
                continue

            whispertoentity: Optional[Entity] = self.context.getnpc(targetname)
            if whispertoentity is None:
                # 这里基本是可能发生，如果出了问题就是check_speak_enable放过去了。
                raise ValueError(f"WhisperActionSystem: whispertoentity {targetname} is None!")
                continue
            whispercontent = whisper_action_prompt(action.name, targetname, message, self.context)
            #临时
            logger.info(f"{Color.HEADER}{whispercontent}{Color.ENDC}")
            #低语的双方添加记忆即可，别人不知道
            self.context.safe_add_human_message_to_entity(entity, whispercontent)
            self.context.safe_add_human_message_to_entity(whispertoentity, whispercontent)
####################################################################################################
        
            
        
                