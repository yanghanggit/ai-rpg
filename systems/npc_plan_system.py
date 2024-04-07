from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from auxiliary.components import (NPCComponent, 
                        FightActionComponent, 
                        SpeakActionComponent, 
                        LeaveForActionComponent, 
                        TagActionComponent, 
                        MindVoiceActionComponent,
                        BroadcastActionComponent, 
                        WhisperActionComponent,
                        SearchActionComponent,
                        PlayerComponent)
from auxiliary.actor_action import ActorPlan
from auxiliary.prompt_maker import npc_plan_prompt
from auxiliary.extended_context import ExtendedContext
from loguru import logger

class NPCPlanSystem(ExecuteProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        self.context = context

    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  NPCPlanSystem  >>>>>>>>>>>>>>>>>")

        entities = self.context.get_group(Matcher(NPCComponent)).entities
        for entity in entities:

            if entity.has(PlayerComponent):
                logger.info(f"{entity.get(NPCComponent).name}正在被玩家控制，不执行自动计划。\n")
                continue

            #开始处理NPC的行为计划
            self.handle(entity)

    def handle(self, entity: Entity) -> None:

        prompt = npc_plan_prompt(entity, self.context)
        agent_connect_system = self.context.agent_connect_system
        npccomp: NPCComponent = entity.get(NPCComponent)

        try:
            response = agent_connect_system.request(npccomp.name, prompt)
            if response is None:
                logger.warning("Agent request is None.如果不是默认Player可能需要检查配置。")
                return
            
            npcplanning = ActorPlan(npccomp.name, response)
            for action in npcplanning.actions:
                match action.actionname:
                    case "FightActionComponent":
                        if not entity.has(FightActionComponent):
                            entity.add(FightActionComponent, action)

                    case "LeaveForActionComponent":
                        if not entity.has(LeaveForActionComponent):
                            entity.add(LeaveForActionComponent, action)

                    case "SpeakActionComponent":
                        if not entity.has(SpeakActionComponent):
                            entity.add(SpeakActionComponent, action)
                    
                    case "TagActionComponent":
                        if not entity.has(TagActionComponent):
                            entity.add(TagActionComponent, action)
                    
                    case "RememberActionComponent":
                        pass

                    case "MindVoiceActionComponent":
                        if not entity.has(MindVoiceActionComponent):
                            entity.add(MindVoiceActionComponent, action)

                    case "BroadcastActionComponent":
                        if not entity.has(BroadcastActionComponent):
                            entity.add(BroadcastActionComponent, action)

                    case "WhisperActionComponent":
                        if not entity.has(WhisperActionComponent):
                            entity.add(WhisperActionComponent, action)

                    case "SearchActionComponent":
                        if not entity.has(SearchActionComponent):
                            entity.add(SearchActionComponent, action)
                    case _:
                        logger.warning(f" {action.actionname}, Unknown action name")
                        continue

        except Exception as e:
            logger.exception(f"NPCPlanSystem: {e}")  
            return
        return
