"""
敌人抽牌决策系统模块

该模块实现了敌人在战斗回合中的智能决策机制，负责在卡牌生成前优化敌人的战术选择。

核心特性：
- 仅处理敌人：只监听带有 EnemyComponent 的实体
- LLM 驱动决策：通过语言模型分析战场态势，做出智能决策
- 修改而非创建：修改已存在的 DrawCardsAction，不创建新组件
- 插拔式设计：位于 DrawCardsActionSystem 之前，可随时从 pipeline 中移除

决策内容：
- 技能选择：从可用技能中选择最合适的一个
- 目标选择：从敌方角色中选择要攻击的目标（可多个）
- 状态效果筛选：从当前状态效果中选择要应用的效果

数据流：
activate_actor_card_draws() → DrawCardsAction(默认值)
  → EnemyDrawDecisionSystem(智能决策) → DrawCardsAction(优化后)
  → DrawCardsActionSystem(生成卡牌)
"""

from typing import Any, Final, List, Dict, final, override
from loguru import logger
from pydantic import BaseModel
from ..chat_services.client import ChatClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    DrawCardsAction,
    EnemyComponent,
    AllyComponent,
    DeathComponent,
    Skill,
    StatusEffect,
    CombatStatsComponent,
    SkillBookComponent,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class EnemyDecisionResponse(BaseModel):
    """敌人决策响应模型

    LLM 返回的战术决策结果，包含技能选择、目标选择和状态效果筛选。
    """

    selected_skill_name: str  # 选择的技能名称
    selected_targets: List[str]  # 选择的目标名称列表（至少1个）
    selected_effects: List[str]  # 选择的状态效果名称列表（可为空）
    reasoning: str = ""  # 战术理由（可选，用于调试）


#######################################################################################################################################
def _generate_enemy_decision_prompt(
    actor_name: str,
    available_skills: List[Skill],
    available_targets: List[Dict[str, Any]],
    actor_stats: Dict[str, int],
    actor_status_effects: List[StatusEffect],
    current_round: int,
) -> str:
    """
    生成敌人战术决策提示词

    要求 LLM 分析战场态势，从以下维度做出最优决策：
    - 技能选择：基于技能效果和当前战况选择最合适的技能
    - 目标选择：选择一个或多个目标，可以集火或分散攻击
    - 状态效果：选择要应用到本次行动的状态效果

    Args:
        actor_name: 敌人角色名称
        available_skills: 可用技能列表
        available_targets: 可选目标列表，每个目标包含 name/hp/max_hp/attack/defense/effects
        actor_stats: 敌人当前属性 {hp, max_hp, attack, defense}
        actor_status_effects: 敌人当前状态效果列表
        current_round: 当前回合数

    Returns:
        str: 格式化的完整提示词
    """

    # 格式化技能列表
    skills_text = "\n".join(
        [f"- {skill.name}: {skill.description}" for skill in available_skills]
    )

    # 格式化目标列表
    targets_text = "\n".join(
        [
            f"- {t['name']}: HP {t['hp']}/{t['max_hp']} | 攻击 {t['attack']} | 防御 {t['defense']}"
            + (
                f" | 状态: {', '.join([e.name for e in t['effects']])}"
                if t["effects"]
                else ""
            )
            for t in available_targets
        ]
    )

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

    return f"""# 战术决策：第 {current_round} 回合

你是 **{actor_name}**，需要制定本回合的战术方案。

## 自身状态
- HP: {actor_stats['hp']}/{actor_stats['max_hp']}
- 攻击: {actor_stats['attack']}
- 防御: {actor_stats['defense']}
- 状态效果:
{effects_text}

## 可用技能
{skills_text}

## 可选目标
{targets_text}

## 决策要求

1. **技能选择**：从可用技能中选择一个最合适的（必须是技能名称）
2. **目标选择**：从可选目标中选择至少一个（可以选择多个）
   - 集火：多个技能效果叠加到一个目标
   - 分散：覆盖多个目标降低整体威胁
3. **状态效果**：从自身状态效果中选择要应用的（可全选/部分选/不选）
   - 选择有利于当前战术的效果
   - 过滤掉不相关或负面的效果

## 战术考虑

- 优先攻击低血量目标（斩杀）
- 控制高威胁目标（高攻击）
- 平衡输出和生存
- 利用状态效果的协同作用

## 输出格式

```json
{{
  "selected_skill_name": "技能名称",
  "selected_targets": ["目标名1", "目标名2"],
  "selected_effects": ["效果名1", "效果名2"],
  "reasoning": "简短说明战术意图"
}}
```

**重要**：
- `selected_skill_name` 必须是上面可用技能列表中的名称
- `selected_targets` 必须是上面可选目标列表中的名称
- `selected_effects` 必须是上面状态效果列表中的名称（可为空数组）
"""


#######################################################################################################################################
def _generate_compressed_decision_prompt(current_round: int) -> str:
    """
    生成压缩版本的决策提示词，用于保存到上下文历史。

    Args:
        current_round: 当前回合数

    Returns:
        str: 压缩后的提示词
    """
    return f"""# 战术决策：第 {current_round} 回合

分析战场态势，选择技能、目标和状态效果。"""


