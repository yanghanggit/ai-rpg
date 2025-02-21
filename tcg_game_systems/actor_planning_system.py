from agent.chat_request_handler import ChatRequestHandler
from components.actions import (
    ACTOR_AVAILABLE_ACTIONS_REGISTER,
    MindVoiceAction,
    WhisperAction,
    AnnounceAction,
    SpeakAction,
)
from components.components import (
    ActorComponent,
    KickOffDoneFlagComponent,
    PlayerActorFlagComponent,
    StageComponent,
    StageEnvironmentComponent,
    FinalAppearanceComponent,
    ActorRolePlayPlanningPermitFlagComponent,
)
from entitas import ExecuteProcessor, Matcher  # type: ignore
from overrides import override
from typing import List, final, cast
from game.tcg_game_context import TCGGameContext
from game.tcg_game import TCGGame
from loguru import logger
from tcg_game_systems.action_bundle import ActionBundle


#######################################################################################################################################
@final
class ActorPlanningSystem(ExecuteProcessor):

    def __init__(self, context: TCGGameContext) -> None:
        self._context: TCGGameContext = context
        self._game: TCGGame = cast(TCGGame, context._game)
        assert self._game is not None

    #######################################################################################################################################
    @override
    def execute(self) -> None:
        logger.debug("ActorPlanningExecutionSystem.execute()")

    #######################################################################################################################################
    @override
    async def a_execute1(self) -> None:
        # logger.debug("ActorPlanningExecutionSystem.a_execute1()")
        await self._process_actor_planning_request()

    #######################################################################################################################################
    @override
    async def a_execute2(self) -> None:
        logger.debug("ActorPlanningExecutionSystem.a_execute2()")

    #######################################################################################################################################
    async def _process_actor_planning_request(self) -> None:

        actor_entities = self._context.get_group(
            Matcher(
                all_of=[
                    ActorRolePlayPlanningPermitFlagComponent,
                ],
            )
        ).entities.copy()

        if len(actor_entities) == 0:
            return

        request_handlers: List[ChatRequestHandler] = []
        for entity in actor_entities:
            # 找到当前场景, TODO 如果只有player在的stage才能更新这个规则不变，可以把下面挪到循环外，省一下复杂度
            current_stage = self._context.safe_get_stage_entity(entity)
            assert current_stage is not None
            # 找到当前场景内所有角色
            actors_set = self._game.retrieve_actors_on_stage(current_stage)
            actors_set.remove(entity)
            # 移除自己后，剩下的角色的名字+外观信息
            actors_info_list: List[str] = [
                f"{actor._name}:{actor.get(FinalAppearanceComponent).final_appearance}"
                for actor in actors_set
                if actor.has(FinalAppearanceComponent)
            ]
            message = _generate_actor_plan_prompt(
                current_stage._name,
                current_stage.get(StageEnvironmentComponent).narrate,
                entity.get(FinalAppearanceComponent).final_appearance,
                actors_info_list,
            )
            assert message is not None
            agent_short_term_memory = self._game.get_agent_short_term_memory(entity)
            request_handlers.append(
                ChatRequestHandler(
                    name=entity._name,
                    prompt=message,
                    chat_history=agent_short_term_memory.chat_history,
                )
            )

        await self._game.langserve_system.gather(request_handlers=request_handlers)

        for request_handler in request_handlers:
            logger.warning(
                f"Agent: {request_handler._name}, Response:\n{request_handler.response_content}"
            )

            if request_handler.response_content == "":
                continue

            entity2 = self._context.get_entity_by_name(request_handler._name)
            assert entity2 is not None
            self._game.append_human_message(
                entity2, _compress_actor_plan_prompt(request_handler._prompt)
            )
            self._game.append_ai_message(entity2, request_handler.response_content)
            bundle = ActionBundle(entity2._name, request_handler.response_content)
            ret = bundle.assign_actions_to_entity(
                entity2, ACTOR_AVAILABLE_ACTIONS_REGISTER
            )
            assert ret is True, "Action Bundle Error"

    #######################################################################################################################################


#######################################################################################################################################


def _generate_actor_plan_prompt(
    current_stage_name: str,
    current_stage_narration: str,
    self_appearence: str,
    actors_info_list: List[str],
) -> str:
    assert current_stage_name is not "", "current_stage is empty"
    return f"""
# 请制定你的行动计划，请确保你的行为和言语符合游戏规则和设定

## 当前所在的场景
{current_stage_name}

### 当前场景描述
{current_stage_narration}

### 你当前的外观特征
{self_appearence}

### 当前场景内除你之外的其他角色的名称与外观特征
{"\n".join(actors_info_list)}

## 输出要求
### 输出格式指南
请严格遵循以下 JSON 结构示例： 
{{
    "{SpeakAction.__name__}":["@角色全名(你要对谁说,只能是场景内的角色):你要说的内容（场景内其他角色会听见）",...],
}}

### 注意事项
- 引用角色或场景时，请严格遵守全名机制
- 所有输出必须为第一人称视角。
- JSON 对象中可以包含上述键中的一个或多个。
- 注意！不允许重复使用上述的键！ 
- 注意！不允许使用不在上述列表中的键！（即未定义的键位），注意看‘输出要求’
- 如要使用名字，请使用全名。见上文‘全名机制’。
- 含有“...”的键可以接收多个值，否则只能接收一个值。
- 输出不得包含超出所需 JSON 格式的其他文本、解释或附加信息。
- 不要使用```json```来封装内容。"""


#  "{MindVoiceAction.__name__}":["你的内心独白",...],
#  "{WhisperAction.__name__}":["@角色全名(你要对谁说,只能是场景内的角色):你想私下说的内容（只有你和目标知道）",...],
#  "{AnnounceAction.__name__}":["你要说的内容（无特定目标，场景内所有角色都会听见）",...],
#  "{SpeakAction.__name__}":["@角色全名(你要对谁说,只能是场景内的角色):你要说的内容（场景内其他角色会听见）",...],


def _compress_actor_plan_prompt(
    prompt: str,
) -> str:

    # logger.debug(f"原来的提示词为:\n{prompt}")
    return "# 请做出你的计划，决定你将要做什么，并以 JSON 格式输出。"
