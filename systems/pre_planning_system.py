
from entitas import ExecuteProcessor, Matcher, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.components import AutoPlanningComponent, StageComponent, NPCComponent, PlayerComponent
   
class PrePlanningSystem(ExecuteProcessor):
############################################################################################################
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  PrePlanningSystem  >>>>>>>>>>>>>>>>>")
        ## 选择比较费的策略。
        self.strategy2_all_stages_and_npcs_except_player_allow_auto_planning()

        ## 选择比较省的策略。
        # playerentities = self.context.get_group(Matcher(PlayerComponent)).entities
        # for playerentity in playerentities:
        #     self.strategy1_only_the_stage_where_player_is_located_and_the_npcs_in_it_allowed_make_plans(playerentity)
        
############################################################################################################
    def strategy1_only_the_stage_where_player_is_located_and_the_npcs_in_it_allowed_make_plans(self, playerentity: Entity) -> None:

        if playerentity is None:
            raise ValueError("playerentity is None")
        
        if not playerentity.has(PlayerComponent):
            raise ValueError("playerentity must have PlayerComponent")
            
        context = self.context
        stageentity = context.get_stage_entity_by_uncertain_entity(playerentity)
        if stageentity is None:
            logger.error("stage is None, 所以全世界都不能做planning")
            return
        
        ##player所在场景可以规划！
        stagecomp: StageComponent = stageentity.get(StageComponent)
        if not stageentity.has(AutoPlanningComponent):
            stageentity.add(AutoPlanningComponent, stagecomp.name)
        else:
            raise ValueError(f"stage {stagecomp.name} has AutoPlanningComponent, so do not add again")
        
        ###player
        players_npc_comp: NPCComponent = playerentity.get(NPCComponent)
        logger.debug(f"playerentity {players_npc_comp.name} is in stage {stagecomp.name}, begin to add AutoPlanningComponent to stage and npcs in this stage")
        ###player 不允许做规划
        if playerentity.has(AutoPlanningComponent):
            playerentity.remove(AutoPlanningComponent)
        
        ###player所在场景的npcs可以规划
        npcsentities = context.npcs_in_this_stage(stagecomp.name)
        for npc in npcsentities:
            if npc.has(PlayerComponent):
                ## 前面略过了，这里就不可以执行
                continue
            npccomp: NPCComponent = npc.get(NPCComponent)
            if not npc.has(AutoPlanningComponent):
                npc.add(AutoPlanningComponent, npccomp.name)
            else:
                raise ValueError(f"npc {npccomp.name} has AutoPlanningComponent, so do not add again")
############################################################################################################
    def strategy2_all_stages_and_npcs_except_player_allow_auto_planning(self) -> None:
        context = self.context
        stages = context.get_group(Matcher(StageComponent)).entities
        for stage in stages:
            stagecomp: StageComponent = stage.get(StageComponent)
            if not stage.has(AutoPlanningComponent):
                stage.add(AutoPlanningComponent, stagecomp.name)
            else:
                raise ValueError(f"stage {stagecomp.name} has AutoPlanningComponent, so do not add again")
        
        npcs = context.get_group(Matcher(NPCComponent)).entities
        for npc in npcs:
            if npc.has(PlayerComponent):
                ## player 就跳过
                continue
            npccomp: NPCComponent = npc.get(NPCComponent)
            if not npc.has(AutoPlanningComponent):
                npc.add(AutoPlanningComponent, npccomp.name)
            else:
                raise ValueError(f"npc {npccomp.name} has AutoPlanningComponent, so do not add again")
############################################################################################################

