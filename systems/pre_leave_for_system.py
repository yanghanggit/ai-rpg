from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import (LeaveForActionComponent, 
                        NPCComponent, 
                        StageEntryConditionComponent,
                        StageExitConditionComponent,
                        PrisonBreakActionComponent)
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from enum import Enum

# 错误代码
class ErrorCheckTargetStage(Enum):
    VALID = 0
    ACTION_PARAMETER_ERROR = 1
    STAGE_CANNOT_BE_FOUND = 2
    ALREADY_IN_THIS_STAGE = 3
    DONT_KNOW_STAGE = 4

# 错误代码
class ErrorCheckExitStageConditions(Enum):
    VALID = 0
    NO_EXIT_CONDITIONS_MATCH = 1

# 错误代码
class ErrorCheckEnterStageConditions(Enum):
    VALID = 0
    NO_ENTRY_CONDITIONS_MATCH = 1

###############################################################################################################################################
class PreLeaveForSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
###############################################################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(LeaveForActionComponent): GroupEvent.ADDED}
###############################################################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(LeaveForActionComponent) and entity.has(NPCComponent)
###############################################################################################################################################
    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  PreLeaveForSystem  >>>>>>>>>>>>>>>>>")
        for entity in entities:
            if not self.check_current_stage_valid(entity):
                #logger.error("场景有问题")
                continue

            error_check_target_stage = self.check_target_stage_valid(entity)
            if error_check_target_stage != ErrorCheckTargetStage.VALID:
                # 要去往的场景有问题
                self.handle_target_stage_invalid(entity, error_check_target_stage)
                continue

            exit_error = self.check_exit_stage_conditions(entity)
            if exit_error != ErrorCheckExitStageConditions.VALID:
                # 离开限制
                self.handle_exit_stage_conditions_invalid(entity, exit_error)
                continue
            
            enter_error = self.check_enter_stage_conditions(entity)
            if enter_error != ErrorCheckEnterStageConditions.VALID:
                # 进入限制
                self.handle_enter_stage_conditions_invalid(entity, enter_error)
                continue
###############################################################################################################################################
    def check_current_stage_valid(self, entity: Entity) -> bool:
        npccomp: NPCComponent = entity.get(NPCComponent)
        current_stage: str = npccomp.current_stage
        stageentity = self.context.getstage(current_stage)
        if stageentity is None:
            logger.error(f"{current_stage},场景有问题")
            return False
        return True
###############################################################################################################################################
    def check_target_stage_valid(self, entity: Entity) -> ErrorCheckTargetStage:
        #
        file_system = self.context.file_system
        npccomp: NPCComponent = entity.get(NPCComponent)
        #
        leavecomp: LeaveForActionComponent = entity.get(LeaveForActionComponent)
        action: ActorAction = leavecomp.action
        if len(action.values) == 0:
           logger.error("参数错误")
           return ErrorCheckTargetStage.ACTION_PARAMETER_ERROR
        #
        targetstagename = action.values[0]
        targetstage = self.context.getstage(targetstagename)
        if targetstage is None:
            logger.error(f"找不到这个场景: {targetstagename}")
            return ErrorCheckTargetStage.STAGE_CANNOT_BE_FOUND
        #
        if targetstagename == npccomp.current_stage:
            logger.error(f"{npccomp.name} 已经在这个场景: {targetstagename}")
            return ErrorCheckTargetStage.ALREADY_IN_THIS_STAGE
        
        #
        knownstagefile = file_system.get_known_stage_file(npccomp.name, targetstagename)
        if knownstagefile is None:
            # 我不认识该怎么办？
            if entity.has(PrisonBreakActionComponent):
                logger.info(f"{npccomp.name} 逃狱了，但不知道这个场景: {targetstagename}。没关系只要目标场景是合理的，系统可以放过去")
            else:
                logger.error(f"{npccomp.name} 不知道这个场景: {targetstagename}，而且不是逃狱。就是不能去")
                return ErrorCheckTargetStage.DONT_KNOW_STAGE
        #
        return ErrorCheckTargetStage.VALID
###############################################################################################################################################
    def handle_target_stage_invalid(self, entity: Entity, error: ErrorCheckTargetStage) -> None:
        entity.remove(LeaveForActionComponent) # 停止离开！
        pass
###############################################################################################################################################
    def check_exit_stage_conditions(self, entity: Entity) -> ErrorCheckExitStageConditions:
        #
        file_system = self.context.file_system
        npccomp: NPCComponent = entity.get(NPCComponent)
        current_stage: str = npccomp.current_stage
        stageentity = self.context.getstage(current_stage)
        assert stageentity is not None
        # 没有离开条件
        if not stageentity.has(StageExitConditionComponent):
            return ErrorCheckExitStageConditions.VALID
        
        #有检查条件
        exit_condition_comp: StageExitConditionComponent = stageentity.get(StageExitConditionComponent)
        conditions = exit_condition_comp.conditions
        if len(conditions) == 0:
            return ErrorCheckExitStageConditions.VALID
        
        ### 检查条件
        for cond in conditions:
            if not file_system.has_prop_file(npccomp.name, cond):
                # 没有这个道具
                return ErrorCheckExitStageConditions.NO_EXIT_CONDITIONS_MATCH
        ##
        return ErrorCheckExitStageConditions.VALID
###############################################################################################################################################
    def handle_exit_stage_conditions_invalid(self, entity: Entity, error: ErrorCheckExitStageConditions) -> None:
        entity.remove(LeaveForActionComponent) # 停止离开！
        pass
###############################################################################################################################################
    def check_enter_stage_conditions(self, entity: Entity) -> ErrorCheckEnterStageConditions:
        #
        file_system = self.context.file_system
        npccomp: NPCComponent = entity.get(NPCComponent)

        leavecomp: LeaveForActionComponent = entity.get(LeaveForActionComponent)
        action: ActorAction = leavecomp.action
        
        targetstagename = action.values[0]
        targetstage = self.context.getstage(targetstagename)
        assert targetstage is not None
        if not targetstage.has(StageEntryConditionComponent):
            return ErrorCheckEnterStageConditions.VALID
        
        #有检查条件
        entry_condition_comp: StageEntryConditionComponent = targetstage.get(StageEntryConditionComponent)
        conditions = entry_condition_comp.conditions
        if len(conditions) == 0:
            return ErrorCheckEnterStageConditions.VALID
        
        ### 检查条件
        for cond in conditions:
            if file_system.has_prop_file(npccomp.name, cond):
                return ErrorCheckEnterStageConditions.VALID
        
        # 没有这个道具
        return ErrorCheckEnterStageConditions.NO_ENTRY_CONDITIONS_MATCH
###############################################################################################################################################
    def handle_enter_stage_conditions_invalid(self, entity: Entity, error: ErrorCheckEnterStageConditions) -> None:
        entity.remove(LeaveForActionComponent) # 停止离开！
        pass
###############################################################################################################################################    
