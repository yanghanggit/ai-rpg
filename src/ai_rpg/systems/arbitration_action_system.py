"""战斗仲裁动作系统模块。

AI驱动的战斗结算系统，负责根据所有参战角色的出牌动作进行战斗仲裁。
系统生成优化的仲裁提示词，调用AI进行战斗结算，并处理返回的战斗结果。

核心流程：
1. 收集所有参战角色的卡牌和目标信息
2. 生成战斗仲裁提示词（卡牌结算序列 + 战斗导演职责 + 输出格式）
3. 调用AI进行战斗计算，生成多行结构的战斗日志和演出描述
4. 更新参战角色的HP值，清除已消耗的状态效果
5. 向所有参战角色广播战斗结果
6. 处理生命值归零的角色，添加死亡组件

提示词优化：
- combat_log采用多行格式，每行=一张卡牌执行结果
- 效果描述要求具体化（如"击中侧腹"而非占位符）
- 简化规则说明，删除冗余示例模板
- Token压缩约25%，清晰度不受影响

注意：仅在战斗进行中(ongoing)阶段执行。
"""

from typing import Dict, Final, List, NamedTuple, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..chat_client.client import ChatClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
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
    final_hp: Dict[str, float]
    narrative: str


#######################################################################################################################################
@final
class CombatActionInfo(NamedTuple):
    actor: str
    targets: List[str]
    card: Card
    combat_stats_component: CombatStatsComponent


#######################################################################################################################################
def _generate_card_sequence_details(
    combat_actions_details: List[CombatActionInfo],
) -> List[str]:
    """生成卡牌结算序列详情列表。

    以卡牌为基本单元，按照行动顺序为每张卡牌生成完整信息，包含：
    出牌者信息（名称、HP、攻防属性）、目标、卡牌描述、词条。
    卡牌属性已包含状态效果修正后的最终数值。
    词条为固有特性，有词条时逐条列出，无词条时显示"无"。

    Args:
        combat_actions_details: 战斗行动信息列表，包含角色名、卡牌、目标等

    Returns:
        格式化的卡牌详情字符串列表，每个元素对应一张卡牌
    """
    details_prompt: List[str] = []
    for index, param in enumerate(combat_actions_details, start=1):
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

        # 格式化词条列表
        if param.card.affixes:
            affixes_text = "\n".join([f"  - {affix}" for affix in param.card.affixes])
            affixes_display = f"\n{affixes_text}"
        else:
            affixes_display = "\n  - 无"

        detail = f"""### {index}. 卡牌：{param.card.name}

- **出牌者**：{param.actor} | HP:{actor_hp}/{actor_max_hp} | 攻击:{card_stats.attack} | 防御:{card_stats.defense}
- **目标**：{target_display}
- **行动**：{param.card.action}
- **规则**：{affixes_display}"""

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
    return """# 通知！你的HP已归零，失去战斗能力！"""


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
    """生成战斗仲裁提示词（简化版）。

    提示词结构：卡牌结算序列 → 战斗导演职责 → 输出格式规范。
    输出JSON包含多行combat_log、final_hp字典、narrative演出描述。
    简化版：将【机制】、【代价】、词条统一为"规则列表"。

    Args:
        combat_actions_details: 战斗行动信息列表（已按行动顺序排序）
        current_round_number: 当前回合数

    Returns:
        完整的仲裁提示词字符串
    """
    # 生成卡牌结算序列详情
    card_sequence_prompt = _generate_card_sequence_details(combat_actions_details)

    return f"""# 指令！第 {current_round_number} 回合：完成战斗结算与演出，以JSON格式返回。

## 1. 卡牌数据

卡牌封装了角色的完整战斗行动信息：

- **出牌者**：角色名、当前HP/最大HP、攻击力、防御力
- **目标**：行动目标角色名列表
- **行动**：第一人称叙事描述
- **规则**：所有战斗规则的统一列表（包含战术、代价、装备效果等）

{"\n\n".join(card_sequence_prompt)}

## 2. 战斗计算公式

结算每张卡牌时按以下步骤：

1. **确定参数**
   - 出牌者攻击力：从该卡牌"出牌者"行获取
   - 目标防御力：从目标卡牌"出牌者"行获取
   - 阅读**规则**列表，分析并应用所有数值修正或特殊触发条件
   
2. **计算伤害**
   - 伤害值 = max(1, 修正后攻击力 - 修正后防御力)
   
3. **更新HP**
   - 最终HP = max(0, min(当前HP - 伤害值, 最大HP))

4. **识别附加效果**
   - 从**规则**列表中识别除HP/攻击/防御数值变化之外的其他效果
   - 这类效果通常描述状态改变、行为限制、持续影响等非即时数值变化的规则
   - 若存在此类效果，提取其核心描述关键词（见第5节格式约束）

## 3. 战斗导演职责

你的任务：

1. **按序结算卡牌**
   依照卡牌顺序逐张处理，每张卡牌结算前检查出牌者当前HP：
   
   - **HP > 0**：正常执行上述公式
   
   - **HP = 0**：阅读该卡牌的**规则**列表，判断其效果设计：
     - 若效果明确声明"死后仍可触发"（如遗言效果、临死反击、死亡爆发等生命终结时触发的特殊机制），则正常执行上述公式
     - 若效果为常规战斗行动（如普通攻击、防御、增益等生存状态下的行为），则跳过结算

2. **先手影响后手**
   先执行的卡牌可改变环境，影响后续卡牌的结算条件

3. **记录完整过程**
   在combat_log中显示每张卡牌的处理结果（包括正常结算、特殊触发、跳过），可选地记录环境变化

## 4. 输出格式

```json
{{
  "combat_log": "多行字符串",
  "final_hp": {{}},
  "narrative": "战斗演出"
}}
```

## 5. 输出规范

### combat_log格式

**重要**：所有角色名统一使用 简名（全名最后一段）

**正常结算**：
```
[简名|卡牌→目标:攻击X,防御Y,伤害Z,效果:关键词] HP:简名1 X→Y，简名2 M/M
```

**跳过结算**：
```
[简名|已阵亡，卡牌无法执行]
```

**补充说明**：
- 攻击X、防御Y：规则列表修正后的最终值
- 效果关键词：从规则列表提取非数值影响，多个用+连接（无效果时省略`,效果:关键词`）
- 环境互动（可选）：`[简名|卡牌→目标→环境物]` 或 `[环境]关键词`

### final_hp格式

字典：`{{"角色全名": HP数值}}`

**约束**：0 ≤ HP ≤ 最大HP

### narrative格式

80-150字，第三人称外部视角，纯感官描写，无数字/术语/内心"""


