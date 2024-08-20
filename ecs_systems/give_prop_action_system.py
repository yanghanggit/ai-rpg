from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from ecs_systems.action_components import GivePropAction, CheckStatusAction, DeadAction
from ecs_systems.components import ActorComponent
from loguru import logger

# from my_agent.agent_action import AgentAction
import gameplay.conversation_helper
from typing import List, override
from ecs_systems.stage_director_component import StageDirectorComponent
from ecs_systems.stage_director_event import IStageDirectorEvent
import ecs_systems.cn_builtin_prompt as builtin_prompt
import file_system.helper
from file_system.files_def import PropFile
import my_format_string.target_and_message_format_string


class ActorGivePropEvent(IStageDirectorEvent):

    def __init__(
        self, from_who: str, to_who: str, prop_name: str, action_result: bool
    ) -> None:
        self._from_who: str = from_who
        self._to_who: str = to_who
        self._prop_name: str = prop_name
        self._action_result: bool = action_result

    def to_actor(self, actor_name: str, extended_context: RPGEntitasContext) -> str:
        if actor_name != self._from_who or actor_name != self._to_who:
            return ""
        return builtin_prompt.give_prop_action_prompt(
            self._from_who, self._to_who, self._prop_name, self._action_result
        )

    def to_stage(self, stage_name: str, extended_context: RPGEntitasContext) -> str:
        return ""


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class GivePropActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext):
        super().__init__(context)
        self._context = context

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(GivePropAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(GivePropAction)
            and entity.has(ActorComponent)
            and not entity.has(DeadAction)
        )

    ####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.give_prop(entity)

    ####################################################################################################################################
    def give_prop(self, entity: Entity) -> List[str]:

        success_target_names: List[str] = []
        safe_name = self._context.safe_get_entity_name(entity)

        give_action = entity.get(GivePropAction)
        # give_action: AgentAction = give_comp.action
        target_and_message = (
            my_format_string.target_and_message_format_string.target_and_message_values(
                give_action.values
            )
        )
        # give_action.target_and_message_values()
        for tp in target_and_message:
            target_name = tp[0]
            message = tp[1]

            if (
                gameplay.conversation_helper.check_conversation_enable(
                    self._context, entity, target_name
                )
                != gameplay.conversation_helper.ErrorConversationEnable.VALID
            ):
                # 不能交谈就是不能交换道具
                continue

            prop_name = message
            action_result = self._give_prop(entity, target_name, prop_name)
            StageDirectorComponent.add_event_to_stage_director(
                self._context,
                entity,
                ActorGivePropEvent(safe_name, target_name, prop_name, action_result),
            )
            success_target_names.append(target_name)

        return success_target_names

    ####################################################################################################################################
    def _give_prop(
        self, entity: Entity, target_actor_name: str, mypropname: str
    ) -> bool:
        safename = self._context.safe_get_entity_name(entity)
        myprop = self._context._file_system.get_file(PropFile, safename, mypropname)
        if myprop is None:
            return False
        # self._context._file_system.give_prop_file(safename, target_actor_name, mypropname)
        file_system.helper.give_prop_file(
            self._context._file_system, safename, target_actor_name, mypropname
        )
        return True

    ####################################################################################################################################
    def on_success(self, name: str) -> None:
        entity = self._context.get_actor_entity(name)
        if entity is None:
            logger.error(f"actor {name} not found")
            return
        if entity.has(CheckStatusAction):
            return
        actor_comp = entity.get(ActorComponent)
        entity.add(
            CheckStatusAction,
            actor_comp.name,
            CheckStatusAction.__name__,
            [actor_comp.name],
        )


####################################################################################################################################
