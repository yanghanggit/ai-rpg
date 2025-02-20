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
    KickOffFlagComponent,
    PlayerComponent,
    StageComponent,
    StageEnvironmentComponent,
    FinalAppearanceComponent,
)
from entitas import ExecuteProcessor, Matcher  # type: ignore
from overrides import override
from typing import List, final, cast
from game.tcg_game_context import TCGGameContext
from game.tcg_game import TCGGame
from loguru import logger
from tcg_game_systems.action_bundle import ActionBundle
from run_terminal_tcg_game import Counter


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
                    ActorComponent,
                    KickOffFlagComponent,
                ],
                # none_of=[PlayerComponent], TODO, For Test
            )
        ).entities.copy()

        # 获取玩家所在stage，随后剔除不在玩家所在场景内的actor TODO，有了strategy后删掉
        player_entity = self._game.get_player_entity()
        assert player_entity is not None
        player_stage = self._context.safe_get_stage_entity(player_entity)
        actor_entities = {
            entity
            for entity in actor_entities
            if self._context.safe_get_stage_entity(entity) == player_stage
        }

        if len(actor_entities) == 0:
            return

        request_handlers: List[ChatRequestHandler] = []

        # 为了测试交叉对话，后面需要改成其他方式,TODO
        Counter.add()
        for entity in actor_entities:
            if Counter.get() % 2 == 0 and entity._name != "角色.战士.凯尔":
                continue
            if Counter.get() % 2 != 0 and entity._name != "角色.怪物.哥布林小队":
                continue

            # 找到当前场景
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
                self._game.world_runtime.root.epoch_script,
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
            # self._game.append_human_message(entity2, request_handler._prompt)
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
    epoch_script: str,
    current_stage_name: str,
    current_stage_narration: str,
    self_appearence: str,
    actors_info_list: List[str],
) -> str:
    assert current_stage_name is not "", "current_stage is empty"
    return f"""
# 请制定你的行动计划，此时的世界背景及场景信息如下，请仔细阅读并牢记，以确保你的行为和言语符合游戏设定，不会偏离时代背景。

## 游戏规则
### 全名机制：
游戏中的角色、道具、场景等都有全名，全名是游戏系统中的唯一标识符。
名字可以由多个单词组成，单词之间用英文句号`.`分隔。例如：角色.战士.凯尔。
注意请完整引用全名以确保一致性。

## 当前游戏背景
{epoch_script}

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
