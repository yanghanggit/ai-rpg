"""战斗仲裁动作系统模块。

AI驱动的战斗结算系统，负责根据所有参战角色的出牌动作进行战斗仲裁。
系统生成优化的仲裁提示词，调用AI进行战斗结算，并处理返回的战斗结果。

核心流程：
1. 收集所有参战角色的卡牌和目标信息
2. 生成战斗仲裁提示词（行动顺序 + 角色生命 + 卡牌属性）
3. 调用AI进行战斗计算，生成战斗日志和演出描述
4. 更新参战角色的HP值，清除已消耗的状态效果
5. 向所有参战角色广播战斗结果
6. 处理生命值归零的角色，添加死亡组件

注意：仅在战斗进行中(ongoing)阶段执行。
"""

from typing import Dict, Final, List, NamedTuple, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..chat_services.client import ChatClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    ArbitrationAction,
    DungeonComponent,
    PlayCardsAction,
    CombatStatsComponent,
    Card,
    StageComponent,
    DeathComponent,
    CombatArbitrationEvent,
    StatusEffect,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class ArbitrationResponse(BaseModel):
    combat_log: str
    final_hp: Dict[str, int]
    narrative: str


#######################################################################################################################################
@final
class CombatActionInfo(NamedTuple):
    actor: str
    targets: List[str]
    card: Card
    combat_stats_component: CombatStatsComponent


#######################################################################################################################################
def _generate_actor_card_details(
    combat_actions_details: List[CombatActionInfo],
) -> List[str]:
    """生成参战角色的卡牌详情列表。

    为每个参战角色生成格式化的战斗信息，包含角色当前生命值和出牌的完整信息
    （卡牌名称、目标、描述、属性）。卡牌属性已包含状态效果修正后的最终数值。

    Args:
        combat_actions_details: 战斗行动信息列表，包含角色名、卡牌、目标等

    Returns:
        格式化的角色卡牌详情字符串列表，每个元素对应一个参战角色
    """
    details_prompt: List[str] = []
    for param in combat_actions_details:
        assert param.card.name != ""

        # 格式化目标显示
        if len(param.targets) == 0:
            target_display = "无目标"
            logger.warning(f"{param.actor} 的出牌动作没有目标！")
        elif len(param.targets) == 1:
            target_display = param.targets[0]
        else:
            target_display = f"[{', '.join(param.targets)}]"

        # 获取角色当前生命值
        actor_hp = param.combat_stats_component.stats.hp
        actor_max_hp = param.combat_stats_component.stats.max_hp

        # 获取卡牌属性（已包含状态效果修正）
        card_stats = param.card.stats

        detail = f"""### {param.actor}

HP:{actor_hp}/{actor_max_hp} | 攻击:{card_stats.attack} | 防御:{card_stats.defense}

{param.card.name} -> {target_display}
{param.card.description}"""

        details_prompt.append(detail)

    return details_prompt


#######################################################################################################################################
def _generate_hp_update_notification(final_hp: int, max_hp: int) -> str:
    """生成HP更新通知消息

    Args:
        final_hp: 更新后的当前HP
        max_hp: 最大HP

    Returns:
        str: 格式化的HP更新通知消息
    """
    return f"""# 通知！你的生命值已更新

当前HP: {final_hp}/{max_hp}"""


#######################################################################################################################################
def _generate_status_effects_consumed_notification(
    consumed_effects: List[StatusEffect],
) -> str:
    """生成状态效果消耗通知消息

    Args:
        consumed_effects: 已被消耗的状态效果列表

    Returns:
        str: 格式化的状态效果消耗通知消息
    """
    effects_list = "\n".join([f"- {effect.name}" for effect in consumed_effects])
    return f"""# 通知！以下状态效果已被消耗移除

{effects_list}"""


#######################################################################################################################################
def _generate_defeat_notification() -> str:
    """生成角色被击败通知消息

    Returns:
        str: 击败通知消息
    """
    return """# 通知！你已被击败！"""


#######################################################################################################################################
def _generate_combat_arbitration_broadcast(
    combat_log: str, narrative: str, current_round_number: int
) -> str:
    """生成战斗仲裁广播消息。

    Args:
        combat_log: 战斗数据日志
        narrative: 战斗演出描述
        current_round_number: 当前回合数

    Returns:
        格式化的战斗广播消息，包含演出和数据日志
    """

    return f"""# 通知！第 {current_round_number} 回合结算

## 战斗演出

{narrative}

## 数据日志

{combat_log}"""


