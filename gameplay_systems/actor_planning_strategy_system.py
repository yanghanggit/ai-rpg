from entitas import InitializeProcessor, ExecuteProcessor, Matcher, Entity  # type: ignore
from overrides import override
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from gameplay_systems.components import (
    AutoPlanningComponent,
    StageComponent,
    ActorComponent,
    EnterStageComponent,
)
from rpg_game.rpg_game import RPGGame
from typing import List, Dict, Optional, cast


class ActorPlanningStrategySystem(InitializeProcessor, ExecuteProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game
        self._order_queue: Dict[str, List[str]] = {}

    ############################################################################################################
    @override
    def initialize(self) -> None:

        self._order_queue.clear()
        stage_entities = self._context.get_group(Matcher(StageComponent)).entities
        for stage_entity in stage_entities:
            self.extend_order_queue(self._order_queue, stage_entity, [])

    ############################################################################################################
    @override
    def execute(self) -> None:
        # 如果有最近的舞台转换，就处理
        self.handle_recent_stage_transition_actors()
        # 添加自动规划组件
        self.handle_add_auto_planning_component()
        # 删除
        self.handle_remove_enter_stage_component()

    ############################################################################################################
    def handle_recent_stage_transition_actors(self) -> None:
        recent_stage_transition_actors: Dict[str, List[str]] = (
            self.analyze_recent_stage_transition_actors()
        )
        if len(recent_stage_transition_actors) == 0:
            return

        stage_entities = self._context.get_group(Matcher(StageComponent)).entities
        for stage_entity in stage_entities:

            stage_comp = stage_entity.get(StageComponent)
            self.extend_order_queue(
                self._order_queue,
                stage_entity,
                recent_stage_transition_actors.get(stage_comp.name, []),
            )

    ############################################################################################################
    def handle_add_auto_planning_component(self) -> None:
        stage_entities = self._context.get_group(
            Matcher(StageComponent, AutoPlanningComponent)
        ).entities

        for stage_entity in stage_entities:

            pop_actor_entity = self.pop_first_executable_actor_from_order_queue(
                self._order_queue, stage_entity
            )
            if pop_actor_entity is None:
                # try to fill again
                self.extend_order_queue(self._order_queue, stage_entity, [])
                pop_actor_entity = self.pop_first_executable_actor_from_order_queue(
                    self._order_queue, stage_entity
                )

            if pop_actor_entity is None:
                continue

            assert pop_actor_entity.has(ActorComponent)
            if not pop_actor_entity.has(AutoPlanningComponent):
                actor_comp = pop_actor_entity.get(ActorComponent)
                pop_actor_entity.add(AutoPlanningComponent, actor_comp.name)

    ############################################################################################################
    def extend_order_queue(
        self,
        order_queue: Dict[str, List[str]],
        stage_entity: Entity,
        append_recent_stage_transition_actors: List[str],
    ) -> None:

        stage_name = stage_entity.get(StageComponent).name
        actor_names = self._context.get_actor_names_in_stage(stage_entity)

        # step1: 移除新进入场景的
        if len(append_recent_stage_transition_actors) > 0:
            actor_names = actor_names - set(append_recent_stage_transition_actors)

        # step2: 重建一组新的
        order_queue.setdefault(stage_name, []).extend(list(actor_names))

        # step3: 新进入场景的加入到队列尾部
        if len(append_recent_stage_transition_actors) > 0:
            order_queue.get(stage_name, []).extend(
                append_recent_stage_transition_actors
            )

    ############################################################################################################
    def analyze_recent_stage_transition_actors(self) -> Dict[str, List[str]]:
        ret: Dict[str, List[str]] = {}

        actor_entities = self._context.get_group(Matcher(EnterStageComponent)).entities

        for actor_entity in actor_entities:
            enter_stage_comp = actor_entity.get(EnterStageComponent)
            ret.setdefault(enter_stage_comp.enter_stage, []).append(
                enter_stage_comp.name
            )

        return ret

    ############################################################################################################
    def handle_remove_enter_stage_component(self) -> None:
        actor_entities = self._context.get_group(
            Matcher(EnterStageComponent)
        ).entities.copy()
        for actor_entity in actor_entities:
            actor_entity.remove(EnterStageComponent)

    ############################################################################################################
    def pop_first_executable_actor_from_order_queue(
        self, order_queue: Dict[str, List[str]], stage_entity: Entity
    ) -> Optional[Entity]:

        stage_name = cast(str, stage_entity.get(StageComponent).name)
        order_queue_list = order_queue.get(stage_name, [])
        while len(order_queue_list) > 0:
            actor_name = order_queue_list.pop(0)
            actor_entity = self._context.get_actor_entity(actor_name)
            if actor_entity is None:
                # 不存在的
                continue

            actor_comp = actor_entity.get(ActorComponent)
            if actor_comp.current_stage != stage_name:
                # 可能已经离开了。
                continue

            return actor_entity

        return None

    ############################################################################################################
