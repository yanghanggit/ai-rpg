
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent
from components import SpeakActionComponent, NPCComponent, StageComponent
from actor_action import ActorAction
from extended_context import ExtendedContext
from agents.tools.print_in_color import Color
from prompt_maker import speak_action_prompt
   
####################################################################################################
class SpeakActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self):
        return {Matcher(SpeakActionComponent): GroupEvent.ADDED}

    def filter(self, entity: list[Entity]):
        return entity.has(SpeakActionComponent)

    def react(self, entities: list[Entity]):
        print("<<<<<<<<<<<<<  SpeakActionSystem  >>>>>>>>>>>>>>>>>")
        # 核心执行
        for entity in entities:
            self.handle(entity)  
        # 必须移除！！！
        for entity in entities:
            entity.remove(SpeakActionComponent)     
####################################################################################################
    def handle(self, entity: Entity) -> None:
        speakcomp = entity.get(SpeakActionComponent)
        action: ActorAction = speakcomp.action
        #debug
        # for value in action.values:
        #     what_to_said = f"{action.name}说:{value}"
        #     print(f"SpeakActionSystem debug: {what_to_said}")

        for value in action.values:
            tp = self.parsespeak(value)
            target = tp[0]
            message = tp[1]
            #print(f"SpeakActionSystem debug: {target}说:{message}")

            ##如果检查不过就能继续
            if not self.check_speak_enable(entity, target):
                continue
            ##拼接说话内容
            #saycontent = f"{action.name}对{target}对说:{message}"
            saycontent = speak_action_prompt(action.name, target, message, self.context)
            print(f"{Color.HEADER}{saycontent}{Color.ENDC}")
            ##添加场景事件，最后随着导演剧本走
            stagecomp = self.context.get_stagecomponent_by_uncertain_entity(entity)
            stagecomp.directorscripts.append(saycontent)
####################################################################################################
    def check_speak_enable(self, src: Entity, dstname: str) -> bool:

        npc_entity: Entity = self.context.getnpc(dstname)
        if npc_entity is None:
            print(f"没有找到名字为{dstname}的NPC")
            return False

        current_stage_comp: StageComponent = self.context.get_stagecomponent_by_uncertain_entity(src)  
        if current_stage_comp is None:
            print(f"没有找到{src}的StageComponent")
            return False  
        
        npccomp: NPCComponent = npc_entity.get(NPCComponent)
        if current_stage_comp.name != npccomp.current_stage:
            print(f"{src}不在{npccomp.current_stage}, {current_stage_comp.name}中")
            return False
        
        return True
####################################################################################################
    def parsespeak(self, content: str) -> tuple[str, str]:
        # 解析出说话者和说话内容
        target, message = content.split(">")
        target = target[1:]  # Remove the '@' symbol
        return target, message
       