###########################################################################################################################################
@final
class ArbitrationActionSystem(ReactiveProcessor):
    """战斗仲裁系统

    AI驱动的战斗结算系统，生成优化的仲裁提示词并处理AI返回的战斗结果。

    核心特性:
    - 卡牌为基本单元：按行动顺序逐张结算，先手可影响后手
    - 多行日志格式：每行记录一张卡牌执行，结构清晰易解析
    - 效果描述具体化：要求AI输出实际影响而非占位符
    - 环境互动支持：可选环境物、代价标记、环境总结行
    - Token优化：精简规则说明，删除冗余示例，压缩约25%
    - 扩展性强：支持任意角色数量（2人、4人、6人等）
    """

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: Final[TCGGame] = game_context

    #######################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(PlayCardsAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(PlayCardsAction)

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:

        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "无法获取玩家实体！"

        combat_stage = self._game.resolve_stage_entity(player_entity)
        assert combat_stage is not None, "无法获取玩家所在场景实体！"

        assert (
            self._game.current_combat_sequence.is_ongoing
        ), "当前没有进行中的战斗序列！"

        # 排序角色！
        assert combat_stage.has(StageComponent) and combat_stage.has(
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
        await self._request_combat_arbitration(combat_stage, sort_actors)

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
        chat_client.chat()

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

            logger.info(
                f"清除 {action_info.actor} 的 {len(consumed_effects)} 个已消耗状态效果(在本轮仲裁中，被消耗与清除): "
                f"{[f'{e.name}: {e.formatted_description}' for e in consumed_effects]}"
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
                max_hp = combat_stats.stats.max_hp
                combat_stats.stats.hp = int(max(0, min(final_hp, max_hp)))
                logger.info(
                    f"更新 {actor_name} HP: {old_hp} → {int(final_hp)}/{max_hp}"
                )

                # 通知角色HP变化
                self._game.add_human_message(
                    entity=entity,
                    message_content=_generate_hp_update_notification(
                        int(final_hp), max_hp
                    ),
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

                # logger.warning(f"{combat_stats_comp.name} is dead")
                self._game.add_human_message(entity, _generate_defeat_notification())
                entity.replace(DeathComponent, combat_stats_comp.name)

    #######################################################################################################################################
