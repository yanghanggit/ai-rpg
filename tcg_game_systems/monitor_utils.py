from entitas import Entity  # type: ignore
from typing import Dict, List, Set, Union, final
from models.components_v_0_0_1 import StageComponent, ActorComponent
from extended_systems.chat_request_handler import ChatRequestHandler
from loguru import logger
from pydantic import BaseModel
import format_string.json_format
from game.tcg_game import TCGGame
from models.dungeon_v_0_0_1 import StatusEffect


# 用于Stage生成请求的数据格式
@final
class StageResponse(BaseModel):
    narrate: str = ""
    actors: List[str] = []


# 用于Actor生成请求的数据格式
@final
class ActorResponse(BaseModel):
    stage: str = ""
    actors: List[str] = []
    status_effects: List[StatusEffect] = []


@final
class MonitorUtils:

    ####################################################################################################################################
    def __init__(
        self,
        game_context: TCGGame,
        stage_entities: Set[Entity],
        actor_entities: Set[Entity],
    ) -> None:

        self._game = game_context

        self._stage_entities = stage_entities
        assert all([entity.has(StageComponent) for entity in stage_entities])

        self._actor_entities = actor_entities
        assert all([entity.has(ActorComponent) for entity in actor_entities])

        self._request_handlers: list[ChatRequestHandler] = []

        self._result_mapping: Dict[Entity, Union[StageResponse, ActorResponse]] = {}

    ####################################################################################################################################
    async def process(self) -> None:

        # 合并一下 request 任务。
        self._request_handlers = self._gen_actors_requests(
            self._actor_entities
        ) + self._gen_stages_requests(self._stage_entities)

        # 并发执行。
        await self._game.langserve_system.gather(
            request_handlers=self._request_handlers
        )

        # 后续处理
        for request_handler in self._request_handlers:

            if request_handler.response_content == "":
                continue

            entity2 = self._game.get_entity_by_name(request_handler._name)
            assert entity2 is not None

            # 分开处理
            if entity2.has(StageComponent):
                # 处理场景
                self._handle_stage_response(entity2, request_handler)
            elif entity2.has(ActorComponent):
                # 处理角色
                self._handle_actor_response(entity2, request_handler)
            else:
                assert False, f"Unknown entity type: {entity2}"

    ####################################################################################################################################
    # 生成请求
    def _gen_stages_requests(
        self, stage_entities: Set[Entity]
    ) -> List[ChatRequestHandler]:

        ret: List[ChatRequestHandler] = []

        # 准备模板
        stage_response_template = StageResponse(
            narrate="当前场景描述", actors=["场景内的角色全名", "..."]
        )

        # 都用这个prompt
        message = f"""# 提示: 将你目前的状态与信息告诉我。
## 输出内容1-场景描述
- 注意：不要输入任何场景内角色信息，只需描述场景本身。
## 输出内容2-角色状态
- 场景内全部的角色的全名(注意‘全名机制’)。
- 不要漏掉任何一个角色。
## 输出要求
- 保持内容简洁，但不要遗漏重要信息。
- 不要使用```json```来封装内容。
### 输出格式(JSON)
{stage_response_template.model_dump_json()}"""

        # 生成请求
        for stage_entity in stage_entities:
            assert stage_entity.has(StageComponent)
            agent_short_term_memory = self._game.get_agent_short_term_memory(
                stage_entity
            )
            ret.append(
                ChatRequestHandler(
                    name=stage_entity._name,
                    prompt=message,
                    chat_history=agent_short_term_memory.chat_history,
                )
            )
        return ret

    ####################################################################################################################################
    # 生成请求
    def _gen_actors_requests(
        self, actor_entities: Set[Entity]
    ) -> List[ChatRequestHandler]:

        ret: List[ChatRequestHandler] = []

        # 准备模板
        actor_response_template = ActorResponse(
            stage="场景全名",
            actors=["场景内的角色全名", "..."],
            status_effects=[
                StatusEffect(name="状态名称1", description="状态描述1", rounds=1),
                StatusEffect(name="状态名称2", description="状态描述2", rounds=2),
            ],
        )

        # 都用这个prompt
        message = f"""# 提示: 将你目前的状态与信息告诉我。
## 输出内容1-场景全名
- 场景全名(注意‘全名机制’)。
## 输出内容2-角色状态
- 场景内所有角色的全名(注意‘全名机制’)。
- 不要漏掉任何一个角色。
## 输出内容3-状态：
- 你当前拥有的状态（增益/减益）。
## 输出要求：
- 保持内容简洁，但不要遗漏重要信息。
- 不要使用```json```来封装内容。
### 输出格式(JSON)
{actor_response_template.model_dump_json()}"""

        # 生成请求
        for actor_entity in actor_entities:
            assert actor_entity.has(ActorComponent)
            agent_short_term_memory = self._game.get_agent_short_term_memory(
                actor_entity
            )

            ret.append(
                ChatRequestHandler(
                    name=actor_entity._name,
                    prompt=message,
                    chat_history=agent_short_term_memory.chat_history,
                )
            )
        return ret

    ####################################################################################################################################
    # 后续处理：处理场景的返回
    def _handle_stage_response(
        self, stage_entity: Entity, request_handler: ChatRequestHandler
    ) -> None:
        assert stage_entity.has(StageComponent)
        assert stage_entity._name == request_handler._name

        # 核心处理
        try:

            format_response = StageResponse.model_validate_json(
                format_string.json_format.strip_json_code_block(
                    request_handler.response_content
                )
            )
            logger.warning(
                f"Stage: {stage_entity._name}, Response:\n{format_response.model_dump_json()}"
            )

            self._result_mapping[stage_entity] = format_response

        except Exception as e:
            logger.error(f"Exception: {e}")

    ####################################################################################################################################
    # 后续处理：处理角色的返回
    def _handle_actor_response(
        self, actor_entity: Entity, request_handler: ChatRequestHandler
    ) -> None:
        assert actor_entity.has(ActorComponent)
        assert actor_entity._name == request_handler._name

        # 核心处理
        try:

            format_response = ActorResponse.model_validate_json(
                format_string.json_format.strip_json_code_block(
                    request_handler.response_content
                )
            )
            logger.warning(
                f"Actor: {actor_entity._name}, Response:\n{format_response.model_dump_json()}"
            )

            self._result_mapping[actor_entity] = format_response
        except Exception as e:
            logger.error(f"Exception: {e}")

    ####################################################################################################################################
