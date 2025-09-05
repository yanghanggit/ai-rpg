from typing import Dict, List, Optional, Set, final, override

from langchain.schema import AIMessage
from loguru import logger
from pydantic import BaseModel

from ..chat_services.client import ChatClient
from ..entitas import Entity, ExecuteProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    CombatKickOffEvent,
    EnvironmentComponent,
    PlayerComponent,
    RPGCharacterProfileComponent,
    StatusEffect,
)
from ..utils import json_format


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
    rpg_character_profile_component: RPGCharacterProfileComponent,
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
{rpg_character_profile_component.attrs_prompt}
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
    async def execute(self) -> None:

        # step1: 不是本阶段就直接返回
        if not self._game.current_engagement.is_kickoff_phase:
            return

        # step2: 参与战斗的人
        actor_entities = self._extract_actor_entities()
        assert len(actor_entities) > 0
        if len(actor_entities) == 0:
            return  # 人不够就返回。

        # step4: 处理角色规划请求
        request_handlers: List[ChatClient] = self._generate_requests(actor_entities)
        await self._game.chat_system.gather(request_handlers=request_handlers)

        # step5: 处理角色规划请求
        response_map: Dict[ChatClient, CombatKickOffResponse] = {}
        for request_handler in request_handlers:
            # if request_handler.last_message_content == "":
            #     continue

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
    # def _reset_combat_attributes(self, actor_entities: Set[Entity]) -> None:
    #     for actor_entity in actor_entities:
    #         self._game.initialize_combat_components(actor_entity)

    ###################################################################################################################################################################
    def _generate_requests(self, actor_entities: set[Entity]) -> List[ChatClient]:

        request_handlers: List[ChatClient] = []

        for actor_entity in actor_entities:

            assert actor_entity.has(RPGCharacterProfileComponent)

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
                current_stage.get(EnvironmentComponent).narrate,
                actors_apperances_mapping,
                actor_entity.get(RPGCharacterProfileComponent),
            )

            # 生成请求处理器
            request_handlers.append(
                ChatClient(
                    agent_name=actor_entity._name,
                    prompt=message,
                    chat_history=self._game.get_agent_short_term_memory(
                        actor_entity
                    ).chat_history,
                )
            )

        return request_handlers

    ###################################################################################################################################################################
    def _validate_response_format(
        self, request_handler: ChatClient
    ) -> Optional[CombatKickOffResponse]:
        try:
            format_response = CombatKickOffResponse.model_validate_json(
                json_format.strip_json_code_block(request_handler.response_content)
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
        request_handler: ChatClient,
        format_response: CombatKickOffResponse,
    ) -> None:

        # 效果更新
        self._game.apply_status_effects(entity2, format_response.status_effects)

        # 添加提示词上下文。

        stage_entity = self._game.safe_get_stage_entity(entity2)
        assert stage_entity is not None
        self._game.append_human_message(
            entity2,
            request_handler._prompt,
            combat_kickoff_tag=stage_entity._name,
        )

        status_effects_prompt = "无"
        if len(format_response.status_effects) > 0:
            status_effects_prompt = "\n".join(
                [e.model_dump_json() for e in format_response.status_effects]
            )

        # 添加记忆 TODO，临时这么写吧，不然就得改interface了。
        ai_message_content = f"""# ！战斗触发！准备完毕。
{format_response.description}
## 目前拥有的状态
{status_effects_prompt}"""

        self._game.append_ai_message(entity2, [AIMessage(content=ai_message_content)])

        # TODO，临时这么写吧，不用notify了，因为里面会append_human_message，等于重复了。后续再优化。
        if entity2.has(PlayerComponent):
            # 添加战斗开始事件
            self._game.player.add_agent_event(
                # entity2,
                CombatKickOffEvent(
                    message=ai_message_content,
                    actor=entity2._name,
                    description=format_response.description,
                ),
            )


###################################################################################################################################################################
