from typing import Dict, Final, List, Optional, Tuple, final
from ..models.messages import AIMessage
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
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
def _build_compressed_stage_description_prompt(
    actor_appearances_in_stage: Dict[str, str],
) -> str:
    """生成压缩版场景描述提示词（仅角色外观动态感知，省略静态输出格式与约束规则）"""

    actor_appearances_in_stage_info = []
    for actor_name, appearance in actor_appearances_in_stage.items():
        actor_appearances_in_stage_info.append(f"{actor_name}: {appearance}")

    if len(actor_appearances_in_stage_info) == 0:
        actor_appearances_in_stage_info.append("无")

    return f"""# 请你输出你的场景描述。并以 JSON 格式输出。

## 场景内角色外观（用于推断环境影响）

以下角色的外观可能对场景环境产生间接影响，请据此推断当前环境状态。

{"\n\n".join(actor_appearances_in_stage_info)}"""


#######################################################################################################################################
def _build_stage_description_prompt(
    actor_appearances_in_stage: Dict[str, str],
) -> str:
    """为场景描述请求构建 prompt。

    指示 AI 根据场景内角色外观推断其对环境的间接影响，并将影响效果融入场景描述，
    但最终输出不得提及任何角色本身。

    Args:
        actor_appearances_in_stage: 角色名称 → 外貌描述的映射。

    Returns:
        包含角色外观列表与 JSON 输出格式要求的 prompt 字符串。
    """

    # 构建角色外观信息列表，若无角色则注明“无”以避免 AI 误以为输入遗漏导致解析错误
    actor_appearances_in_stage_info = []
    for actor_name, appearance in actor_appearances_in_stage.items():
        actor_appearances_in_stage_info.append(f"{actor_name}: {appearance}")

    # 若场景内无角色，则明确告知 AI 以避免其误以为是输入遗漏导致的解析错误
    if len(actor_appearances_in_stage_info) == 0:
        actor_appearances_in_stage_info.append("无")

    return f"""# 请你输出你的场景描述。并以 JSON 格式输出。

## 场景内角色外观（用于推断环境影响）

以下角色的外观可能对场景环境产生间接影响，请据此推断当前环境状态。

{"\n\n".join(actor_appearances_in_stage_info)}

## 输出格式(JSON)

```json
{{
  "description": "场景内的环境描述"
}}
```

**约束规则**：

- 若角色外观会对环境产生直接影响（例如：持火把者照亮黑暗空间、发光生物映亮洞壁），须将该**环境影响效果**纳入场景描述
- 无论角色是否对环境产生影响，最终描述中均**不得提及**任何角色本身（不得出现角色名称、角色形态或角色行为）
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

    def __init__(
        self,
        game: TCGGame,
        enable_debug_cache: bool,
        use_compressed_prompt: bool = True,
    ) -> None:
        self._game: Final[TCGGame] = game
        self._enable_debug_cache: Final[bool] = enable_debug_cache
        self._use_compressed_prompt: Final[bool] = use_compressed_prompt

    #######################################################################################################################################
    @override
    async def execute(self) -> None:

        # step1: 收集 narrative 为空、真正需要推理的实体
        # 每项为 (实体, full_prompt, compressed_prompt)
        pending: List[Tuple[Entity, str, str]] = self._collect_pending_stage_entities()

        # step2: 启用缓存时，命中缓存的直接 replay 并从 pending 移除
        # 每项为 (实体, full_prompt, compressed_prompt, cache_key)
        pending_with_key: List[Tuple[Entity, str, str, str]] = (
            self._apply_debug_cache(pending)
            if self._enable_debug_cache
            else [(entity, full, comp, "") for entity, full, comp in pending]
        )

        # step3: 剩余实体走 AI 推理，完成后更新上下文并写入缓存
        await self._run_inference(pending_with_key)

    #######################################################################################################################################
    def _collect_pending_stage_entities(self) -> List[Tuple[Entity, str, str]]:
        """收集尚未生成描述的场景实体（有 StageComponent 但无 StageDescriptionComponent），并为每个实体预构建 prompt。

        触发条件：实体拥有 StageComponent 且尚未持有 StageDescriptionComponent。
        强制刷新方式：外部移除 StageDescriptionComponent，下次执行将重新触发推理。

        Returns:
            待处理列表，每项为 (实体, full_prompt, compressed_prompt)。
        """
        pending: List[Tuple[Entity, str, str]] = []

        stage_entities = self._game.get_group(
            Matcher(all_of=[StageComponent], none_of=[StageDescriptionComponent])
        ).entities.copy()

        for stage_entity in stage_entities:
            actor_appearances_in_stage: Dict[str, str] = (
                self._game.get_actor_appearances_in_stage(stage_entity)
            )
            full_prompt = _build_stage_description_prompt(actor_appearances_in_stage)
            compressed_prompt = (
                _build_compressed_stage_description_prompt(actor_appearances_in_stage)
                if self._use_compressed_prompt
                else full_prompt
            )
            pending.append((stage_entity, full_prompt, compressed_prompt))

        return pending

    #######################################################################################################################################
    def _apply_debug_cache(
        self, pending: List[Tuple[Entity, str, str]]
    ) -> List[Tuple[Entity, str, str, str]]:
        """从 pending 中消费缓存命中项：直接 replay 并移除，未命中的附带 cache_key 返回。

        Args:
            pending: 待处理的 (实体, full_prompt, compressed_prompt) 列表。

        Returns:
            仍需 AI 推理的列表，每项为 (实体, full_prompt, compressed_prompt, cache_key)。
        """
        remaining: List[Tuple[Entity, str, str, str]] = []

        for stage_entity, full_prompt, compressed_prompt in pending:

            # 计算缓存键（基于 full_prompt 保持语义一致性）并尝试加载
            context = self._game.get_agent_context(stage_entity).context
            cache_key = compute_cache_key(context, full_prompt, stage_entity.name)
            cached = load_debug_cache(cache_key)

            if cached is not None:
                logger.debug(
                    f"[cache hit] 场景 {stage_entity.name} 命中缓存，跳过 AI 推理"
                )
                self._process_cached(
                    stage_entity, full_prompt, compressed_prompt, cached
                )
            else:
                remaining.append(
                    (stage_entity, full_prompt, compressed_prompt, cache_key)
                )

        return remaining

    #######################################################################################################################################
    async def _run_inference(
        self, pending_with_key: List[Tuple[Entity, str, str, str]]
    ) -> None:
        """对待推理实体并行发起 AI 请求，完成后更新上下文并写入磁盘缓存。

        Args:
            pending_with_key: (实体, full_prompt, compressed_prompt, cache_key) 列表；cache_key 为空串时不写缓存。
        """
        if not pending_with_key:
            return

        chat_clients: List[DeepSeekClient] = [
            DeepSeekClient(
                name=stage_entity.name,
                prompt=full_prompt,
                compressed_prompt=(
                    compressed_prompt if self._use_compressed_prompt else None
                ),
                context=self._game.get_agent_context(stage_entity).context,
            )
            for stage_entity, full_prompt, compressed_prompt, _ in pending_with_key
        ]
        await DeepSeekClient.batch_chat(clients=chat_clients)

        key_map: Dict[str, str] = {
            stage_entity.name: cache_key
            for stage_entity, _, _comp, cache_key in pending_with_key
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
        full_prompt: str,
        compressed_prompt: str,
        ai_message: AIMessage,
    ) -> None:
        """用磁盘缓存的 AI 响应 replay 场景描述更新，不触发网络请求。

        Args:
            stage_entity: 目标场景实体。
            full_prompt: 发送给 LLM 的完整 prompt。
            compressed_prompt: 写入对话历史的压缩版 prompt。
            ai_message: 缓存的 AIMessage。
        """
        try:

            # 解析响应并更新环境描写
            format_response = StageDescriptionResponse.model_validate_json(
                extract_json_from_code_block(ai_message.content)
            )

            if format_response.description == "":
                logger.warning(f"缓存的环境描写为空，stage_entity={stage_entity.name}")
                raise ValueError("缓存的环境描写为空")

            # 仅更新对话历史和环境描写，不触发网络请求
            if self._use_compressed_prompt:
                self._game.add_human_message(
                    stage_entity,
                    compressed_prompt,
                    stage_description_full_prompt=full_prompt,
                )
            else:
                self._game.add_human_message(stage_entity, full_prompt)
            self._game.add_ai_message(stage_entity, ai_message)

            # if format_response.description != "":
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
        chat_client: DeepSeekClient,
        cache_key: Optional[str] = None,
    ) -> None:
        """解析 AI 响应，更新 StageDescriptionComponent 并存入对话历史。

        Args:
            stage_entity: 目标场景实体。
            chat_client: 已完成请求的 DeepSeekClient。
            cache_key: 不为 None 时将响应写入磁盘缓存。
        """
        try:

            format_response = StageDescriptionResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            if format_response.description == "":
                logger.warning(
                    f"AI返回的环境描写为空，stage_entity={stage_entity.name}, response_content={chat_client.response_content}"
                )
                raise ValueError("AI返回的环境描写为空")

            if self._use_compressed_prompt:
                self._game.add_human_message(
                    stage_entity,
                    chat_client.compressed_prompt,
                    stage_description_full_prompt=chat_client.prompt,
                )
            else:
                self._game.add_human_message(stage_entity, chat_client.prompt)
            assert chat_client.response_ai_message is not None
            self._game.add_ai_message(stage_entity, chat_client.response_ai_message)

            # 更新环境描写
            # if format_response.description != "":
            stage_entity.replace(
                StageDescriptionComponent,
                stage_entity.name,
                format_response.description,
            )

            # 写入缓存
            if self._enable_debug_cache and cache_key is not None:
                assert chat_client.response_ai_message is not None
                save_debug_cache(cache_key, chat_client.response_ai_message)

        except Exception as e:
            logger.error(f"Exception: {e}")


#######################################################################################################################################
