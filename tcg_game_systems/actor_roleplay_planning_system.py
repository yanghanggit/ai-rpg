from entitas import ExecuteProcessor, Matcher, Entity  # type: ignore
from agent.chat_request_handler import ChatRequestHandler
from components.actions import (
    ACTOR_AVAILABLE_ACTIONS_REGISTER,
    SpeakAction,
)
from components.components import (
    StageEnvironmentComponent,
    FinalAppearanceComponent,
    ActorRolePlayPlanningPermitFlagComponent,
)
from overrides import override
from typing import List, final
from game.tcg_game import TCGGame
from loguru import logger
from tcg_game_systems.action_bundle import ActionBundle


#######################################################################################################################################
def _generate_actor_plan_prompt(
    current_stage_name: str,
    current_stage_narration: str,
    self_appearence: str,
    actors_info_list: List[str],
) -> str:

    return f"""# 请制定你的行动计划，请确保你的行为和言语符合游戏规则和设定

## 当前所在的场景
{current_stage_name}

### 当前场景描述
{current_stage_narration}

## 你当前的外观特征
{self_appearence}

## 当前场景内除你之外的其他角色的名称与外观特征
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


#######################################################################################################################################
#######################################################################################################################################
def _compress_actor_plan_prompt(
    prompt: str,
) -> str:
    return "# 请做出你的计划，决定你将要做什么，并以 JSON 格式输出。"


#######################################################################################################################################
@final
class ActorRoleplayPlanningSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    #######################################################################################################################################
    @override
    async def a_execute1(self) -> None:
        await self._process_actor_planning_request()

    #######################################################################################################################################
    async def _process_actor_planning_request(self) -> None:

        # 获取所有需要进行角色规划的角色
        actor_entities = self._game.get_group(
            Matcher(
                all_of=[
                    ActorRolePlayPlanningPermitFlagComponent,
                ],
            )
        ).entities

        # 处理角色规划请求
        request_handlers: List[ChatRequestHandler] = self._generate_chat_requests(
            actor_entities
        )

        # 语言服务
        await self._game.langserve_system.gather(request_handlers=request_handlers)

        # 处理角色规划请求
        self._handle_chat_response(request_handlers)

    #######################################################################################################################################
    def _handle_chat_response(self, request_handlers: List[ChatRequestHandler]) -> None:
        for request_handler in request_handlers:
            logger.warning(
                f"Agent: {request_handler._name}, Response:\n{request_handler.response_content}"
            )

            if request_handler.response_content == "":
                continue

            entity2 = self._game.get_entity_by_name(request_handler._name)
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
    def _generate_chat_requests(
        self, actor_entities: set[Entity]
    ) -> List[ChatRequestHandler]:

        request_handlers: List[ChatRequestHandler] = []

        for entity in actor_entities:

            current_stage = self._game.safe_get_stage_entity(entity)
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

            # 生成消息
            message = _generate_actor_plan_prompt(
                current_stage._name,
                current_stage.get(StageEnvironmentComponent).narrate,
                entity.get(FinalAppearanceComponent).final_appearance,
                actors_info_list,
            )

            # 生成请求处理器
            request_handlers.append(
                ChatRequestHandler(
                    name=entity._name,
                    prompt=message,
                    chat_history=self._game.get_agent_short_term_memory(
                        entity
                    ).chat_history,
                )
            )

        return request_handlers

    #######################################################################################################################################
