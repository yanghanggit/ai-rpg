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
    """场景描述系统的 AI 响应格式。"""

    description: str = ""


#######################################################################################################################################
def _build_stage_description_prompt(
    actor_appearances_on_stage: Dict[str, str],
) -> str:
    """为场景描述请求构建 prompt。

    指示 AI 仅描述场景环境，不得包含角色信息。

    Args:
        actor_appearances_on_stage: 角色名称 → 外貌描述的映射。

    Returns:
        包含角色列表与 JSON 输出格式要求的 prompt 字符串。
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
    """为场景实体生成环境描述，写入 StageDescriptionComponent.narrative。

    执行流程分三步：收集待处理实体 → 命中缓存则直接 replay → 剩余实体并行 AI 推理。
    开发期可通过 enable_debug_cache 开启磁盘缓存，相同输入直接复用上次结果。

    Attributes:
        _game: 游戏上下文。
        _enable_debug_cache: 是否启用开发期磁盘缓存。
    """

    def __init__(self, game: TCGGame, enable_debug_cache: bool) -> None:
        self._game: Final[TCGGame] = game
        self._enable_debug_cache: Final[bool] = enable_debug_cache

    #######################################################################################################################################
    @override
    async def execute(self) -> None:

        # step1: 收集 narrative 为空、真正需要推理的实体
        pending: List[Tuple[Entity, str]] = self._collect_pending_stage_entities()

        # step2: 启用缓存时，命中缓存的直接 replay 并从 pending 移除
        pending_with_key: List[Tuple[Entity, str, str]] = (
            self._apply_debug_cache(pending)
            if self._enable_debug_cache
            else [(entity, prompt, "") for entity, prompt in pending]
        )

        # step3: 剩余实体走 AI 推理，完成后更新上下文并写入缓存
        await self._run_inference(pending_with_key)

    #######################################################################################################################################
    def _collect_pending_stage_entities(self) -> List[Tuple[Entity, str]]:
        """收集 narrative 为空的场景实体，并为每个实体预构建 prompt。

        Returns:
            待处理列表，每项为 (实体, prompt)。
        """
        pending: List[Tuple[Entity, str]] = []

        stage_entities = self._game.get_group(
            Matcher(all_of=[StageComponent])
        ).entities.copy()

        for stage_entity in stage_entities:
            if stage_entity.get(StageDescriptionComponent).narrative != "":
                logger.debug(
                    f"跳过场景 {stage_entity.name} 的规划请求，因其环境描述不为空"
                )
                continue

            actor_appearances_on_stage: Dict[str, str] = (
                self._game.get_actor_appearances_on_stage(stage_entity)
            )
            prompt = _build_stage_description_prompt(actor_appearances_on_stage)
            pending.append((stage_entity, prompt))

        return pending

    #######################################################################################################################################
    def _apply_debug_cache(
        self, pending: List[Tuple[Entity, str]]
    ) -> List[Tuple[Entity, str, str]]:
        """从 pending 中消费缓存命中项：直接 replay 并移除，未命中的附带 cache_key 返回。

        Args:
            pending: 待处理的 (实体, prompt) 列表。

        Returns:
            仍需 AI 推理的列表，每项为 (实体, prompt, cache_key)。
        """
        remaining: List[Tuple[Entity, str, str]] = []

        for stage_entity, prompt in pending:
            context = self._game.get_agent_context(stage_entity).context
            cache_key = compute_cache_key(context, prompt, stage_entity.name)
            cached = load_debug_cache(cache_key)

            if cached is not None:
                logger.debug(
                    f"[cache hit] 场景 {stage_entity.name} 命中缓存，跳过 AI 推理"
                )
                self._process_cached(stage_entity, prompt, cached)
            else:
                remaining.append((stage_entity, prompt, cache_key))

        return remaining

    #######################################################################################################################################
    async def _run_inference(
        self, pending_with_key: List[Tuple[Entity, str, str]]
    ) -> None:
        """对待推理实体并行发起 AI 请求，完成后更新上下文并写入磁盘缓存。

        Args:
            pending_with_key: (实体, prompt, cache_key) 列表；cache_key 为空串时不写缓存。
        """
        if not pending_with_key:
            return

        chat_clients: List[ChatClient] = [
            ChatClient(
                name=stage_entity.name,
                prompt=prompt,
                context=self._game.get_agent_context(stage_entity).context,
            )
            for stage_entity, prompt, _ in pending_with_key
        ]
        await ChatClient.batch_chat(clients=chat_clients)

        key_map: Dict[str, str] = {
            stage_entity.name: cache_key
            for stage_entity, _, cache_key in pending_with_key
        }

        for chat_client in chat_clients:
            stage_entity_or_none = self._game.get_entity_by_name(chat_client.name)
            assert (
                stage_entity_or_none is not None
            ), f"未找到名称为 {chat_client.name} 的实体"
            self._process_stage_description_response(
                stage_entity_or_none,
                chat_client,
                cache_key=key_map.get(chat_client.name),
            )

    #######################################################################################################################################
    def _process_cached(
        self,
        stage_entity: Entity,
        prompt: str,
        ai_messages: List[AIMessage],
    ) -> None:
        """用磁盘缓存的 AI 响应 replay 场景描述更新，不触发网络请求。

        Args:
            stage_entity: 目标场景实体。
            prompt: 本次请求的 prompt（写入对话历史）。
            ai_messages: 缓存的 AIMessage 列表。
        """
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
        """解析 AI 响应，更新 StageDescriptionComponent 并存入对话历史。

        Args:
            stage_entity: 目标场景实体。
            chat_client: 已完成请求的 ChatClient。
            cache_key: 不为 None 时将响应写入磁盘缓存。
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