#######################################################################################################################################
@final
class EnemyDrawDecisionSystem(ReactiveProcessor):
    """
    敌人抽牌决策系统

    在卡牌生成前为敌人实体提供智能决策，优化技能选择、目标选择和状态效果筛选。

    工作流程：
    1. 监听 DrawCardsAction 添加事件
    2. 过滤出敌人实体（EnemyComponent）
    3. 收集战场信息（可用技能、可选目标、自身状态）
    4. 调用 LLM 做战术决策
    5. 验证决策结果
    6. 修改 DrawCardsAction 组件

    触发时机：在 DrawCardsActionSystem 之前执行

    容错机制：
    - LLM 失败时保持原始 DrawCardsAction 不变
    - 技能/目标/效果验证失败时使用默认值
    - 确保至少有一个有效目标
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
        await ChatClient.gather_request_post(clients=chat_clients)

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

        # 获取可选目标
        available_targets = self._get_available_targets(entity)

        # 获取自身属性
        combat_stats_comp = entity.get(CombatStatsComponent)
        assert (
            combat_stats_comp is not None
        ), f"Entity {entity.name} must have CombatStatsComponent"

        actor_stats = {
            "hp": combat_stats_comp.stats.hp,
            "max_hp": combat_stats_comp.stats.max_hp,
            "attack": combat_stats_comp.stats.attack,
            "defense": combat_stats_comp.stats.defense,
        }

        # 获取当前状态效果
        draw_cards_action = entity.get(DrawCardsAction)
        assert (
            draw_cards_action is not None
        ), f"Entity {entity.name} must have DrawCardsAction"
        actor_status_effects = draw_cards_action.status_effects

        # 生成提示词
        prompt = _generate_enemy_decision_prompt(
            actor_name=entity.name,
            available_skills=available_skills,
            available_targets=available_targets,
            actor_stats=actor_stats,
            actor_status_effects=actor_status_effects,
            current_round=current_round,
        )

        # 创建并返回聊天客户端
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

            # 添加压缩提示词到历史
            self._game.add_human_message(
                entity=entity,
                message_content=_generate_compressed_decision_prompt(current_round),
                compressed_prompt=chat_client.prompt,
            )

            # 添加 AI 响应到历史
            self._game.add_ai_message(entity, chat_client.response_ai_messages)

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

            # 筛选状态效果
            filtered_effects = self._filter_effects(
                entity, validated_response.selected_effects
            )

            # 记录决策结果（调试用）
            logger.debug(
                f"{entity.name} 决策: 技能=[{selected_skill.name}] "
                f"目标={validated_targets} 效果数={len(filtered_effects)} "
                f"理由: {validated_response.reasoning}"
            )

            # 修改 DrawCardsAction
            entity.replace(
                DrawCardsAction,
                entity.name,
                selected_skill,
                validated_targets,
                filtered_effects,
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
    def _get_available_targets(self, entity: Entity) -> List[Dict[str, Any]]:
        """
        获取可选目标的详细信息列表

        Args:
            entity: 敌人实体

        Returns:
            目标信息列表，每个元素包含 name/hp/max_hp/attack/defense/effects
        """
        # 获取场景上所有存活的角色
        actor_entities = self._game.get_alive_actors_on_stage(entity)

        # 筛选出友方角色（敌人的目标）
        ally_entities = [actor for actor in actor_entities if actor.has(AllyComponent)]

        targets = []
        for ally in ally_entities:
            combat_stats = ally.get(CombatStatsComponent)
            if combat_stats is None:
                continue

            targets.append(
                {
                    "name": ally.name,
                    "hp": combat_stats.stats.hp,
                    "max_hp": combat_stats.stats.max_hp,
                    "attack": combat_stats.stats.attack,
                    "defense": combat_stats.stats.defense,
                    "effects": combat_stats.status_effects.copy(),
                }
            )

        return targets

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

        # 获取场景上所有存活的友方角色
        actor_entities = self._game.get_alive_actors_on_stage(entity)
        valid_ally_names = {
            actor.name for actor in actor_entities if actor.has(AllyComponent)
        }

        # 筛选有效目标
        validated = [name for name in target_names if name in valid_ally_names]

        if len(validated) == 0:
            logger.warning(f"{entity.name}: 所有目标都无效 {target_names}")

        return validated

    ####################################################################################################################################
    def _filter_effects(
        self, entity: Entity, effect_names: List[str]
    ) -> List[StatusEffect]:
        """
        筛选状态效果

        Args:
            entity: 敌人实体
            effect_names: LLM 选择的效果名称列表

        Returns:
            验证通过的状态效果列表（可为空）
        """
        if len(effect_names) == 0:
            return []

        # 获取当前所有状态效果
        draw_cards_action = entity.get(DrawCardsAction)
        assert draw_cards_action is not None
        current_effects = draw_cards_action.status_effects

        # 筛选匹配的效果
        filtered = [effect for effect in current_effects if effect.name in effect_names]

        if len(filtered) < len(effect_names):
            logger.debug(
                f"{entity.name}: 部分效果名称无效，筛选后 {len(filtered)}/{len(effect_names)}"
            )

        return filtered

    ####################################################################################################################################