#######################################################################################################################################
def _generate_combat_arbitration_prompt(
    combat_actions_details: List[CombatActionInfo],
    current_round_number: int,
) -> str:
    """生成战斗仲裁提示词。

    生成给AI的完整仲裁指令，包含行动顺序、角色信息、战斗规则和输出JSON格式。
    支持复活机制（多段HP变化X→0→Y）和环境互动。

    Args:
        combat_actions_details: 战斗行动信息列表
        current_round_number: 当前回合数

    Returns:
        完整的仲裁提示词字符串
    """
    # 生成角色&卡牌详情
    details_prompt = _generate_actor_card_details(combat_actions_details)

    return f"""# 指令！第 {current_round_number} 回合：完成战斗结算与演出，以JSON格式返回。

## 行动顺序

{" → ".join([param.actor for param in combat_actions_details])}

先手角色行动优先生效，可改变环境与战场状态，影响后续角色的行动结果。

## 参战信息

{"\n\n".join(details_prompt)}

**注意**：HP:X/Y的X是本回合起始HP，combat_log的"HP:角色=X→..."必须使用该值。

## 战斗计算

严格按照 System 提示词的 **## 战斗机制** 进行计算

## 仲裁规则

- 角色可利用或改变环境物体（先到先得）
- 环境变化影响后续角色行动

## 输出格式

```json
{{
  "combat_log": "[角色A|卡牌A→环境A→角色X:伤10 代价:防-2] [角色B|卡牌B→环境B→角色Y:伤50 代价:攻-3] [角色C|卡牌C→角色Z:伤8] HP:角色A=45/50 角色B=30→25/40 角色C=50/50 角色X=40→30/50 角色Y=35→0→50/50 角色Z=42→34/50 [环境]效果1+效果2",
  "final_hp": {{
    "A角色全名": 45,
    "B角色全名": 25,
    "C角色全名": 50,
    "X角色全名": 30,
    "Y角色全名": 50,
    "Z角色全名": 34
  }},
  "narrative": "战斗过程的故事化描述"
}}
```

**约束**

- combat_log：格式 `[角色简名|卡牌→环境→目标:效果 代价:X]` 依次记录每个角色的完整行动流程，`HP:角色=X→Y/Z` 集中记录所有角色最终HP（支持多段变化X→Y→Z），`[环境]关键词` 最后记录环境变化。角色名仅保留最后一段
- final_hp：字典格式，键为**角色全名**，值为该角色的最终HP数值（与combat_log中HP部分的最终值一致）
- narrative：感官描写、禁数字、简洁扼要
- 严格按上述JSON格式输出"""


