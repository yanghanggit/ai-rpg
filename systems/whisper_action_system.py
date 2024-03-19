
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import WhisperActionComponent, StageComponent, NPCComponent
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from agents.tools.print_in_color import Color
from auxiliary.prompt_maker import whisper_action_prompt
from typing import Optional

class WhisperActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(WhisperActionComponent): GroupEvent.ADDED}

    def filter(self, entity: Entity) -> bool:
        return entity.has(WhisperActionComponent)

    def react(self, entities: list[Entity]) -> None:
        print("<<<<<<<<<<<<<  WhisperActionSystem  >>>>>>>>>>>>>>>>>")

        for entity in entities:
            self.handle(entity)  # 核心处理

        for entity in entities:
            entity.remove(WhisperActionComponent)  # 必须移除！！！       

    def handle(self, entity_stage_or_npc: Entity) -> None:

        whispercomp: WhisperActionComponent = entity_stage_or_npc.get(WhisperActionComponent)
        stagecomp: Optional[StageComponent] = self.context.get_stagecomponent_by_uncertain_entity(entity_stage_or_npc) 
        if stagecomp is None or whispercomp is None:
            print(f"WhisperActionSystem: stagecomp or whispercomp is None!")
            return

        action: ActorAction = whispercomp.action
        values: list[str] = action.values
        if len(values) < 2:
            print(f"WhisperActionSystem: values length < 2")
            return

        target_name: str = values[0]
        target_entity = self.context.getnpc(target_name)
        if target_entity is None:
            print(f"The person you want to whisper does not exist, or is not an NPC!")
            return
        
        target_npc_comp: NPCComponent = target_entity.get(NPCComponent)
        if target_npc_comp.current_stage != stagecomp.name:
            print(f"Not in this stage!")
            return
        
        #组装新的记忆。但是不要加到场景事件里
        content: str = values[1]
        new_memory = whisper_action_prompt(action.name, target_name, content, self.context)
        print(f"{Color.HEADER}{new_memory}{Color.ENDC}")

        #整理代码，加到记忆里
        self.context.add_agent_memory(entity_stage_or_npc, new_memory)
        self.context.add_agent_memory(target_entity, new_memory)

            
        
                