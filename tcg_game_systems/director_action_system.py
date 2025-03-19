from pydantic import BaseModel
from entitas import Entity, Matcher, GroupEvent  # type: ignore
from agent.chat_request_handler import ChatRequestHandler
from overrides import override
from typing import List, NamedTuple, final
from loguru import logger
from components.actions2 import DirectorAction2, FeedbackAction2
from rpg_models.event_models import AgentEvent
from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem
from tcg_models.v_0_0_1 import Skill
from components.components import CombatAttributesComponent


#######################################################################################################################################
@final
class DirectorResponse(BaseModel):
    calculation: str
    performance: str


#######################################################################################################################################
@final
class ActionPromptParameters(NamedTuple):
    actor: str
    targets: List[str]
    skill: Skill
    temp_combat_attrs_component: CombatAttributesComponent


#######################################################################################################################################
def _generate_director_prompt(prompt_params: List[ActionPromptParameters]) -> str:

    details_prompt: List[str] = []
    for param in prompt_params:

        detail = f"""{param.actor} 
技能: {param.skill.name}
目标: {param.targets}
描述: {param.skill.description}
效果: {param.skill.effect}
{param.temp_combat_attrs_component.gen_prompt}"""

        details_prompt.append(detail)

    # 模版
    director_response_sample = DirectorResponse(
        calculation="简明战斗计算（含最终生命值）", performance="生动的文学化演绎"
    )

    return f"""# 提示！回合行动指令。根据下列信息执行战斗回合：
## 角色行动序列（后续技能在前序执行后生效）
{" -> ".join([param.actor for param in prompt_params])}
## 角色&技能详情
{"\n".join(details_prompt)}
## 输出内容
1. 计算过程（<200字）
    - 根据‘战斗规则’说明计算过程。
    - 精确简练，明确最终生命值。
2. 演绎过程（~200字）
    - 文学化描写，禁用数字与计算过程
## 输出格式规范
{director_response_sample.model_dump_json()}
- 禁用换行/空行
- 直接输出合规JSON"""


#######################################################################################################################################
@final
class DirectorActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(DirectorAction2): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(DirectorAction2)

    #######################################################################################################################################
    @override
    async def a_execute2(self) -> None:

        if len(self._react_entities_copy) == 0:
            return

        if len(self._game.combat_system.latest_combat.latest_round.turns) == 0:
            return

        # 将self._react_entities_copy以self._game._round_action_order的顺序进行重新排序
        self._react_entities_copy.sort(
            key=lambda entity: self._game.combat_system.latest_combat.latest_round.turns.index(
                entity._name
            )
        )

        await self._process_request(self._react_entities_copy)

    #######################################################################################################################################
    def _generate_action_prompt_parameters(
        self, react_entities: List[Entity]
    ) -> List[ActionPromptParameters]:

        ret: List[ActionPromptParameters] = []
        for entity in react_entities:

            skill_action2 = entity.get(DirectorAction2)
            assert skill_action2 is not None

            assert entity.has(CombatAttributesComponent)
            ret.append(
                ActionPromptParameters(
                    actor=entity._name,
                    targets=skill_action2.targets,
                    skill=skill_action2.skill,
                    temp_combat_attrs_component=entity.get(CombatAttributesComponent),
                )
            )

        return ret

    #######################################################################################################################################
    async def _process_request(self, react_entities: List[Entity]) -> None:

        # 用场景来推理
        current_stage = self._game.safe_get_stage_entity(react_entities[0])
        assert current_stage is not None

        # 生成推理参数。
        params = self._generate_action_prompt_parameters(react_entities)
        assert len(params) > 0

        # 生成推理信息。
        message = _generate_director_prompt(params)

        # 用场景推理。
        request_handler = ChatRequestHandler(
            name=current_stage._name,
            prompt=message,
            chat_history=self._game.get_agent_short_term_memory(
                current_stage
            ).chat_history,
        )

        # 用语言服务系统进行推理。
        await self._game.langserve_system.gather(request_handlers=[request_handler])

        # 处理返回结果。
        if request_handler.response_content == "":
            logger.error(f"Agent: {request_handler._name}, Response is empty.")
            return

        # 处理返回结果。
        self._handle_response(request_handler)

    #######################################################################################################################################
    def _handle_response(self, request_handler: ChatRequestHandler) -> None:

        try:

            current_stage = self._game.get_entity_by_name(request_handler._name)
            assert current_stage is not None

            logger.warning(
                f"返回格式正确, Response = \n{request_handler.response_content}"
            )

            # 发送事件。
            self._game.broadcast_event(
                entity=current_stage,
                agent_event=AgentEvent(
                    message=f"# 发生事件！\n{request_handler.response_content}",
                ),
            )

            #
            actors_on_stage = self._game.retrieve_actors_on_stage(current_stage)
            for actor_entity in actors_on_stage:
                actor_entity.replace(FeedbackAction2, actor_entity._name)

        except:
            logger.error(
                f"""返回格式错误, Response = \n{request_handler.response_content}"""
            )

    #######################################################################################################################################