###########################################################################################################################################
@final
class ArbitrationActionSystem(ReactiveProcessor):
    """战斗仲裁系统

    AI驱动的战斗结算系统，生成优化的仲裁提示词并处理AI返回的战斗结果。

    核心优化:
    - Token压缩60%：紧凑格式 + 精简规则 + 内嵌示例
    - 完整流程：卡牌 → 环境 → 效果 → 代价 → HP → 环境
    - 支持复活：多段HP变化(X→0→Y)自动识别
    - 扩展性强：支持1v1到3v3及更多角色
    """

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: Final[TCGGame] = game_context

    #######################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(ArbitrationAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(ArbitrationAction) and entity.has(StageComponent)

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:

        assert (
            self._game.current_combat_sequence.is_ongoing
        ), "当前没有进行中的战斗序列！"
        assert len(entities) == 1, "当前只能有一个场景实体进行仲裁处理！"

        # 排序角色！
        stage_entity = entities[0]
        assert stage_entity.has(StageComponent) and stage_entity.has(
            DungeonComponent
        ), "场景实体缺少StageComponent或DungeonComponent！"

        # 获取所有出牌动作的角色实体
        play_cards_actors = self._game.get_group(
            Matcher(
                all_of=[
                    PlayCardsAction,
                ],
            )
        ).entities

        assert len(play_cards_actors) > 0, "没有检测到任何出牌动作的角色！"
        if len(play_cards_actors) == 0:
            logger.warning("没有检测到任何出牌动作的角色！")
            return

        # 依据当前回合的行动顺序排序角色实体
        sort_actors: List[Entity] = []
        for (
            action_order
        ) in self._game.current_combat_sequence.latest_round.action_order:
            for entity in play_cards_actors:
                assert not entity.has(DeathComponent)
                if entity.name == action_order:
                    sort_actors.append(entity)
                    break

        # 日志输出排序结果
        for sort_actor in sort_actors:
            logger.info(f"sort_actor: {sort_actor.name}")

        # 发起仲裁请求
        await self._request_combat_arbitration(stage_entity, sort_actors)

    #######################################################################################################################################
    def _collect_combat_action_info(
        self, react_entities: List[Entity]
    ) -> List[CombatActionInfo]:
        """收集参战角色的行动信息。

        从实体列表中提取卡牌、目标和战斗属性，组装成CombatActionInfo列表。

        Args:
            react_entities: 参战角色实体列表

        Returns:
            战斗行动信息列表
        """
        ret: List[CombatActionInfo] = []
        for entity in react_entities:

            play_cards_action = entity.get(PlayCardsAction)
            assert play_cards_action.card.name != "", "出牌动作缺少卡牌信息！"

            ret.append(
                CombatActionInfo(
                    actor=entity.name,
                    targets=play_cards_action.targets,
                    card=play_cards_action.card,
                    combat_stats_component=entity.get(CombatStatsComponent),
                )
            )

        return ret

    #######################################################################################################################################
    async def _request_combat_arbitration(
        self, stage_entity: Entity, actor_entities: List[Entity]
    ) -> None:
        """发起AI战斗仲裁请求。

        生成仲裁提示词，调用ChatClient进行AI推理，并应用返回的战斗结果。
        处理流程：生成提示词 → 调用ChatClient → 应用结果 → 清除状态效果 → 处理死亡。

        Args:
            stage_entity: 场景实体
            actor_entities: 参战角色实体列表（已按行动顺序排序）
        """
        # 生成推理参数。
        combat_actions_details = self._collect_combat_action_info(actor_entities)
        assert len(combat_actions_details) > 0

        # 获取当前回合数
        current_round_number = len(self._game.current_combat_sequence.current_rounds)

        # 生成推理信息。
        message = _generate_combat_arbitration_prompt(
            combat_actions_details, current_round_number
        )

        # 用场景推理
        chat_client = ChatClient(
            name=stage_entity.name,
            prompt=message,
            context=self._game.get_agent_context(stage_entity).context,
            timeout=60 * 2,  # 战斗推理允许更长时间
        )

        # 用语言服务系统进行推理。
        chat_client.request_post()

        # 处理返回结果。
        self._apply_arbitration_result(
            stage_entity, chat_client, actor_entities, combat_actions_details
        )

        # 清除已消耗的状态效果（已合入卡牌并打出）
        self._clear_consumed_status_effects(combat_actions_details)

        # 处理生命值归零的实体
        self._process_zero_health_entities()

    #######################################################################################################################################
    def _clear_consumed_status_effects(
        self, combat_actions_details: List[CombatActionInfo]
    ) -> None:
        """清除已消耗的状态效果。

        状态效果已在DrawCards阶段合入卡牌数值，
        卡牌打出后这些状态效果应被清除。

        Args:
            combat_actions_details: 战斗行动信息列表
        """
        for action_info in combat_actions_details:
            # 通过角色名称获取实体
            entity = self._game.get_entity_by_name(action_info.actor)
            if entity is None:
                logger.warning(f"无法找到角色实体: {action_info.actor}")
                continue

            # 获取战斗属性组件
            combat_stats = entity.get(CombatStatsComponent)
            if combat_stats is None:
                logger.warning(f"角色 {action_info.actor} 缺少 CombatStatsComponent")
                continue

            # 从卡牌中获取已消耗的状态效果
            consumed_effects = action_info.card.status_effects
            if len(consumed_effects) == 0:
                continue

            # 从角色的状态效果列表中移除已消耗的效果
            for consumed_effect in consumed_effects:
                # 通过名称匹配移除
                combat_stats.status_effects = [
                    effect
                    for effect in combat_stats.status_effects
                    if effect.name != consumed_effect.name
                ]

            logger.debug(
                f"清除 {action_info.actor} 的 {len(consumed_effects)} 个已消耗状态效果"
            )

            # 通知角色状态效果已被消耗
            self._game.add_human_message(
                entity=entity,
                message_content=_generate_status_effects_consumed_notification(
                    consumed_effects
                ),
            )

    #######################################################################################################################################
    def _apply_arbitration_result(
        self,
        stage_entity: Entity,
        chat_client: ChatClient,
        actor_entities: List[Entity],
        combat_actions_details: List[CombatActionInfo],
    ) -> None:
        """应用AI仲裁结果。

        解析AI返回的JSON数据，更新场景上下文，广播战斗结果，
        更新所有参战角色的HP值，并记录战斗数据。

        Args:
            stage_entity: 场景实体
            chat_client: ChatClient实例，包含AI返回结果
            actor_entities: 参战角色实体列表
            combat_actions_details: 战斗行动信息列表（未使用）
        """
        try:

            format_response = ArbitrationResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            # 添加上下文
            self._game.add_human_message(
                entity=stage_entity,
                message_content=chat_client.prompt,
            )

            # 添加AI回复
            self._game.add_ai_message(
                entity=stage_entity,
                ai_messages=chat_client.response_ai_messages,
            )

            # 推理的场景记录下！
            arbitration_action = stage_entity.get(ArbitrationAction)
            stage_entity.replace(
                ArbitrationAction,
                arbitration_action.name,
                format_response.combat_log,
                format_response.narrative,
            )

            # 获取当前回合数
            current_round_number = len(
                self._game.current_combat_sequence.current_rounds
            )

            # 广播事件
            self._game.broadcast_to_stage(
                entity=stage_entity,
                agent_event=CombatArbitrationEvent(
                    message=_generate_combat_arbitration_broadcast(
                        format_response.combat_log,
                        format_response.narrative,
                        current_round_number,
                    ),
                    stage=stage_entity.name,
                    combat_log=format_response.combat_log,
                    narrative=format_response.narrative,
                ),
                exclude_entities={stage_entity},  # 排除场景实体自身
            )

            # 更新参战角色的HP
            for entity in actor_entities:
                actor_name = entity.name

                # 从LLM返回的结果中获取该角色的最终HP
                if actor_name not in format_response.final_hp:
                    logger.warning(f"LLM返回结果中缺少角色 {actor_name} 的HP数据")
                    continue

                final_hp = format_response.final_hp[actor_name]

                # 获取战斗属性组件
                combat_stats = entity.get(CombatStatsComponent)
                if combat_stats is None:
                    logger.warning(f"角色 {actor_name} 缺少 CombatStatsComponent")
                    continue

                # 更新当前HP
                old_hp = combat_stats.stats.hp
                combat_stats.stats.hp = final_hp
                max_hp = combat_stats.stats.max_hp

                logger.info(f"更新 {actor_name} HP: {old_hp} → {final_hp}/{max_hp}")

                # 通知角色HP变化
                self._game.add_human_message(
                    entity=entity,
                    message_content=_generate_hp_update_notification(final_hp, max_hp),
                )

            # 记录数据！
            latest_round = self._game.current_combat_sequence.latest_round
            latest_round.combat_log = format_response.combat_log
            latest_round.narrative = format_response.narrative

        except Exception as e:
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
    def _process_zero_health_entities(self) -> None:
        """处理生命值归零的实体，为其添加死亡组件。

        遍历所有拥有战斗属性但尚未标记为死亡的实体，
        检查其生命值是否小于等于0。如果是，则:
        1. 记录死亡日志
        2. 向该实体发送被击败通知消息
        3. 为实体添加死亡组件(DeathComponent)
        """
        defeated_entities = self._game.get_group(
            Matcher(all_of=[CombatStatsComponent], none_of=[DeathComponent])
        ).entities.copy()

        for entity in defeated_entities:
            combat_stats_comp = entity.get(CombatStatsComponent)
            if combat_stats_comp.stats.hp <= 0:

                logger.warning(f"{combat_stats_comp.name} is dead")
                self._game.add_human_message(entity, _generate_defeat_notification())
                entity.replace(DeathComponent, combat_stats_comp.name)

    #######################################################################################################################################
