from loguru import logger
from pydantic import BaseModel
from llm_serves.chat_request_handler import ChatRequestHandler
from entitas import ExecuteProcessor, Entity  # type: ignore
from typing import Dict, List, Optional, Set, final, override
from game.tcg_game import TCGGame
from models_v_0_0_1 import (
    StageEnvironmentComponent,
    CombatRoleComponent,
    StatusEffect,
    CombatKickOffEvent,
)
import format_string.json_format


#######################################################################################################################################
@final
class CombatKickOffResponse(BaseModel):
    description: str
    status_effects: List[StatusEffect]


###################################################################################################################################################################
def _generate_prompt(
    stage_name: str,
    stage_narrate: str,
    actors_apperances_mapping: Dict[str, str],
    temp_combat_attr_component: CombatRoleComponent,
) -> str:

    actors_appearances_info = []
    for actor_name, appearance in actors_apperances_mapping.items():
        actors_appearances_info.append(f"{actor_name}: {appearance}")
    if len(actors_appearances_info) == 0:
        actors_appearances_info.append("无")

    combat_kickoff_response_example = CombatKickOffResponse(
        description="第一人称状态描述（<200字）",
        status_effects=[
            StatusEffect(name="效果1的名字", description="效果1的描述", rounds=1),
            StatusEffect(name="效果2的名字", description="效果2的描述", rounds=2),
        ],
    )

    # 导出战斗属性
    return f"""# 发生事件！战斗触发！请用第一人称描述临场感受。
## 场景信息
{stage_name} ｜ {stage_narrate}
## （场景内）角色信息
{"\n".join(actors_appearances_info)}
## 你的属性（仅在战斗中使用）
{temp_combat_attr_component.attrs_prompt}
## 输出内容
1. 状态感受：单段紧凑自述（禁用换行/空行/数字）
2. 在你身上的持续效果：生成效果列表，包含效果名、效果描述、持续回合数。
## 输出格式规范
{combat_kickoff_response_example.model_dump_json()}
- 直接输出合规JSON"""


###################################################################################################################################################################
@final
class CombatKickOffSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###################################################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    ###################################################################################################################################################################
    @override
    async def a_execute1(self) -> None:

        # step1: 不是本阶段就直接返回
        if not self._game.current_engagement.is_kickoff_phase:
            return

        # step2: 参与战斗的人
        actor_entities = self._extract_actor_entities()
        assert len(actor_entities) > 0
        if len(actor_entities) == 0:
            return  # 人不够就返回。

        # step3: 重置战斗属性! 这个是必须的！
        self._reset_combat_attributes(actor_entities)

        # step4: 处理角色规划请求
        request_handlers: List[ChatRequestHandler] = self._generate_requests(
            actor_entities
        )
        await self._game.chat_system.gather(request_handlers=request_handlers)

        # step5: 处理角色规划请求
        response_map: Dict[ChatRequestHandler, CombatKickOffResponse] = {}
        for request_handler in request_handlers:
            if request_handler.response_content == "":
                continue

            format_response = self._validate_response_format(request_handler)
            if format_response is None:
                logger.error(
                    f"请求处理器返回的内容格式不正确！\n{request_handler._name}:{request_handler.response_content}"
                )
                continue
            response_map[request_handler] = format_response

        # step6: 处理返回结果
        if len(response_map) != len(request_handlers):
            # 如果有角色没有返回结果，就直接返回
            logger.error("有角色没有返回结果！就不允许进入战斗阶段！")
            return

        # step7: 统一处理所有角色的返回结果。
        for request_handler, format_response in response_map.items():
            entity2 = self._game.get_entity_by_name(request_handler._name)
            assert entity2 is not None
            self._handle_response(entity2, request_handler, format_response)

        # final 开始战斗，最后一步，转换到战斗阶段。
        self._game.current_engagement.combat_ongoing()

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
    def _generate_requests(
        self, actor_entities: set[Entity]
    ) -> List[ChatRequestHandler]:

        request_handlers: List[ChatRequestHandler] = []

        for actor_entity in actor_entities:

            assert actor_entity.has(CombatRoleComponent)

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
                actor_entity.get(CombatRoleComponent),
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
    def _validate_response_format(
        self, request_handler: ChatRequestHandler
    ) -> Optional[CombatKickOffResponse]:
        try:
            format_response = CombatKickOffResponse.model_validate_json(
                format_string.json_format.strip_json_code_block(
                    request_handler.response_content
                )
            )
            return format_response
        except Exception as e:
            logger.error(f"Exception: {e}")
            return None

        return None

    ###################################################################################################################################################################
    # 核心处理。
    def _handle_response(
        self,
        entity2: Entity,
        request_handler: ChatRequestHandler,
        format_response: CombatKickOffResponse,
    ) -> None:

        # 效果更新
        self._game.update_combat_status_effects(entity2, format_response.status_effects)

        # 添加提示词上下文。
        self._game.append_human_message(
            entity2,
            request_handler._prompt,
            combat_init_tag="战斗触发！",
        )

        status_effects_prompt = "无"
        if len(format_response.status_effects) > 0:
            status_effects_prompt = "\n".join(
                [e.model_dump_json() for e in format_response.status_effects]
            )

        # 添加记忆
        message = f"""# ！战斗触发！准备完毕。
{format_response.description}
## 目前拥有的状态
{status_effects_prompt}"""

        self._game.append_ai_message(entity2, message)

        # 添加战斗开始事件
        self._game.player.add_agent_event(
            CombatKickOffEvent(
                message=message,
                actor=entity2._name,
                description=format_response.description,
            )
        )


###################################################################################################################################################################
