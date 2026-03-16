from typing import Dict, Final, List, Optional, Tuple, final
from langchain_core.messages import AIMessage
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..chat_client.client import ChatClient
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import (
    StageDescriptionComponent,
    StageComponent,
)
from ..utils import (
    compute_cache_key,
    extract_json_from_code_block,
    load_debug_cache,
    save_debug_cache,
)


#######################################################################################################################################
@final
class StageDescriptionResponse(BaseModel):
    description: str = ""


#######################################################################################################################################
def _build_stage_description_prompt(
    actor_appearances_on_stage: Dict[str, str],
) -> str:
    """构建场景描述的提示词。

    根据场景内角色的外貌信息，生成用于请求AI生成场景环境描述的提示词。
    该提示词要求AI仅描述场景环境，不包含角色信息。

    Args:
        actor_appearances_on_stage: 角色名称到外貌描述的映射字典

    Returns:
        格式化的提示词字符串，包含角色列表和输出格式说明
    """
    actor_appearances_on_stage_info = []
    for actor_name, appearance in actor_appearances_on_stage.items():
        actor_appearances_on_stage_info.append(f"{actor_name}: {appearance}")
    if len(actor_appearances_on_stage_info) == 0:
        actor_appearances_on_stage_info.append("无")

    return f"""# 指令！请你输出你的场景描述。并以 JSON 格式输出。

## 场景内角色

{"\n\n".join(actor_appearances_on_stage_info)}

## 输出格式(JSON)

```json
{{
  "description": "场景内的环境描述"
}}
```

**约束规则**：

- 场景内的环境描述，不要包含任何角色信息
- 所有输出必须为第三人称视角
- 严格按上述JSON格式输出"""


#######################################################################################################################################
@final
class StageDescriptionSystem(ExecuteProcessor):
    """场景描述生成系统。

    为 StageComponent 实体生成环境描述文本，结果写入 StageDescriptionComponent。
    跳过已有描述的场景，对待处理场景并行发起 AI 请求。

    Attributes:
        _game: TCG游戏上下文
    """

    def __init__(self, game: TCGGame, enable_debug_cache: bool = True) -> None:
        self._game: Final[TCGGame] = game
        self._enable_debug_cache: bool = enable_debug_cache

    #######################################################################################################################################
    @override
    async def execute(self) -> None:

        # 获取所有可以进行场景规划的场景实体
        stage_entities = self._game.get_group(
            Matcher(all_of=[StageComponent])
        ).entities.copy()

        # 预检阶段：构建 prompt，计算 cache key，分流 cache hit / pending
        cache_hit_map: Dict[str, Tuple[str, List[AIMessage]]] = (
            {}
        )  # entity_name -> (prompt, ai_messages)
        pending_key_map: Dict[str, str] = {}  # entity_name -> cache_key
        pending_inputs: List[Tuple[Entity, str]] = []  # (entity, prompt)

        for stage_entity in stage_entities:
            environment_comp = stage_entity.get(StageDescriptionComponent)
            if environment_comp.narrative != "":
                logger.debug(
                    f"跳过场景 {stage_entity.name} 的规划请求，因其环境描述不为空"
                )
                continue

            actor_appearances_on_stage: Dict[str, str] = (
                self._game.get_actor_appearances_on_stage(stage_entity)
            )
            prompt = _build_stage_description_prompt(actor_appearances_on_stage)
            context = self._game.get_agent_context(stage_entity).context

            if self._enable_debug_cache:
                cache_key = compute_cache_key(context, prompt)
                cached = load_debug_cache(cache_key)
                if cached is not None:
                    cache_hit_map[stage_entity.name] = (prompt, cached)
                    logger.debug(
                        f"[cache hit] 场景 {stage_entity.name} 命中缓存，跳过 AI 推理"
                    )
                    continue
                pending_key_map[stage_entity.name] = cache_key

            pending_inputs.append((stage_entity, prompt))

        # 推理阶段：仅对 pending 实体发起 AI 请求
        chat_clients: List[ChatClient] = [
            ChatClient(
                name=stage_entity.name,
                prompt=prompt,
                context=self._game.get_agent_context(stage_entity).context,
            )
            for stage_entity, prompt in pending_inputs
        ]
        await ChatClient.batch_chat(clients=chat_clients)

        # 结果处理阶段：cache hit 直接 replay，推理结果正常处理并写入缓存
        for entity_name, (prompt, ai_messages) in cache_hit_map.items():
            stage_entity_or_none = self._game.get_entity_by_name(entity_name)
            assert (
                stage_entity_or_none is not None
            ), f"未找到名称为 {entity_name} 的实体"
            self._process_cached(stage_entity_or_none, prompt, ai_messages)

        for chat_client in chat_clients:
            stage_entity_or_none = self._game.get_entity_by_name(chat_client.name)
            assert (
                stage_entity_or_none is not None
            ), f"未找到名称为 {chat_client.name} 的实体"
            self._process_stage_description_response(
                stage_entity,
                chat_client,
                cache_key=pending_key_map.get(chat_client.name),
            )

    #######################################################################################################################################
    #######################################################################################################################################
    def _process_cached(
        self,
        stage_entity: Entity,
        prompt: str,
        ai_messages: List[AIMessage],
    ) -> None:
        """用缓存的 AI 响应 replay 场景描述更新（不触发网络请求）。"""
        try:
            response_content = ""
            if ai_messages:
                content = ai_messages[-1].content
                response_content = content if isinstance(content, str) else str(content)

            format_response = StageDescriptionResponse.model_validate_json(
                extract_json_from_code_block(response_content)
            )

            self._game.add_human_message(stage_entity, prompt)
            self._game.add_ai_message(stage_entity, ai_messages)

            if format_response.description != "":
                stage_entity.replace(
                    StageDescriptionComponent,
                    stage_entity.name,
                    format_response.description,
                )

        except Exception as e:
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
    def _process_stage_description_response(
        self,
        stage_entity: Entity,
        chat_client: ChatClient,
        cache_key: Optional[str] = None,
    ) -> None:
        """解析 AI 响应，更新场景实体的 StageDescriptionComponent 并存入对话历史。

        若 cache_key 不为 None 且启用了 debug cache，则将响应写入磁盘缓存。
        """
        try:

            format_response = StageDescriptionResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            self._game.add_human_message(stage_entity, chat_client.prompt)
            self._game.add_ai_message(stage_entity, chat_client.response_ai_messages)

            # 更新环境描写
            if format_response.description != "":
                stage_entity.replace(
                    StageDescriptionComponent,
                    stage_entity.name,
                    format_response.description,
                )

            # 写入缓存
            if self._enable_debug_cache and cache_key is not None:
                save_debug_cache(cache_key, chat_client.response_ai_messages)

        except Exception as e:
            logger.error(f"Exception: {e}")


#######################################################################################################################################
