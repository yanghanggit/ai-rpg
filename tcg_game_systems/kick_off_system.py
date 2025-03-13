from entitas import Entity, Matcher, ExecuteProcessor  # type: ignore
from overrides import override
from components.components import (
    WorldSystemComponent,
    StageComponent,
    ActorComponent,
    KickOffMessageComponent,
    KickOffDoneFlagComponent,
    SystemMessageComponent,
    StageEnvironmentComponent,
)
from typing import Dict, Set, final, List
from game.tcg_game import TCGGame
from loguru import logger
from agent.chat_request_handler import ChatRequestHandler
from components.actions import (
    ACTOR_AVAILABLE_ACTIONS_REGISTER,
    MindVoiceAction,
)
from tcg_game_systems.action_bundle import ActionBundle


###############################################################################################################################################
def _generate_actor_kick_off_prompt(kick_off_message: str, epoch_script: str) -> str:
    return f"""# 游戏启动! 你将开始你的扮演，此时的世界背景如下，请仔细阅读并牢记，以确保你的行为和言语符合游戏设定，不会偏离时代背景。
## 当前世界背景
{epoch_script}
## 你的初始设定与状态
{kick_off_message}
## 输出要求
### 输出格式指南
请严格遵循以下 JSON 结构示例： 
{{
    "{MindVoiceAction.__name__}":["你的内心独白",...], 
}}
### 注意事项
- 所有输出必须为第一人称视角。
- 含有“...”的键可以接收多个值，否则只能接收一个值。
- 输出不得包含超出所需 JSON 格式的其他文本、解释或附加信息。
- 不要使用```json```来封装内容。"""


###############################################################################################################################################
def _generate_stage_kick_off_prompt(
    kick_off_message: str,
    epoch_script: str,
    actor_appearance_mapping: Dict[str, str],
) -> str:

    # 组织一下格式
    actor_descriptions = ["无"]
    if len(actor_appearance_mapping) > 0:
        actor_descriptions = []
        for actor_name, final_appearance in actor_appearance_mapping.items():
            actor_descriptions.append(f"- {actor_name}: {final_appearance}")

    return f"""# 游戏启动! 你将开始你的扮演。
## 世界背景
{epoch_script}
## 初始设定与状态
{kick_off_message}
## 场景内的角色
{"\n".join(actor_descriptions)}
## 输出要求
- 尽量简短。"""


###############################################################################################################################################
def _generate_world_system_kick_off_prompt() -> str:
    return f"""# 游戏启动! # 游戏启动! 你将开始你的扮演，此时的世界背景如下，请仔细阅读并牢记，以确保你的行为和言语符合游戏设定，不会偏离时代背景。
## 请回答你的职能与描述。
## 输出要求
- 尽量简短。"""


###############################################################################################################################################


######################################################################################################################################################
@final
class KickOffSystem(ExecuteProcessor):

    ############################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ######################################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    ######################################################################################################################################################
    @override
    async def a_execute1(self) -> None:

        entities: Set[Entity] = self._game.get_group(
            Matcher(
                all_of=[SystemMessageComponent, KickOffMessageComponent],
                any_of=[ActorComponent, WorldSystemComponent, StageComponent],
                none_of=[KickOffDoneFlagComponent],
            )
        ).entities.copy()

        if len(entities) == 0:
            return

        # 添加系统消息
        self._add_system_message(entities)

        # 处理请求
        await self._process_kick_off_request(entities)

    ######################################################################################################################################################
    async def _process_kick_off_request(self, entities: Set[Entity]) -> None:

        # 添加请求处理器
        request_handlers: List[ChatRequestHandler] = []

        for entity1 in entities:
            # 不同实体生成不同的提示
            gen_prompt = self._generate_kick_off_prompt(entity1)
            # assert gen_prompt is not ""
            if gen_prompt == "":
                continue

            agent_short_term_memory = self._game.get_agent_short_term_memory(entity1)
            request_handlers.append(
                ChatRequestHandler(
                    name=entity1._name,
                    prompt=gen_prompt,
                    chat_history=agent_short_term_memory.chat_history,
                )
            )

        # 并发
        await self._game.langserve_system.gather(request_handlers=request_handlers)

        # 添加上下文。
        for request_handler in request_handlers:

            entity2 = self._game.get_entity_by_name(request_handler._name)
            assert entity2 is not None

            if request_handler.response_content == "":
                logger.error(
                    f"Agent: {request_handler._name}, Response is empty!!!!!!!!!!!!!!!!!!!!!!!!! KickOff Failed."
                )
                continue

            logger.warning(
                f"Agent: {request_handler._name}, Response:\n{request_handler.response_content}"
            )

            self._game.append_human_message(entity2, request_handler._prompt)
            self._game.append_ai_message(entity2, request_handler.response_content)

            # 必须执行
            entity2.replace(KickOffDoneFlagComponent, entity2._name)

            # 若是场景，用response替换narrate
            if entity2.has(StageComponent):
                entity2.replace(
                    StageEnvironmentComponent,
                    entity2._name,
                    request_handler.response_content,
                )
            elif entity2.has(ActorComponent):
                # 添加行动
                self._allocate_actor_actions(entity2, request_handler.response_content)

    ######################################################################################################################################################
    def _allocate_actor_actions(self, entity: Entity, response_content: str) -> None:

        assert response_content != ""
        assert entity.has(ActorComponent)
        action_bundle = ActionBundle(entity._name, response_content)
        if not action_bundle.assign_actions_to_entity(
            entity, ACTOR_AVAILABLE_ACTIONS_REGISTER
        ):
            assert False, "Assign action failed."

    ######################################################################################################################################################
    def _generate_kick_off_prompt(self, entity: Entity) -> str:

        kick_off_message_comp = entity.get(KickOffMessageComponent)
        assert kick_off_message_comp is not None
        kick_off_message = kick_off_message_comp.content

        # 不同实体生成不同的提示
        gen_prompt = ""
        if entity.has(ActorComponent):
            # 角色的
            gen_prompt = _generate_actor_kick_off_prompt(
                kick_off_message, self._game.world.boot.epoch_script
            )
        elif entity.has(StageComponent):
            # 舞台的
            actors_appearance_on_stage = (
                self._game.retrieve_actor_appearance_on_stage_mapping(entity)
            )
            gen_prompt = _generate_stage_kick_off_prompt(
                kick_off_message,
                self._game.world.boot.epoch_script,
                actors_appearance_on_stage,
            )
        elif entity.has(WorldSystemComponent):
            # 世界系统的
            gen_prompt = _generate_world_system_kick_off_prompt()

        return gen_prompt

    ######################################################################################################################################################
    def _add_system_message(self, entities: Set[Entity]) -> None:
        for entity in entities:
            system_message_comp = entity.get(SystemMessageComponent)
            assert system_message_comp is not None
            self._game.append_system_message(entity, system_message_comp.content)

    ######################################################################################################################################################
