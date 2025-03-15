from entitas import ExecuteProcessor  # type: ignore
from agent.chat_request_handler import ChatRequestHandler
from overrides import override
from typing import List, Tuple, final
from game.tcg_game import TCGGame
from loguru import logger
from tcg_models.v_0_0_1 import Skill
from components.actions2 import SkillAction2


#######################################################################################################################################
def _generate_execute_skills_prompt(execute_list: List[Tuple[str, Skill]]) -> str:

    skill_infos: List[str] = []
    for actor_name, skill in execute_list:
        skill_infos.append(
            f"""### {actor_name} : {skill.name}。
- 技能描述: {skill.description}
- 技能效果: {skill.effect}"""
        )

    return f"""# 将要执行一次战斗行动。请根据输入的信息来做演绎。
## 技能信息
{"\n".join(skill_infos)}
## 技能执行顺序
{" -> ".join([actor_name for actor_name, _ in execute_list])}
## 输出要求
- 输出一整段文字来描述你的演绎。
- 不要使用换行与空行。"""


#######################################################################################################################################
@final
class ExecuteSkillSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    #######################################################################################################################################
    @override
    async def a_execute1(self) -> None:
        await self._process_request()

    #######################################################################################################################################
    async def _process_request(self) -> None:
        assert len(self._game._round_action_order) > 0
        if len(self._game._round_action_order) == 0:
            return

        execute_list: List[Tuple[str, Skill]] = []
        for actor_name in self._game._round_action_order:

            actor_entity = self._game.get_entity_by_name(actor_name)
            assert actor_entity is not None

            skill_action2 = actor_entity.get(SkillAction2)
            if skill_action2 is None:
                continue

            execute_list.append((skill_action2.name, skill_action2.skill))

        #
        entity = self._game.get_entity_by_name(execute_list[0][0])
        assert entity is not None
        current_stage = self._game.safe_get_stage_entity(entity)
        assert current_stage is not None

        #
        message = _generate_execute_skills_prompt(execute_list)

        # 用场景推理。
        request_handler = ChatRequestHandler(
            name=current_stage._name,
            prompt=message,
            chat_history=self._game.get_agent_short_term_memory(
                current_stage
            ).chat_history,
        )

        #
        await self._game.langserve_system.gather(request_handlers=[request_handler])

        #
        if request_handler.response_content == "":
            logger.error(f"Agent: {request_handler._name}, Response is empty.")
            return

        self._handle_response(request_handler)

    #######################################################################################################################################
    def _handle_response(self, request_handler: ChatRequestHandler) -> None:

        try:
            logger.info(f"Agent, Response = \n{request_handler.response_content}")

        except:
            logger.error(
                f"""返回格式错误, Response = \n{request_handler.response_content}"""
            )

    #######################################################################################################################################
