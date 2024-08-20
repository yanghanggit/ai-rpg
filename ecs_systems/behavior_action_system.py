from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from ecs_systems.action_components import BehaviorAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import override, Optional, Any, Dict
from loguru import logger

# from my_agent.agent_action import AgentAction
from file_system.files_def import PropFile
from build_game.data_model import PropModel
import json


class BehaviorActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context

    ######################################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(BehaviorAction): GroupEvent.ADDED}

    ######################################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(BehaviorAction)

    ######################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.handle(entity)

    ######################################################################################################################################################
    #
    def handle(self, entity: Entity) -> None:
        assert entity.has(BehaviorAction)

        behavior_action: BehaviorAction = entity.get(BehaviorAction)
        # acton: AgentAction = behavior_action.action
        if len(behavior_action.values) != 4:
            return

        # /behavior 激活#黑火印记
        # skill_name = "激活特殊能力"
        # name = "人物.火十一"
        # target = "人物.火十一"
        # prop_name = "黑火印记"

        # /behavior 激活#黑火印记
        # skill_name = acton.value(0)
        # my_name = acton.value(1)
        # target_name = acton.value(2)
        # prop_name = acton.value(3)

        skill_name = "激活特殊能力"
        my_name = "人物.火十一"
        target_name = "人物.火十一"
        prop_name = "黑火印记"

        target_entity = self._context.get_entity_by_codename_component(target_name)
        if target_entity is None:
            return

        my_safe_name = self._context.safe_get_entity_name(entity)
        assert my_safe_name == my_name

        prop_file = self._context._file_system.get_file(PropFile, my_name, prop_name)

        skill_file = self.get_skill(my_name, skill_name)

        self.handle_behavior(entity, skill_file, my_name, target_name, prop_file)

    ######################################################################################################################################################
    def handle_behavior(
        self,
        entity: Entity,
        skill_file: Optional[PropFile],
        my_name: str,
        target_name: str,
        prop_file: Optional[PropFile],
    ) -> None:
        return

        # 判断是否可以发起

        # 判断是否符合世界规律

        # 最后向目标释放

        # pass

    ######################################################################################################################################################
    def get_skill(self, owner_name: str, skill_name: str) -> Optional[PropFile]:

        fake_data: Dict[str, Any] = {
            "name": skill_name,
            "codename": "special_ability",
            "description": skill_name,
            "isunique": "No",
            "type": "Skill",
            "attributes": [0, 0, 0, 0],
            "appearance": "无",
        }

        prop_model = PropModel.model_validate_json(
            json.dumps(fake_data, ensure_ascii=False)
        )

        prop_file = PropFile(
            self._context._guid_generator.generate(),
            skill_name,
            owner_name,
            prop_model,
            1,
        )

        return prop_file

    ######################################################################################################################################################
