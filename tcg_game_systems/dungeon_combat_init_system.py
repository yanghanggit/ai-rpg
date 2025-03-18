from loguru import logger
from agent.chat_request_handler import ChatRequestHandler
from entitas import ExecuteProcessor, Matcher, Entity  # type: ignore
from typing import List, final, override
from game.tcg_game import TCGGame
from components.components import ActorComponent, StageEnvironmentComponent
from components.actions2 import (
    CandidateAction2,
)
from extended_systems.combat_system import CombatSystem, CombatState


# combat_system = self._game.combat_system.current_combat()
# match(combat_system.current_state):
#     case CombatState.INIT:
#         self._process()
#     case _:
#         assert False, f"未知的状态 = {combat_system.current_state}"

# self._game._round_number = self._game._round_number + 1

# entities2 = self._game.get_group(
#     Matcher(
#         all_of=[
#             ActorComponent,
#         ],
#     )
# ).entities

# for actor_entity in entities2:

#     break

#     stage_entity = self._game.safe_get_stage_entity(actor_entity)
#     assert stage_entity is not None

#     self._game.append_human_message(
#         entity=actor_entity,
#         chat=f"# 提示！战斗回合开始 = {self._game._round_number}",
#         tag=f"battle:{stage_entity._name}:{self._game._round_number}",
#     )

#     actor_entity.replace(CandidateAction2, actor_entity._name)


###################################################################################################################################################################
def _generate_prompt(
    stage_name: str,
    stage_narrate: str,
    actors_apperances_mapping: dict[str, str],
) -> str:

    actors_appearances_info = []
    for actor_name, appearance in actors_apperances_mapping.items():
        actors_appearances_info.append(f"{actor_name}: {appearance}")
    if len(actors_appearances_info) == 0:
        actors_appearances_info.append("无")

    return f"""# 发生事件！一场战斗即将开始！请说一下你的感受！
## 当前场景
{stage_name}
### 场景描述
{stage_narrate}
## 场景内角色
{"\n".join(actors_appearances_info)}
## 输出要求
- 引用角色或场景时，请严格遵守全名机制
- 以第一人称视角，一整段话来描述，不要换行或折行。
- 输出字数尽量简短。"""


###################################################################################################################################################################
@final
class DungeonCombatInitSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###################################################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    ###################################################################################################################################################################
    @override
    async def a_execute1(self) -> None:

        if self._game.combat_system.current_combat.current_state != CombatState.INIT:
            # 不是本阶段就直接返回
            return

        # 核心处理
        await self._process_chat_requests()

        # 开始战斗
        self._game.combat_system.current_combat.start_combat()

    ###################################################################################################################################################################
    def _extract_actor_entities(self) -> set[Entity]:

        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        actors_on_stage = self._game.retrieve_actors_on_stage(player_entity)
        return actors_on_stage

    ###################################################################################################################################################################
    async def _process_chat_requests(self) -> None:

        actor_entities = self._extract_actor_entities()
        assert len(actor_entities) > 0
        if len(actor_entities) == 0:
            return

        # 处理角色规划请求
        request_handlers: List[ChatRequestHandler] = self._generate_chat_requests(
            actor_entities
        )

        # 语言服务
        await self._game.langserve_system.gather(request_handlers=request_handlers)

        # 处理角色规划请求
        self._handle_chat_responses(request_handlers)

    ###################################################################################################################################################################
    def _generate_chat_requests(
        self, actor_entities: set[Entity]
    ) -> List[ChatRequestHandler]:

        request_handlers: List[ChatRequestHandler] = []

        for entity in actor_entities:

            current_stage = self._game.safe_get_stage_entity(entity)
            assert current_stage is not None

            # 找到当前场景内所有角色
            actors_apperances_mapping = (
                self._game.retrieve_actor_appearance_on_stage_mapping(current_stage)
            )
            actors_apperances_mapping.pop(entity._name, None)

            # 生成消息
            message = _generate_prompt(
                current_stage._name,
                current_stage.get(StageEnvironmentComponent).narrate,
                actors_apperances_mapping,
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

    ###################################################################################################################################################################
    def _handle_chat_responses(
        self, request_handlers: List[ChatRequestHandler]
    ) -> None:
        for request_handler in request_handlers:

            entity2 = self._game.get_entity_by_name(request_handler._name)
            assert entity2 is not None

            if request_handler.response_content == "":
                logger.error(f"Agent: {request_handler._name}, Response is empty.")
                continue

            logger.warning(
                f"Agent: {request_handler._name}, Response:\n{request_handler.response_content}"
            )

            self._handle_actor_response(entity2, request_handler)

    ###################################################################################################################################################################
    def _handle_actor_response(
        self, entity2: Entity, request_handler: ChatRequestHandler
    ) -> None:

        # 核心处理
        try:
            # 添加上下文。
            self._game.append_human_message(entity2, request_handler._prompt)
            self._game.append_ai_message(entity2, request_handler.response_content)

        except:
            logger.error(
                f"""返回格式错误: {entity2._name}, Response = \n{request_handler.response_content}"""
            )

    ###################################################################################################################################################################
