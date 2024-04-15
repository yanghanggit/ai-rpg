
from entitas import ExecuteProcessor, Matcher, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.components import DeadActionComponent, NPCComponent, StageComponent
from auxiliary.prompt_maker import gen_npc_archive_prompt, npc_memory_before_death

# 战斗后处理，入股哦死了就死亡存档
class PostFightSystem(ExecuteProcessor):
############################################################################################################
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  PostFightActionSystem  >>>>>>>>>>>>>>>>>")
        # 如果死了先存档
        if self.context.savedata:
            self.save_dead()
########################################################################################################################################################################
    def save_dead(self) -> None:
         entities: set[Entity] = self.context.get_group(Matcher(DeadActionComponent)).entities
         for entity in entities:
            self.save_npc(entity)
########################################################################################################################################################################
    def save_npc(self, entity: Entity) -> None:
        agent_connect_system = self.context.agent_connect_system
        memory_system = self.context.memory_system
        if entity.has(NPCComponent):
            npccomp: NPCComponent = entity.get(NPCComponent)
            # 添加记忆
            mem_before_death = npc_memory_before_death(self.context)
            self.context.add_human_message_to_entity(entity, mem_before_death)
            # 推理死亡，并且进行存档
            archiveprompt = gen_npc_archive_prompt(self.context)
            archive = agent_connect_system.request(npccomp.name, archiveprompt)
            if archive is not None:
                # 存档!
                memory_system.overwritememory(npccomp.name, archive)
        elif entity.has(StageComponent):
            logger.error("PostFightSystem: 为什么场景死了？")
            raise Exception("DeadActionSystem: 把场景打死了？")
########################################################################################################################################################################

            

