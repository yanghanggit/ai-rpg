"""战斗状态效果追加系统模块"""

from typing import Final, List, final, Dict, Optional
from loguru import logger
from overrides import override
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    ActorComponent,
    AddStatusEffectsAction,
    HumanMessage,
    StatusEffectsComponent,
    DeathComponent,
    StatusEffect,
)
from ..utils import extract_json_from_code_block
from .arbitration_prompt_builders import fmt_duration
from .status_effect_prompt_builders import (
    generate_add_status_effects_prompt,
    generate_compressed_add_status_effects_prompt,
)
from pydantic import BaseModel


#######################################################################################################################################
class AddStatusEffectsResponse(BaseModel):
    """追加状态效果响应"""

    add_effects: List[StatusEffect] = []  # 本次追加的新效果列表


#######################################################################################################################################
def _generate_status_effects_notification_prompt(
    entity_name: str, status_effects: List[StatusEffect]
) -> str:
    """将角色当前状态效果列表构建为 Markdown 格式提示词（含全部字段），用于通知类 HumanMessage 内容。"""

    if not status_effects:
        effects_block = "- 无"
    else:
        effects_block = "\n".join(
            f"- 【{e.name}】{fmt_duration(e.duration)} | phase={e.phase} | "
            f"counter={e.counter} | speed={e.speed:+d} | defense={e.defense:+d} | "
            f"source={e.source or '未知'}\n"
            f"  描述：{e.description}"
            for e in status_effects
        )

    return f"""# 状态效果通知：{entity_name} 当前状态效果（共 {len(status_effects)} 个）

{effects_block}"""


