from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from gameplay_systems.action_components import (
    GoToAction,
    TagAction,
    DeadAction,
    WhisperAction,
)
from gameplay_systems.components import (
    StageComponent,
    ActorComponent,
    AppearanceComponent,
    StageGraphComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
import gameplay_systems.cn_builtin_prompt as builtin_prompt
from gameplay_systems.cn_constant_prompt import _CNConstantPrompt_ as ConstantPrompt
from typing import cast, override, List, Set, Any, Dict, Optional
from gameplay_systems.check_self_helper import CheckSelfHelper
from my_agent.agent_task import AgentTask, AgentTasksGather
from my_agent.agent_plan_and_action import AgentPlan
from extended_systems.files_def import PropFile
from rpg_game.rpg_game import RPGGame
from my_data.model_def import PropType


class StageCondCheckResponse(AgentPlan):

    def __init__(self, name: str, input_str: str) -> None:
        super().__init__(name, input_str)

    @property
    def allow(self) -> bool:
        tip_action = self.get_by_key(TagAction.__name__)
        if tip_action is None or len(tip_action.values) == 0:
            return False
        first_value = tip_action.values[0].lower()
        return first_value == "yes" or first_value == "true"

    @property
    def tips(self) -> str:
        whisper_action = self.get_by_key(WhisperAction.__name__)
        if whisper_action is None or len(whisper_action.values) == 0:
            return ""
        return " ".join(whisper_action.values)


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class PreBeforeGoToActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ###############################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(GoToAction): GroupEvent.ADDED}

    ###############################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(GoToAction)
            and entity.has(ActorComponent)
            and not entity.has(DeadAction)
        )

    ###############################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:

        for entity in entities:

            self.trans_guid_stage_name(entity)

            # 检查目标场景是否有效，可能是无效的，例如不存在，或者已经在目标场景了
            if not self.base_check(entity):
                self.on_failed(entity)
                continue

            # 检查离开当前场景的条件是否满足，需要LLM推理
            exit_result = self.handle_exit_stage_with_conditions(entity)
            if not exit_result:
                self.on_failed(entity)
                continue

            # 检查进入目标场景的条件是否满足，需要LLM推理
            enter_result = self.handle_enter_stage_with_conditions(entity)
            if not enter_result:
                self.on_failed(entity)
                continue

            # 通过了，可以去下一个场景了
            logger.debug(
                f"{self._context.safe_get_entity_name(entity)} 通过了离开和进入条件，可以去下一个场景了"
            )

    ###############################################################################################################################################
    def base_check(self, actor_entity: Entity) -> bool:

        safe_actor_name = self._context.safe_get_entity_name(actor_entity)
        current_stage_entity = self._context.safe_get_stage_entity(actor_entity)
        if current_stage_entity is None:
            logger.error(f"{safe_actor_name}没有当前场景，这是个错误")
            return False

        target_stage_name = self.get_target_stage_name(actor_entity)
        target_stage_entity = self._context.get_stage_entity(
            self.get_target_stage_name(actor_entity)
        )
        if target_stage_entity is None:
            # 无效的去往目标!
            self._context.broadcast_entities(
                set({actor_entity}),
                builtin_prompt.go_to_stage_failed_because_stage_is_invalid_prompt(
                    safe_actor_name, target_stage_name
                ),
            )
            return False

        if current_stage_entity == target_stage_entity:
            # 已经在这个场景里了，不要重复去了
            self._context.broadcast_entities(
                set({actor_entity}),
                builtin_prompt.go_to_stage_failed_because_already_in_stage_prompt(
                    safe_actor_name, target_stage_name
                ),
            )

            return False

        assert current_stage_entity.has(StageGraphComponent)
        stage_graph_comp = current_stage_entity.get(StageGraphComponent)
        stage_graph: Set[str] = stage_graph_comp.stage_graph
        if target_stage_name not in stage_graph:
            ## 场景之间无连接就不能去。
            self._context.broadcast_entities(
                set({actor_entity}),
                builtin_prompt.go_to_stage_failed_because_stage_is_invalid_prompt(
                    safe_actor_name, target_stage_name
                ),
            )
            return False

        return True

    ###############################################################################################################################################
    def has_exit_conditions(self, stage_entity: Entity) -> bool:
        safe_name = self._context.safe_get_entity_name(stage_entity)
        kickoff = self._context._kick_off_message_system.get_message(safe_name)
        return ConstantPrompt.STAGE_EXIT_TAG in kickoff

    ###############################################################################################################################################
    def has_entry_conditions(self, stage_entity: Entity) -> bool:
        safe_name = self._context.safe_get_entity_name(stage_entity)
        kickoff = self._context._kick_off_message_system.get_message(safe_name)
        return ConstantPrompt.STAGE_ENTRY_TAG in kickoff

    ###############################################################################################################################################
    def handle_exit_stage_with_conditions(self, actor_entity: Entity) -> bool:
        #
        current_stage_entity = self._context.safe_get_stage_entity(actor_entity)
        assert current_stage_entity is not None
        if not self.has_exit_conditions(current_stage_entity):
            return True
        #
        actor_name = self._context.safe_get_entity_name(actor_entity)
        current_stage_name = self._context.safe_get_entity_name(current_stage_entity)

        final_prompt = builtin_prompt.stage_exit_conditions_check_prompt(
            actor_name,
            current_stage_name,
            self.get_actor_appearance_prompt(actor_entity),
            self.get_actor_props(actor_entity),
        )

        ## 让大模型去推断是否可以离开，分别检查stage自身，角色状态（例如长相），角色道具（拥有哪些道具与文件）
        agent = self._context._langserve_agent_system.get_agent(current_stage_name)
        if agent is None:
            return False

        task = AgentTask.create(agent, final_prompt)
        if task is None:
            return False

        response = task.request()
        if response is None:
            return False

        response_plan = StageCondCheckResponse(current_stage_name, response)
        #
        if not response_plan.allow:
            # 通知事件
            self._context.broadcast_entities(
                set({actor_entity}),
                builtin_prompt.exit_stage_failed_beacuse_stage_refuse_prompt(
                    actor_name, current_stage_name, response_plan.tips
                ),
            )

            return False

        logger.debug(f"允许通过！说明如下: {response_plan.tips}")
        ## 可以删除，允许通过！这个上下文就拿掉，不需要了。
        self._context._langserve_agent_system.remove_last_conversation_between_human_and_ai(
            current_stage_name
        )
        return True

    ###############################################################################################################################################
    def handle_enter_stage_with_conditions(self, actor_entity: Entity) -> bool:

        target_stage_entity = self._context.get_stage_entity(
            self.get_target_stage_name(actor_entity)
        )
        assert target_stage_entity is not None
        if target_stage_entity is None:
            return False

        ##
        if not self.has_entry_conditions(target_stage_entity):
            return True

        ##
        actor_name = self._context.safe_get_entity_name(actor_entity)
        target_stage_name = self._context.safe_get_entity_name(target_stage_entity)

        # 最终提示词
        final_prompt = builtin_prompt.stage_entry_conditions_check_prompt(
            actor_name,
            target_stage_name,
            self.get_actor_appearance_prompt(actor_entity),
            self.get_actor_props(actor_entity),
        )

        ## 让大模型去推断是否可以离开，分别检查stage自身，角色状态（例如长相），角色道具（拥有哪些道具与文件）
        agent = self._context._langserve_agent_system.get_agent(target_stage_name)
        if agent is None:
            return False

        task = AgentTask.create(agent, final_prompt)
        if task is None:
            return False

        response = task.request()
        if response is None:
            return False

        response_plan = StageCondCheckResponse(target_stage_name, response)
        if not response_plan.allow:
            # 通知事件, 因为没动，得是当前场景需要通知
            current_stage_entity = self._context.safe_get_stage_entity(actor_entity)
            assert current_stage_entity is not None

            self._context.broadcast_entities(
                set({actor_entity}),
                builtin_prompt.enter_stage_failed_beacuse_stage_refuse_prompt(
                    actor_name, target_stage_name, response_plan.tips
                ),
            )

            return False

        logger.debug(f"允许通过！说明如下: {response_plan.tips}")
        ## 可以删除，允许通过！这个上下文就拿掉，不需要了。
        self._context._langserve_agent_system.remove_last_conversation_between_human_and_ai(
            target_stage_name
        )
        return True

    ###############################################################################################################################################
    def get_target_stage_name(self, actor_entity: Entity) -> str:
        assert actor_entity.has(ActorComponent)
        assert actor_entity.has(GoToAction)

        go_to_action = actor_entity.get(GoToAction)
        if len(go_to_action.values) == 0:
            return ""
        return str(go_to_action.values[0])

    ###############################################################################################################################################
    def get_actor_appearance_prompt(self, actor_entity: Entity) -> str:
        assert actor_entity.has(ActorComponent)
        if not actor_entity.has(AppearanceComponent):
            return ""
        appearance_comp = actor_entity.get(AppearanceComponent)
        return cast(str, appearance_comp.appearance)

    ###############################################################################################################################################
    def get_actor_props(self, actor_entity: Entity) -> List[PropFile]:

        check_self = CheckSelfHelper(self._context, actor_entity)
        return (
            check_self.get_prop_files(PropType.TYPE_SPECIAL.value)
            + check_self.get_prop_files(PropType.TYPE_WEAPON.value)
            + check_self.get_prop_files(PropType.TYPE_CLOTHES.value)
            + check_self.get_prop_files(PropType.TYPE_NON_CONSUMABLE_ITEM.value)
        )

    ###############################################################################################################################################
    def on_failed(self, actor_entity: Entity) -> None:
        if actor_entity.has(GoToAction):
            actor_entity.remove(GoToAction)

    ###############################################################################################################################################
    def trans_guid_stage_name(self, actor_entity: Entity) -> None:
        assert actor_entity.has(ActorComponent)
        assert actor_entity.has(GoToAction)

        go_to_action = actor_entity.get(GoToAction)
        if len(go_to_action.values) == 0:
            return
        check_unknown_guid_stage_name = go_to_action.values[0]
        if not builtin_prompt.is_unknown_guid_stage_name(check_unknown_guid_stage_name):
            return

        logger.debug(f"current_name = {check_unknown_guid_stage_name}")
        guid = builtin_prompt.extract_from_unknown_guid_stage_name(
            check_unknown_guid_stage_name
        )
        stage_entity = self._context.get_entity_by_guid(guid)
        if stage_entity is None:
            logger.error(f"未知的场景GUID({guid})")
            return

        if not stage_entity.has(StageComponent):
            logger.error(f"({guid}) 对应的不是一个场景")
            return

        go_to_action.values[0] = self._context.safe_get_entity_name(stage_entity)


###############################################################################################################################################
