from pydantic import BaseModel
from entitas import Entity, Matcher, GroupEvent  # type: ignore
from extended_systems.chat_request_handler import ChatRequestHandler
from overrides import override
from typing import List, Tuple, final
from loguru import logger
from components.actions2 import FeedbackAction2
from extended_systems.combat_system import CombatState
from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem
from tcg_models.v_0_0_1 import Effect
import format_string.json_format
from components.components import CombatAttributesComponent, CombatEffectsComponent


#######################################################################################################################################
@final
class FeedbackResponse(BaseModel):
    description: str
    hp: float
    max_hp: float
    effects: List[Effect]


#######################################################################################################################################
def _generate_prompt(
    combat_attributes_component: CombatAttributesComponent,
    feedback_component: FeedbackAction2,
) -> str:

    feedback_response_example = FeedbackResponse(
        description="第一人称状态描述（<200字）",
        hp=combat_attributes_component.hp,
        max_hp=combat_attributes_component.max_hp,
        effects=[
            Effect(name="效果1的名字", description="效果1的描述", rounds=1),
            Effect(name="效果2的名字", description="效果2的描述", rounds=2),
        ],
    )

    return f"""# 提示！根据战斗结果，更新状态并反馈！(仅反馈你自身状态)
## 战斗结果

### 计算摘要
{feedback_component.calculation}

### 演绎摘要
{feedback_component.performance}

## 输出内容
1. 状态感受：单段紧凑自述（禁用换行/空行）
3. 生命值：根据‘战斗结果-计算摘要’，更新hp/max_hp。
2. 在你身上的持续效果：生成效果列表，包含效果名、效果描述、剩余回合数。
    
## 输出格式规范
{feedback_response_example.model_dump_json()}
- 数值精确，禁用文字修饰。
- 直接输出合规JSON"""


#######################################################################################################################################
@final
class FeedbackActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(FeedbackAction2): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(FeedbackAction2)

    #######################################################################################################################################
    @override
    async def a_execute2(self) -> None:
        if len(self._react_entities_copy) > 0:

            assert (
                self._game.combat_system.latest_combat.current_state
                == CombatState.RUNNING
            )
            await self._process_request(self._react_entities_copy)

    #######################################################################################################################################
    async def _process_request(self, react_entities: List[Entity]) -> None:

        #
        chat_requests = self._generate_chat_requests(set(react_entities))

        # 用语言服务系统进行推理。
        await self._game.langserve_system.gather(request_handlers=chat_requests)

        # 处理返回结果。
        self._handle_chat_responses(chat_requests)

    #######################################################################################################################################
    def _handle_chat_responses(
        self, request_handlers: List[ChatRequestHandler]
    ) -> None:

        for request_handler in request_handlers:

            if request_handler.response_content == "":
                logger.error(f"Agent: {request_handler._name}, Response is empty.")
                continue

            entity2 = self._game.get_entity_by_name(request_handler._name)
            assert entity2 is not None
            self._handle_response(entity2, request_handler)

    #######################################################################################################################################
    def _handle_response(
        self, entity: Entity, request_handler: ChatRequestHandler
    ) -> None:

        try:

            format_response = FeedbackResponse.model_validate_json(
                format_string.json_format.strip_json_code_block(
                    request_handler.response_content
                )
            )

            logger.info(
                f"Agent: {entity._name}, Response = {format_response.model_dump_json()}"
            )

            # 血量更新
            self.update_combat_health(
                entity, format_response.hp, format_response.max_hp
            )

            # 效果更新
            self._game.refresh_combat_effects(entity, format_response.effects)

            # 效果扣除
            remaining_effects, removed_effects = self.update_combat_remaining_effects(
                entity
            )

            remaining_effects_prompt = "无"
            if len(remaining_effects) > 0:
                remaining_effects_prompt = "\n".join(
                    [e.model_dump_json() for e in remaining_effects]
                )

            removed_effects_prompt = "无"
            if len(removed_effects) > 0:
                removed_effects_prompt = "\n".join(
                    [e.model_dump_json() for e in removed_effects]
                )

            # 添加记忆
            message = f"""# 你的状态更新，请注意！
{format_response.description}
生命值：{format_response.hp}/{format_response.max_hp}
持续效果：
{remaining_effects_prompt}
失效效果：
{removed_effects_prompt}"""

            self._game.append_human_message(entity, message)

        except:
            logger.error(
                f"""返回格式错误, Response = \n{request_handler.response_content}"""
            )

    #######################################################################################################################################
    def _generate_chat_requests(
        self, actor_entities: set[Entity]
    ) -> List[ChatRequestHandler]:

        request_handlers: List[ChatRequestHandler] = []

        for entity in actor_entities:

            feedback_action2 = entity.get(FeedbackAction2)

            combat_attributes_component = entity.get(CombatAttributesComponent)
            assert combat_attributes_component is not None

            # 生成消息
            message = _generate_prompt(combat_attributes_component, feedback_action2)
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
    # 状态效果扣除。
    def update_combat_remaining_effects(
        self, entity: Entity
    ) -> Tuple[List[Effect], List[Effect]]:

        # 效果更新
        assert entity.has(CombatEffectsComponent)
        combat_effects_comp = entity.get(CombatEffectsComponent)
        assert combat_effects_comp is not None

        current_effects = combat_effects_comp.effects.copy()
        remaining_effects = []
        removed_effects = []
        for i, e in enumerate(current_effects):
            current_effects[i].rounds -= 1
            current_effects[i].rounds = max(0, current_effects[i].rounds)

            if current_effects[i].rounds > 0:
                remaining_effects.append(current_effects[i])
            else:
                removed_effects.append(current_effects[i])

        entity.replace(
            CombatEffectsComponent, combat_effects_comp.name, remaining_effects
        )

        return remaining_effects, removed_effects

    ###############################################################################################################################################
    def update_combat_health(self, entity: Entity, hp: float, max_hp: float) -> None:

        combat_attributes_comp = entity.get(CombatAttributesComponent)
        assert combat_attributes_comp is not None

        entity.replace(
            CombatAttributesComponent,
            combat_attributes_comp.name,
            hp,
            max_hp,
            combat_attributes_comp.physical_attack,
            combat_attributes_comp.physical_defense,
            combat_attributes_comp.magic_attack,
            combat_attributes_comp.magic_defense,
        )

    ###############################################################################################################################################
