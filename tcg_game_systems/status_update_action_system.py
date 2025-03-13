from entitas import Entity, Matcher, GroupEvent  # type: ignore
from typing import Set, Tuple, final, override
from components.actions2 import (
    StatusUpdateAction,
)
from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem
from tcg_game_systems.status_check_utils import StatusCheckUtils


@final
class StatusUpdateActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(StatusUpdateAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(StatusUpdateAction)

    ####################################################################################################################################
    @override
    async def a_execute2(self) -> None:

        # 准备数据
        stage_entities, actor_entities = self._classify_entities()

        status_check_utils = StatusCheckUtils(
            self._game, stage_entities, actor_entities
        )
        await status_check_utils.a_execute()

    ####################################################################################################################################
    # 分类并提取出场景和角色
    def _classify_entities(self) -> Tuple[Set[Entity], Set[Entity]]:
        ret_stage_entities: Set[Entity] = set()
        ret_actor_entities: Set[Entity] = set()

        # 先分类
        for entity in self._react_entities_copy:

            # 找所在场景
            stage_entity = self._game.safe_get_stage_entity(entity)
            assert stage_entity is not None
            ret_stage_entities.add(stage_entity)

            # 找所在角色
            ret_actor_entities.update(self._game.retrieve_actors_on_stage(stage_entity))

        return ret_stage_entities, ret_actor_entities

    ####################################################################################################################################
