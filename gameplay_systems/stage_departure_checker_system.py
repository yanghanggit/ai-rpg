from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from my_components.action_components import (
    GoToAction,
    TagAction,
    DeadAction,
    WhisperAction,
)
from my_components.components import (
    ActorComponent,
    AppearanceComponent,
    KickOffContentComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
import gameplay_systems.builtin_prompt_util as builtin_prompt_util
from typing import final, override, List, Set, Any, Dict, Optional
from gameplay_systems.actor_checker import ActorChecker
from my_agent.agent_task import AgentTask
from my_agent.agent_plan import AgentPlanResponse
from extended_systems.prop_file import PropFile, generate_prop_prompt
from rpg_game.rpg_game import RPGGame
from my_models.file_models import PropType
from my_models.event_models import AgentEvent


def _generate_exit_conditions_prompt(
    actor_name: str,
    current_stage_name: str,
    actor_status_prompt: str,
    prop_files: List[PropFile],
) -> str:

    prop_prompt_list = "无"
    if len(prop_files) > 0:
        prop_prompt_list = "\n".join(
            [
                generate_prop_prompt(
                    prop, description_prompt=True, appearance_prompt=True
                )
                for prop in prop_files
            ]
        )

    ret_prompt = f"""# {actor_name} 想要离开场景: {current_stage_name}。
## 第1步: 请回顾你的 {builtin_prompt_util.ConstantPromptTag.STAGE_EXIT_TAG}

## 第2步: 根据当前‘你的状态’判断是否满足允许{actor_name}离开
当前状态可能由于事件而变化，请仔细考虑。

## 第3步: 检查{actor_name}的状态是否符合离开的需求:
### 当前角色状态: 
{actor_status_prompt if actor_status_prompt != "" else "无"}

## 第4步: 检查{actor_name}的道具(与拥有的特殊能力)是否符合以下要求:
### 当前角色道具与特殊能力信息: 
{prop_prompt_list}

# 判断结果
- 完成以上步骤后，决定是否允许 {actor_name} 离开 {current_stage_name}。

# 本次输出结果格式要求。需遵循 输出格式指南:
{{
    {WhisperAction.__name__}: ["@角色名字(你要对谁说,只能是场景内的角色)>你想私下说的内容，即描述允许离开或不允许的原因，使{actor_name}明白"],
    {TagAction.__name__}: ["Yes/No"]
}}
## 附注
- {WhisperAction.__name__} 中描述的判断理由。如果不允许离开，就只说哪一条不符合要求，不要都说出来，否则会让{actor_name}迷惑，和造成不必要的提示，影响玩家解谜的乐趣。
- Yes: 允许离开
- No: 不允许离开
"""

    return ret_prompt


################################################################################################################################################
def _generate_stage_exit_failure_prompt(
    actor_name: str, current_stage_name: str, show_tips: str
) -> str:
    return f"""# {actor_name} 想要离开场景: {current_stage_name}，但是失败了。
## 说明:
{show_tips}"""


###############################################################################################################################################
@final
class StageDepartureResponse(AgentPlanResponse):

    def __init__(self, name: str, input_str: str) -> None:
        super().__init__(name, input_str)

    @property
    def allow(self) -> bool:
        return self._parse_boolean(TagAction.__name__)

    @property
    def tips(self) -> str:
        return self._concatenate_values(WhisperAction.__name__)


###############################################################################################################################################


@final
class StageDepartureCheckerSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game
        self._react_entities_copy: List[Entity] = []

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
        self._react_entities_copy = entities.copy()

    ###############################################################################################################################################
    @override
    async def a_execute2(self) -> None:
        if len(self._react_entities_copy) == 0:
            return

        await self._execute2(self._react_entities_copy)
        self._react_entities_copy.clear()

    ###############################################################################################################################################
    async def _execute2(self, entities: List[Entity]) -> None:

        tasks = self.create_tasks(entities)
        if len(tasks) == 0:
            return

        responses = await AgentTask.gather(
            [task for task in tasks.values()],
        )

        if len(responses) == 0:
            self.on_remove_all(entities)
            return

        self.handle_tasks(tasks)

    ######################################################################################################################################################
    def create_tasks(self, actor_entities: List[Entity]) -> Dict[str, AgentTask]:

        ret: Dict[str, AgentTask] = {}

        for actor_entity in actor_entities:

            current_stage_entity = self._context.safe_get_stage_entity(actor_entity)
            assert current_stage_entity is not None
            if not self.has_conditions(current_stage_entity):
                continue

            task = self.create_task(actor_entity)
            if task is not None:
                ret[self._context.safe_get_entity_name(actor_entity)] = task
            else:
                self.on_remove_action(actor_entity)

        return ret

    ######################################################################################################################################################
    def create_task(self, actor_entity: Entity) -> Optional[AgentTask]:
        #
        current_stage_entity = self._context.safe_get_stage_entity(actor_entity)
        assert current_stage_entity is not None

        current_stage_name = self._context.safe_get_entity_name(current_stage_entity)
        stage_agent = self._context.agent_system.get_agent(current_stage_name)
        if stage_agent is None:
            return None

        actor_name = self._context.safe_get_entity_name(actor_entity)
        prompt = _generate_exit_conditions_prompt(
            actor_name,
            current_stage_name,
            actor_entity.get(AppearanceComponent).appearance,
            self.get_actor_props(actor_entity),
        )

        return AgentTask.create(stage_agent, prompt)

    ######################################################################################################################################################
    def handle_tasks(self, tasks: Dict[str, AgentTask]) -> None:

        for actor_name, stage_agent_task in tasks.items():
            if stage_agent_task.response_content == "":
                continue

            response_plan = StageDepartureResponse(
                stage_agent_task.agent_name, stage_agent_task.response_content
            )

            if not response_plan.allow:

                actor_entity = self._context.get_actor_entity(actor_name)
                assert actor_entity is not None

                self._context.notify_event(
                    set({actor_entity}),
                    AgentEvent(
                        message=_generate_stage_exit_failure_prompt(
                            actor_name, stage_agent_task.agent_name, response_plan.tips
                        )
                    ),
                )

                self.on_remove_action(actor_entity)

            else:

                self._context.agent_system.remove_last_human_ai_conversation(
                    stage_agent_task.agent_name
                )

    ###############################################################################################################################################
    def on_remove_all(
        self, entities: List[Entity], action_comps: Set[type[Any]] = {GoToAction}
    ) -> None:

        for entity in entities:
            self.on_remove_action(entity, action_comps)

    ###############################################################################################################################################
    def on_remove_action(
        self, entity: Entity, action_comps: Set[type[Any]] = {GoToAction}
    ) -> None:

        for action_comp in action_comps:
            if entity.has(action_comp):
                entity.remove(action_comp)

    ###############################################################################################################################################
    def has_conditions(self, stage_entity: Entity) -> bool:
        if not stage_entity.has(KickOffContentComponent):
            return False

        kick_off_comp = stage_entity.get(KickOffContentComponent)
        return (
            builtin_prompt_util.ConstantPromptTag.STAGE_EXIT_TAG
            in kick_off_comp.content
        )

    ###############################################################################################################################################
    # def get_actor_appearance_prompt(self, actor_entity: Entity) -> str:
    #     assert actor_entity.has(ActorComponent)
    #     if not actor_entity.has(AppearanceComponent):
    #         return ""
    #     appearance_comp = actor_entity.get(AppearanceComponent)
    #     return appearance_comp.appearance

    ###############################################################################################################################################
    def get_actor_props(self, actor_entity: Entity) -> List[PropFile]:

        check_self = ActorChecker(self._context, actor_entity)
        return (
            check_self.get_prop_files(PropType.TYPE_SPECIAL)
            + check_self.get_prop_files(PropType.TYPE_WEAPON)
            + check_self.get_prop_files(PropType.TYPE_CLOTHES)
            + check_self.get_prop_files(PropType.TYPE_NON_CONSUMABLE_ITEM)
        )

    ###############################################################################################################################################
