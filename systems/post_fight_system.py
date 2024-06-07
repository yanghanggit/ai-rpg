
from entitas import ExecuteProcessor, Matcher, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.components import DeadActionComponent, ACTOR_INTERACTIVE_ACTIONS_REGISTER, ActorComponent
from auxiliary.cn_builtin_prompt import gen_npc_archive_prompt, died_in_fight_prompt

# 战斗后处理，入股哦死了就死亡存档
class PostFightSystem(ExecuteProcessor):
############################################################################################################
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    def execute(self) -> None:
        # 移除后续动作
        self.remove_npc_interactive_actions()
        #可以存档
        if self.context.save_data_enable:
            self.savedead()
########################################################################################################################################################################
    def savedead(self) -> None:
         entities: set[Entity] = self.context.get_group(Matcher(DeadActionComponent)).entities
         for entity in entities:
            self.savenpc(entity)
########################################################################################################################################################################
    def savenpc(self, entity: Entity) -> None:
        agent_connect_system = self.context.agent_connect_system
        memory_system = self.context.kick_off_memory_system
        safename = self.context.safe_get_entity_name(entity)
        if safename == "":
            return

        # 
        newmsg = died_in_fight_prompt(self.context)
        self.context.safe_add_human_message_to_entity(entity, newmsg)

        # 推理死亡，并且进行存档
        archiveprompt = gen_npc_archive_prompt(self.context)
        archive = agent_connect_system.agent_request(safename, archiveprompt)
        if archive is not None:
            memory_system.set_and_write(safename, archive)    # 存档!    
        else:
            logger.error(f"存档失败:{safename}")    
########################################################################################################################################################################
    def remove_npc_interactive_actions(self) -> None:
        npcentities:set[Entity] = self.context.get_group(Matcher(all_of = [ActorComponent, DeadActionComponent], any_of = ACTOR_INTERACTIVE_ACTIONS_REGISTER)).entities.copy()
        for entity in npcentities:
            for actionsclass in ACTOR_INTERACTIVE_ACTIONS_REGISTER:
                if entity.has(actionsclass):
                    entity.remove(actionsclass)
########################################################################################################################################################################

            