#######################################################################################################################################
@final
class AddStatusEffectsActionSystem(ReactiveProcessor):
    """让每个参战 Actor 根据战斗上下文评估并追加新的状态效果（增益/减益/削弱等）。"""

    def __init__(
        self,
        game: DBGGame,
        use_compressed_prompt: bool = True,
    ) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game
        self._use_compressed_prompt: Final[bool] = use_compressed_prompt

    #######################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(AddStatusEffectsAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(AddStatusEffectsAction)
            and entity.has(StatusEffectsComponent)
            and entity.has(ActorComponent)
            and not entity.has(DeathComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        """并发为所有实体调用 LLM 评估并追加状态效果。"""

        # 仅在战斗进行中时触发
        if not self._game.current_combat_room.combat.is_ongoing:
            return

        logger.debug(
            f"触发 AddActorStatusEffectsActionSystem，处理 {len(entities)} 个实体"
        )

        # 直接使用 filter() 已过滤的实体列表，避免重新查询导致对未添加 AddStatusEffectsAction 的角色 assert 失败
        # 为每个参战角色创建评估任务
        chat_clients: List[DeepSeekClient] = [
            self._build_client(entity) for entity in entities
        ]

        # 并发调用所有 LLM
        logger.debug(f"开始并发评估 {len(chat_clients)} 个角色的状态效果...")
        await DeepSeekClient.batch_chat(clients=chat_clients)

        # 处理每个角色的响应
        for chat_client in chat_clients:
            self._process_status_effects_response(chat_client)
            # self._mock_inject_counter_effect(entity)  # [测试用]

    #######################################################################################################################################
    def _build_client(self, entity: Entity) -> DeepSeekClient:

        # 获取当前回合数
        current_round_number = len(self._game.current_combat_room.combat.rounds or [])

        combat_status_effects = entity.get(StatusEffectsComponent)
        assert (
            combat_status_effects is not None
        ), f"角色 {entity.name} 缺少 StatusEffectsComponent！"

        # 从 action 组件读取任务说明
        add_status_effects_action = entity.get(AddStatusEffectsAction)
        assert (
            add_status_effects_action is not None
        ), f"角色 {entity.name} 缺少 AddStatusEffectsAction 组件！"

        # 生成追加状态效果提示词
        prompt = generate_add_status_effects_prompt(
            current_status_effects=combat_status_effects.status_effects,
            current_round_number=current_round_number,
            task_hints=add_status_effects_action.task_hints,
        )

        # 如果启用了压缩提示词，则生成压缩后的提示词，用于在与 LLM 交互时减少上下文长度，提高效率
        compressed_message: Optional[str] = None
        if self._use_compressed_prompt:
            compressed_message = generate_compressed_add_status_effects_prompt(
                current_status_effects=combat_status_effects.status_effects,
                current_round_number=current_round_number,
                task_hints=add_status_effects_action.task_hints,
            )

        # 构建 DeepSeekClient 实例，用于与 LLM 交互，传入实体名称、提示词、压缩提示词以及实体上下文信息
        return DeepSeekClient(
            name=entity.name,
            prompt=prompt,
            compressed_prompt=compressed_message,
            context=self._game.get_agent_context(entity).context,
        )

    #######################################################################################################################################
    def _process_status_effects_response(self, chat_client: DeepSeekClient) -> None:
        """解析 LLM 响应并追加新状态效果；将本轮对话写入实体上下文。"""

        # 检查 LLM 是否返回了有效的 AI 消息，如果没有则记录错误并返回
        if chat_client.response_ai_message is None:
            logger.error(f"[{chat_client.name}] LLM 返回空响应")
            return

        ## 获取对应实体
        entity = self._game.get_entity_by_name(chat_client.name)
        assert entity is not None, f"无法找到角色实体: {chat_client.name}"
        assert entity.has(
            StatusEffectsComponent
        ), f"Entity {entity.name} must have StatusEffectsComponent"

        # 解析 LLM 响应，追加状态效果
        try:
            json_content = extract_json_from_code_block(chat_client.response_content)
            format_response = AddStatusEffectsResponse.model_validate_json(json_content)
        except Exception as e:
            logger.error(f"[{entity.name}] 解析状态效果评估失败: {e}")
            logger.error(f"原始响应: {chat_client.response_content}")
            return

        # 将本轮 prompt 写入角色上下文（Human 端）
        if self._use_compressed_prompt:
            self._game.add_human_message(
                entity=entity,
                human_message=HumanMessage(
                    content=chat_client.compressed_prompt,
                    add_status_effects_full_prompt=chat_client.prompt,
                ),
            )
        else:
            self._game.add_human_message(
                entity=entity,
                human_message=HumanMessage(content=chat_client.prompt),
            )

        # 将 LLM 回复写入角色上下文（AI 端），完成本轮对话
        assert chat_client.response_ai_message is not None
        self._game.add_ai_message(
            entity=entity, ai_message=chat_client.response_ai_message
        )

        # 添加新效果到现有列表
        if format_response.add_effects:

            # 将新增效果的 source 字段设置为角色名称，便于后续追踪来源
            for effect in format_response.add_effects:
                effect.source = entity.name

            # 追加新效果到 CombatStatusEffectsComponent
            combat_status_effects = entity.get(StatusEffectsComponent)
            combat_status_effects.status_effects.extend(format_response.add_effects)
            logger.debug(
                f"[{entity.name}] 新增 {len(format_response.add_effects)} 个状态效果"
            )
            for effect in format_response.add_effects:
                logger.debug(
                    f"[{entity.name}] 新增效果: 「{effect.name}」 phase={effect.phase} duration={effect.duration}"
                )

            # 追加提示消息：告知当前完整状态效果列表（Markdown 格式，全字段），便于后续 LLM 交互感知最新状态
            notification_messages = self._game.filter_messages_by_attributes(
                entity=entity,
                attributes={"status_effects_notification": entity.name},
            )
            if notification_messages:
                # 如果已有通知类消息，就全部删除旧的然后添加新的
                logger.debug(
                    f"[{entity.name}] 删除 {len(notification_messages)} 条旧的状态效果通知消息"
                )
                self._game.remove_messages(
                    entity=entity, messages=notification_messages
                )

            self._game.add_human_message(
                entity=entity,
                human_message=HumanMessage(
                    content=_generate_status_effects_notification_prompt(
                        entity_name=entity.name,
                        status_effects=combat_status_effects.status_effects,
                    ),
                    status_effects_notification=entity.name,  # 标记：本消息为状态效果通知类消息
                ),
            )

        else:
            logger.debug(f"[{entity.name}] 本回合无新增状态效果")


#######################################################################################################################################
