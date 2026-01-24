"""
敌人抽牌决策系统模块

为敌人实体提供基于LLM的智能战术决策。敌人通过历史战斗记录和观察推断战况，
而非直接获取数值面板，模拟真实战士的决策过程。

使用方式：
    在combat_pipeline中注册EnemyDrawDecisionSystem，位于DrawCardsActionSystem之前。
    系统会自动拦截敌人的DrawCardsAction，调用LLM优化技能和目标选择。
"""

from typing import Final, List, final, override
from loguru import logger
from pydantic import BaseModel
from ..chat_service.client import ChatClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    DrawCardsAction,
    EnemyComponent,
    DeathComponent,
    Skill,
    StatusEffect,
    SkillBookComponent,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class EnemyDecisionResponse(BaseModel):
    """敌人决策响应模型

    LLM 返回的战术决策结果，包含技能选择和目标选择。
    状态效果由系统随机分配，不可选择（防止作弊）。
    """

    selected_skill_name: str  # 选择的技能名称
    selected_targets: List[str]  # 选择的目标名称列表（至少1个）
    reasoning: str = ""  # 战术理由（可选，用于调试）


#######################################################################################################################################
def _generate_enemy_decision_prompt(
    # actor_name: str,
    available_skills: List[Skill],
    available_targets: List[str],
    actor_status_effects: List[StatusEffect],
    current_round: int,
) -> str:
    """
    生成敌人战术决策提示词（基于感知的决策）

    敌人通过观察战斗演出、数据日志和历史记忆做决策，而非查看数值面板。
    决策依据来自 Agent context 中的历史消息（战斗演出 + 数据日志）。

    状态效果由系统随机分配（"出题"），敌人必须围绕它选择技能和目标（"解题"）。

    Args:
        available_skills: 可用技能列表
        available_targets: 场景内所有存活角色名称列表（包括自己/队友/敌人）
        actor_status_effects: 系统分配的状态效果列表（不可修改，必须适应）
        current_round: 当前回合数

    Returns:
        str: 格式化的完整提示词
    """

    # 格式化技能列表
    skills_text = "\n".join(
        [f"- {skill.name}: {skill.description}" for skill in available_skills]
    )

    # 格式化目标列表（简单名称列表）
    targets_text = "\n".join([f"- {target}" for target in available_targets])

    # 格式化状态效果列表
    if actor_status_effects:
        effects_text = "\n".join(
            [
                f"- {effect.name}: {effect.description}"
                for effect in actor_status_effects
            ]
        )
    else:
        effects_text = "无"

    return f"""# 指令！第{current_round}回合战术决策（JSON格式）

基于历史战斗记录推断战况并制定战术。

## 可用技能

{skills_text}

## 场景角色

{targets_text}

## 系统分配的效果（必须围绕它制定战术）

{effects_text}

## 输出格式

```json
{{
  "selected_skill_name": "选择应对状态效果的技能",
  "selected_targets": ["选择合适的目标"],
  "reasoning": "如何应对这个状态效果（字数<100）"
}}
```"""


