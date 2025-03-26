from loguru import logger
from pydantic import BaseModel
from extended_systems.chat_request_handler import ChatRequestHandler
from entitas import ExecuteProcessor, Entity  # type: ignore
from typing import Dict, List, Set, final, override
from game.tcg_game import TCGGame
from components.components_v_0_0_1 import (
    StageEnvironmentComponent,
    CombatAttributesComponent,
)
import format_string.json_format
from models.v_0_0_1 import Effect


#######################################################################################################################################
@final
class CombatPreparationResponse(BaseModel):
    description: str
    effects: List[Effect]


###################################################################################################################################################################
def _generate_prompt(
    stage_name: str,
    stage_narrate: str,
    actors_apperances_mapping: Dict[str, str],
    temp_combat_attr_component: CombatAttributesComponent,
) -> str:

    actors_appearances_info = []
    for actor_name, appearance in actors_apperances_mapping.items():
        actors_appearances_info.append(f"{actor_name}: {appearance}")
    if len(actors_appearances_info) == 0:
        actors_appearances_info.append("无")

    combat_init_response_example = CombatPreparationResponse(
        description="第一人称状态描述（<200字）",
        effects=[
            Effect(name="效果1的名字", description="效果1的描述", rounds=1),
            Effect(name="效果2的名字", description="效果2的描述", rounds=2),
        ],
    )

    # 导出战斗属性
    return f"""# 发生事件！战斗触发！请用第一人称描述临场感受。
## 场景信息
{stage_name} ｜ {stage_narrate}
## （场景内）角色信息
{"\n".join(actors_appearances_info)}
## 你的属性（仅在战斗中使用）
{temp_combat_attr_component.as_prompt}
## 输出内容
1. 状态感受：单段紧凑自述（禁用换行/空行/数字）
2. 在你身上的持续效果：生成效果列表，包含效果名、效果描述、持续回合数。
## 输出格式规范
{combat_init_response_example.model_dump_json()}
- 直接输出合规JSON"""


###################################################################################################################################################################
@final
class DungeonCombatPreparationSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###################################################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    ###################################################################################################################################################################
    @override
    async def a_execute1(self) -> None:

        if not self._game.combat_system.is_preparation_phase:
            # 不是本阶段就直接返回
            return

        actor_entities = self._extract_actor_entities()
        assert len(actor_entities) > 0
        if len(actor_entities) == 0:
            return

        # 重置战斗属性! 这个是必须的！
        self._reset_combat_attributes(actor_entities)

        # 核心处理
        await self._process_chat_requests(actor_entities)

        # 开始战斗
        self._game.combat_system.combat_go()

    ###################################################################################################################################################################
    # 所有参与战斗的角色！
    def _extract_actor_entities(self) -> Set[Entity]:
        player_entity = self._game.get_player_entity()
        assert player_entity is not None
        return self._game.retrieve_actors_on_stage(player_entity)

    ###################################################################################################################################################################
    def _reset_combat_attributes(self, actor_entities: Set[Entity]) -> None:

        for actor_entity in actor_entities:
            self._game.setup_combat_attributes(actor_entity)

    ###################################################################################################################################################################
    async def _process_chat_requests(self, actor_entities: Set[Entity]) -> None:

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

        for actor_entity in actor_entities:

            assert actor_entity.has(CombatAttributesComponent)

            current_stage = self._game.safe_get_stage_entity(actor_entity)
            assert current_stage is not None

            # 找到当前场景内所有角色
            actors_apperances_mapping = (
                self._game.retrieve_actor_appearance_on_stage_mapping(current_stage)
            )
            actors_apperances_mapping.pop(actor_entity._name, None)

            # 生成消息
            message = _generate_prompt(
                current_stage._name,
                current_stage.get(StageEnvironmentComponent).narrate,
                actors_apperances_mapping,
                actor_entity.get(CombatAttributesComponent),
            )

            # 生成请求处理器
            request_handlers.append(
                ChatRequestHandler(
                    name=actor_entity._name,
                    prompt=message,
                    chat_history=self._game.get_agent_short_term_memory(
                        actor_entity
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

            self._handle_actor_response(entity2, request_handler)

    ###################################################################################################################################################################
    def _handle_actor_response(
        self, entity2: Entity, request_handler: ChatRequestHandler
    ) -> None:

        # 核心处理
        try:

            format_response = CombatPreparationResponse.model_validate_json(
                format_string.json_format.strip_json_code_block(
                    request_handler.response_content
                )
            )

            logger.info(
                f"Agent: {entity2._name}, Response = {format_response.model_dump_json()}"
            )

            # 效果更新
            self._game.update_combat_effects(entity2, format_response.effects)

            # 添加提示词上下文。
            self._game.append_human_message(
                entity2,
                request_handler._prompt,
                combat_init_tag="战斗触发！",
            )

            # 添加记忆
            message = f"""# ！战斗触发！准备完毕。
{format_response.description}
## 你目前拥有的状态
{'\n'.join([e.model_dump_json() for e in format_response.effects])}"""

            self._game.append_ai_message(entity2, message)

        except:
            logger.error(
                f"""返回格式错误: {entity2._name}, Response = \n{request_handler.response_content}"""
            )

    ###################################################################################################################################################################
