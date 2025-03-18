from entitas import Entity, Matcher, GroupEvent  # type: ignore
from agent.chat_request_handler import ChatRequestHandler
from overrides import override
from typing import List, final
from loguru import logger
from components.actions2 import DirectorAction2, FeedbackAction2
from rpg_models.event_models import AgentEvent
from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem
from tcg_models.v_0_0_1 import ActorInstance


#######################################################################################################################################
def _generate_execute_skills_prompt(
    actions_list: List[DirectorAction2], actor_instances: List[ActorInstance]
) -> str:

    skill_execution_details: List[str] = []
    for skill_action in actions_list:
        for actor_instance in actor_instances:
            if actor_instance.name != skill_action.name:
                continue

            export_combat_attr = actor_instance.base_attributes.export_combat_attrs()

            detail = f"""### {actor_instance.name} 
**{skill_action.skill.name}**
- 目标: {skill_action.targets}
- 技能描述: {skill_action.skill.description}
- 技能效果: {skill_action.skill.effect}
**属性**
- 当前生命: {actor_instance.hp}
- 最大生命: {export_combat_attr.max_hp}
- 物理攻击: {export_combat_attr.physical_attack}
- 物理防御: {export_combat_attr.physical_defense}
- 魔法攻击: {export_combat_attr.magic_attack}
- 魔法防御: {export_combat_attr.magic_defense}"""

            skill_execution_details.append(detail)

    return f"""# 将要执行一次战斗行动。请根据输入的信息来做推理与演绎。
## 技能执行详情
{"\n".join(skill_execution_details)}
## 技能执行顺序
{" -> ".join([action.name for action in actions_list])}
### 注意顺序
- 排在后面的技能会在前面的技能执行完毕后再执行！
## 输出要求
- 输出一整段文字来描述你的演绎。
- 需要描述计算过程与结果。
- 不要使用换行与空行。"""


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
    async def _process_request(self, react_entities: List[Entity]) -> None:

        skill_actions: List[DirectorAction2] = []
        for entity in react_entities:
            skill_action2 = entity.get(DirectorAction2)
            assert skill_action2 is not None
            skill_actions.append(skill_action2)

        current_stage = self._game.safe_get_stage_entity(react_entities[0])
        assert current_stage is not None

        # 临时
        all_actor_instances = (
            self._game._world.boot.actors + self._game._world.boot.players
        )

        message = _generate_execute_skills_prompt(skill_actions, all_actor_instances)

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