#######################################################################################################################################
@final
class EnemyDrawDecisionSystem(ReactiveProcessor):
    """
    敌人抽牌决策系统

    拦截敌人的DrawCardsAction，通过LLM基于历史战斗记录做出战术决策，
    优化技能选择和目标选择。决策失败时保持原始Action不变。
    """

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: Final[TCGGame] = game_context

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(DrawCardsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        """只处理敌人实体且未死亡的情况"""
        return (
            entity.has(DrawCardsAction)
            and entity.has(EnemyComponent)
            and not entity.has(DeathComponent)
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        """
        为敌人实体执行智能决策

        批量处理所有敌人的决策请求，调用 LLM 后修改各自的 DrawCardsAction。
        """

        if len(entities) == 0:
            return

        # 验证战斗状态
        if not self._game.current_combat_sequence.is_ongoing:
            logger.debug("EnemyDrawDecisionSystem: 战斗未进行中，跳过决策")
            return

        # 获取当前回合数
        current_round_number = len(self._game.current_combat_sequence.current_rounds)

        # 为每个敌人实体创建聊天客户端
        chat_clients: List[ChatClient] = []
        for entity in entities:
            try:
                chat_client = self._create_chat_client(entity, current_round_number)
                chat_clients.append(chat_client)
            except Exception as e:
                logger.error(f"创建 ChatClient 失败 ({entity.name}): {e}")
                # 跳过该实体，保持原始 DrawCardsAction

        if len(chat_clients) == 0:
            logger.warning("EnemyDrawDecisionSystem: 没有有效的 ChatClient，跳过决策")
            return

        # 批量调用 LLM
        await ChatClient.batch_chat(clients=chat_clients)

        # 处理每个决策响应
        for chat_client in chat_clients:
            found_entity = self._game.get_entity_by_name(chat_client.name)
            if found_entity is None:
                logger.error(f"实体 {chat_client.name} 未找到")
                continue
            entity = found_entity

            self._process_decision_response(entity, chat_client, current_round_number)

    ####################################################################################################################################
    def _create_chat_client(self, entity: Entity, current_round: int) -> ChatClient:
        """
        为敌人实体创建聊天客户端以请求 LLM 做决策

        Args:
            entity: 敌人实体
            current_round: 当前回合数

        Returns:
            ChatClient: 准备好的聊天客户端
        """
        # 获取可用技能
        available_skills = self._get_available_skills(entity)

        # 获取场景内所有角色名称（简化信息，不包含数值）
        available_targets = self._get_available_targets(entity)

        # 获取当前状态效果（用于选择要应用的效果）
        draw_cards_action = entity.get(DrawCardsAction)
        assert (
            draw_cards_action is not None
        ), f"Entity {entity.name} must have DrawCardsAction"
        actor_status_effects = draw_cards_action.status_effects

        # 生成提示词（基于感知而非数值）
        prompt = _generate_enemy_decision_prompt(
            # actor_name=entity.name,
            available_skills=available_skills,
            available_targets=available_targets,
            actor_status_effects=actor_status_effects,
            current_round=current_round,
        )

        # 创建并返回聊天客户端
        # Agent context 会自动包含历史消息（战斗演出 + 数据日志）
        return ChatClient(
            name=entity.name,
            prompt=prompt,
            context=self._game.get_agent_context(entity).context,
        )

    ####################################################################################################################################
    def _process_decision_response(
        self, entity: Entity, chat_client: ChatClient, current_round: int
    ) -> None:
        """
        处理 LLM 返回的决策响应并修改 DrawCardsAction

        Args:
            entity: 敌人实体
            chat_client: 包含 LLM 响应的聊天客户端
            current_round: 当前回合数
        """
        try:
            # 解析 JSON 响应
            validated_response = EnemyDecisionResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            # 验证并获取选择的技能
            selected_skill = self._validate_skill(
                entity, validated_response.selected_skill_name
            )
            if selected_skill is None:
                logger.warning(f"{entity.name}: 技能验证失败，保持原始 DrawCardsAction")
                return

            # 验证并获取选择的目标
            validated_targets = self._validate_targets(
                entity, validated_response.selected_targets
            )
            if len(validated_targets) == 0:
                logger.warning(f"{entity.name}: 目标验证失败，保持原始 DrawCardsAction")
                return

            # 获取原始状态效果（系统分配的，不可修改）
            draw_cards_action = entity.get(DrawCardsAction)
            assert draw_cards_action is not None
            system_effects = draw_cards_action.status_effects

            # 记录决策结果（调试用）
            logger.debug(
                f"{entity.name} 决策: 技能=[{selected_skill.name}] "
                f"目标={validated_targets} 系统效果数={len(system_effects)} "
                f"理由: {validated_response.reasoning}"
            )

            # 修改 DrawCardsAction（保持系统分配的effects）
            entity.replace(
                DrawCardsAction,
                entity.name,
                selected_skill,
                validated_targets,
                system_effects,  # 使用系统分配的effects，不允许修改
            )

        except Exception as e:
            logger.error(f"{entity.name} 决策处理失败: {e}")
            logger.error(f"响应内容: {chat_client.response_content}")
            # 保持原始 DrawCardsAction 不变

    ####################################################################################################################################
    def _get_available_skills(self, entity: Entity) -> List[Skill]:
        """
        获取实体的可用技能列表

        Args:
            entity: 目标实体

        Returns:
            可用技能列表
        """
        skill_book_comp = entity.get(SkillBookComponent)
        assert (
            skill_book_comp is not None
        ), f"Entity {entity.name} must have SkillBookComponent"

        if len(skill_book_comp.skills) == 0:
            logger.warning(f"{entity.name} 没有可用技能")
            assert False, f"Entity {entity.name} has no skills"

        return skill_book_comp.skills.copy()

    ####################################################################################################################################
    def _get_available_targets(self, entity: Entity) -> List[str]:
        """
        获取场景内所有存活角色的名称列表（包括自己/队友/敌人）

        敌人决策时可以看到场景内所有角色，但看不到他们的数值数据。
        通过历史消息（战斗演出和数据日志）推断战况。

        Args:
            entity: 敌人实体

        Returns:
            角色名称列表
        """
        # 获取场景上所有存活的角色
        actor_entities = self._game.get_alive_actors_on_stage(entity)

        # 返回所有角色名称（包括自己）
        return [actor.name for actor in actor_entities]

    ####################################################################################################################################
    def _validate_skill(self, entity: Entity, skill_name: str) -> Skill | None:
        """
        验证技能名称是否有效

        Args:
            entity: 敌人实体
            skill_name: LLM 选择的技能名称

        Returns:
            验证通过返回 Skill 对象，否则返回 None
        """
        available_skills = self._get_available_skills(entity)

        for skill in available_skills:
            if skill.name == skill_name:
                return skill

        logger.warning(f"{entity.name}: 技能 '{skill_name}' 不在可用列表中")
        return None

    ####################################################################################################################################
    def _validate_targets(self, entity: Entity, target_names: List[str]) -> List[str]:
        """
        验证目标名称列表是否有效

        Args:
            entity: 敌人实体
            target_names: LLM 选择的目标名称列表

        Returns:
            验证通过的目标名称列表（至少包含1个，否则返回空列表表示失败）
        """
        if len(target_names) == 0:
            logger.warning(f"{entity.name}: 目标列表为空")
            return []

        # 获取场景上所有存活角色的名称（包括自己/队友/敌人）
        actor_entities = self._game.get_alive_actors_on_stage(entity)
        valid_names = {actor.name for actor in actor_entities}

        # 筛选有效目标
        validated = [name for name in target_names if name in valid_names]

        if len(validated) == 0:
            logger.warning(f"{entity.name}: 所有目标都无效 {target_names}")

        return validated

    ####################################################################################################################################
