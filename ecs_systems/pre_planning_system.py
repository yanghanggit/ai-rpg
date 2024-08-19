from overrides import override
from entitas import InitializeProcessor, ExecuteProcessor, Matcher, Entity  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from ecs_systems.components import (
    AutoPlanningComponent,
    StageComponent,
    ActorComponent,
    PlayerComponent,
)
from enum import Enum


# 规划的策略
class PlanningStrategy(Enum):
    INVALID = 0
    STRATEGY_ONLY_PLAYERS_STAGE = 1000
    STRATEGY_ALL = 2000


class PrePlanningSystem(InitializeProcessor, ExecuteProcessor):

    def __init__(self, context: RPGEntitasContext) -> None:
        self._context: RPGEntitasContext = context
        self._strategy: PlanningStrategy = PlanningStrategy.STRATEGY_ALL
        self._execute_count: int = 0

    ############################################################################################################
    @override
    def initialize(self) -> None:
        pass

    ############################################################################################################
    @override
    def execute(self) -> None:
        ## 计数
        self._execute_count += 1
        ## 通过策略来做计划
        strategy = self.decide_strategy(self._strategy, self._execute_count)
        ## 制定更新策略
        self.make_planning_by_strategy(strategy)

    ############################################################################################################
    def decide_strategy(
        self, strategy: PlanningStrategy, current_execute_count: int
    ) -> PlanningStrategy:
        if current_execute_count == 1:
            # 第一次执行必须全部更新一遍
            return PlanningStrategy.STRATEGY_ALL
        return strategy

    ############################################################################################################
    def make_planning_by_strategy(self, strategy: PlanningStrategy) -> None:
        if strategy == PlanningStrategy.STRATEGY_ONLY_PLAYERS_STAGE:
            logger.warning(
                "STRATEGY_ONLY_PLAYERS_STAGE, 选择比较省的策略, 只规划player所在场景和actors"
            )
            playerentities = self._context.get_group(Matcher(PlayerComponent)).entities
            for playerentity in playerentities:
                # 如果有多个player在同一个stage，这里会多次执行, 但是没关系，因为这里是做防守的
                self.strategy1_only_the_stage_where_player_is_located_and_the_actors_in_it_allowed_make_plans(
                    playerentity
                )
        elif strategy == PlanningStrategy.STRATEGY_ALL:
            logger.warning(
                "STRATEGY_ALL, 选择比较费的策略，全都更新，但如果场景内没有任何actor，就不更新"
            )
            self.strategy2_all_stages_and_actors_except_player_allow_auto_planning()

    ############################################################################################################
    def strategy1_only_the_stage_where_player_is_located_and_the_actors_in_it_allowed_make_plans(
        self, playerentity: Entity
    ) -> None:
        assert playerentity is not None
        assert playerentity.has(PlayerComponent)

        context = self._context
        stage_entity = context.safe_get_stage_entity(playerentity)
        if stage_entity is None:
            logger.error("stage is None, player无所在场景是有问题的")
            return

        ##player所在场景可以规划
        stage_comp = stage_entity.get(StageComponent)

        ###player所在场景的actors可以规划
        actor_entities = context.actors_in_stage(stage_comp.name)
        if len(actor_entities) == 0:
            return

        if not stage_entity.has(AutoPlanningComponent):
            stage_entity.add(AutoPlanningComponent, stage_comp.name)

        for actor_entity in actor_entities:

            if actor_entity.has(PlayerComponent):
                continue

            actor_comp = actor_entity.get(ActorComponent)
            if not actor_entity.has(AutoPlanningComponent):
                actor_entity.add(AutoPlanningComponent, actor_comp.name)

    ############################################################################################################
    def strategy2_all_stages_and_actors_except_player_allow_auto_planning(self) -> None:
        context = self._context
        stage_entities = context.get_group(Matcher(StageComponent)).entities
        for stage_entity in stage_entities:
            stage_comp = stage_entity.get(StageComponent)
            actors_in_stage = context.actors_in_stage(stage_comp.name)
            if len(actors_in_stage) == 0:
                continue
            if not stage_entity.has(AutoPlanningComponent):
                stage_entity.add(AutoPlanningComponent, stage_comp.name)

        actor_entities = context.get_group(Matcher(ActorComponent)).entities
        for actor_entity in actor_entities:
            if actor_entity.has(PlayerComponent):
                continue
            actor_comp = actor_entity.get(ActorComponent)
            if not actor_entity.has(AutoPlanningComponent):
                actor_entity.add(AutoPlanningComponent, actor_comp.name)


############################################################################################################
