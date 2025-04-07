from typing import Tuple, final, List
from loguru import logger
from entitas import ExecuteProcessor, Matcher, Entity  # type: ignore
from overrides import override
from game.tcg_game import TCGGame
from models_v_0_0_1 import (
    HomeComponent,
    CanStartPlanningComponent,
    StageComponent,
    RuntimeComponent,
    PlayerComponent,
)


@final
class HomePrePlanningSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ############################################################################################################
    @override
    def execute(self) -> None:
        # 清除所有的 planning 组件
        self._cleanup_planning_entities()
        # 给所有的stage添加 planning 组件
        self._assign_planning_component_to_stages()
        # 给所有的actor添加 planning 组件
        self._assign_planning_component_to_actors()

    ############################################################################################################
    def _cleanup_planning_entities(self) -> None:

        planning_entities = self._game.get_group(
            Matcher(all_of=[CanStartPlanningComponent])
        ).entities.copy()

        for entity in planning_entities:
            logger.debug(
                f"HomePrePlanningSystem: _clear_planning: {entity.get(CanStartPlanningComponent).name}，清除 CanStartPlanningComponent。"
            )
            entity.remove(CanStartPlanningComponent)

    ############################################################################################################
    def _assign_planning_component_to_stages(self) -> None:

        stage_entities = self._game.get_group(
            Matcher(
                all_of=[HomeComponent, StageComponent],
                none_of=[
                    CanStartPlanningComponent,
                ],
            )
        ).entities.copy()

        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        player_stage = self._game.safe_get_stage_entity(player_entity)
        assert player_stage is not None

        for stage_entity in stage_entities:

            if stage_entity != player_stage:
                # 如果不是玩家的stage，跳过
                continue

            # 如果是玩家的stage，添加 CanStartPlanningComponent
            logger.debug(
                f"HomePrePlanningSystem: _can_stage_planning: {stage_entity.get(StageComponent).name}，添加 CanStartPlanningComponent。"
            )
            stage_entity.replace(CanStartPlanningComponent, stage_entity._name)

    ############################################################################################################
    def _assign_planning_component_to_actors(self) -> None:
        stage_entities = self._game.get_group(
            Matcher(
                all_of=[HomeComponent, StageComponent, CanStartPlanningComponent],
            )
        ).entities.copy()

        # 如果是空了，就重置一次。
        for stage_entity in stage_entities:
            self._refresh_home_stage_actor_order(stage_entity)

        # 每个stage的action_order的第一个pop出来，作为可以行动的人。
        for stage_entity in stage_entities:
            home_comp = stage_entity.get(HomeComponent)
            action_order = home_comp.action_order
            while len(action_order) > 0:

                actor_name = action_order.pop(0)
                actor_entity = self._game.get_actor_entity(actor_name)
                assert actor_entity is not None
                if actor_entity is None:
                    continue

                if actor_entity.has(PlayerComponent):
                    # 如果是玩家的角色，跳过
                    continue

                logger.debug(
                    f"HomePrePlanningSystem: _can_actor_planning: {actor_name}，添加 CanStartPlanningComponent。"
                )
                actor_entity.replace(
                    CanStartPlanningComponent,
                    actor_name,
                )
                # 只有第一个。
                break

        # 如果空了，就重新构建一次。
        for stage_entity in stage_entities:
            self._refresh_home_stage_actor_order(stage_entity)

    ############################################################################################################
    def _refresh_home_stage_actor_order(self, stage_entity: Entity) -> None:
        # 重新构建stage的action_order
        home_comp = stage_entity.get(HomeComponent)
        action_order = home_comp.action_order
        if len(action_order) == 0:
            actors_on_stage = self._game.retrieve_actors_on_stage(stage_entity)
            order_actors_by_action = self._sort_action_order_by_guid(
                list(actors_on_stage)
            )
            sorted_actor_names = [actor._name for actor in order_actors_by_action]
            stage_entity.replace(
                HomeComponent,
                home_comp.name,
                sorted_actor_names,
            )

    ############################################################################################################
    def _sort_action_order_by_guid(self, actor_entities: List[Entity]) -> List[Entity]:

        entity_guid_pairs: List[Tuple[Entity, int]] = []
        for entity in actor_entities:
            assert entity.has(RuntimeComponent)
            runtime_comp = entity.get(RuntimeComponent)
            entity_guid_pairs.append((entity, runtime_comp.runtime_index))

        return [entity for entity, _ in sorted(entity_guid_pairs, key=lambda x: x[1])]

    ############################################################################################################
