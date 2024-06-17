from typing import override, Set
from entitas import ExecuteProcessor, Matcher, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
#from loguru import logger
from auxiliary.components import DeadActionComponent, ACTOR_INTERACTIVE_ACTIONS_REGISTER, ActorComponent
#from auxiliary.cn_builtin_prompt import gen_actor_archive_prompt, died_in_fight_prompt

# 战斗后处理，入股哦死了就死亡存档
class PostFightSystem(ExecuteProcessor):
############################################################################################################
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    @override
    def execute(self) -> None:
        # 移除后续动作
        self.remove_actor_interactive_actions()
        #可以存档
        if self.context.save_data_enable:
            pass
########################################################################################################################################################################
    def remove_actor_interactive_actions(self) -> None:
        actor_entities:Set[Entity] = self.context.get_group(Matcher(all_of = [ActorComponent, DeadActionComponent], any_of = ACTOR_INTERACTIVE_ACTIONS_REGISTER)).entities.copy()
        for entity in actor_entities:
            for actionsclass in ACTOR_INTERACTIVE_ACTIONS_REGISTER:
                if entity.has(actionsclass):
                    entity.remove(actionsclass)
########################################################################################################################################################################

            

