"""战斗仲裁动作系统模块。

响应 PlayCardsAction 事件，对每次单张出牌立即进行 AI 仲裁结算。
每次 pipeline.process() 只有一个角色出牌（ActionCleanupSystem 保证），仲裁随即触发。

核心流程：
1. 从 PlayCardsAction 提取卡牌（name/damage/block/action）与目标列表
2. 解析目标实体的当前 HP，构建仲裁提示词
3. 调用 AI 计算伤害、更新 HP，生成战斗日志与演出描述
4. 遍历 final_hp 更新所有受影响角色（出牌者与目标）的 HP
5. 处理生命值归零的角色，添加死亡组件
"""

from typing import Dict, Final, List, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..chat_client.client import ChatClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    PlayCardsAction,
    BlockComponent,
    CharacterStatsComponent,
    DeathComponent,
    CombatArbitrationEvent,
    StatusEffectsComponent,
    StatusEffect,
    StatusEffectPhase,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class EntityFinalStats(BaseModel):
    hp: float
    block: int


#######################################################################################################################################
@final
class ArbitrationResponse(BaseModel):
    combat_log: str
    final_stats: Dict[str, EntityFinalStats]
    narrative: str


#######################################################################################################################################
def _generate_stats_update_notification(final_hp: int, max_hp: int, block: int) -> str:
    """生成HP与格挡更新通知消息

    Args:
        final_hp: 更新后的当前HP
        max_hp: 最大HP
        block: 结算后的格挡值

    Returns:
        str: 格式化的属性更新通知消息
    """
    return f"""# 你的生命值已更新

当前HP: {final_hp}/{max_hp}
当前格挡: {block}"""


#######################################################################################################################################
def _generate_defeat_notification() -> str:
    """生成角色被击败通知消息

    Returns:
        str: 击败通知消息
    """
    return """# 你的HP已归零，失去战斗能力！"""


#######################################################################################################################################
def _generate_combat_arbitration_broadcast(
    combat_log: str, narrative: str, current_round_number: int, actor_name: str
) -> str:
    """生成战斗仲裁广播消息。

    Args:
        combat_log: 战斗数据日志
        narrative: 战斗演出描述
        current_round_number: 当前回合数
        actor_name: 出牌角色全名

    Returns:
        格式化的战斗广播消息，包含演出和数据日志
    """
    actor_short_name = actor_name.split(".")[-1]
    return f"""# 第 {current_round_number} 回合 · {actor_short_name} 出牌仲裁

## 战斗演出

{narrative}

## 数据日志

{combat_log}"""


#######################################################################################################################################
def _generate_combat_arbitration_prompt(
    actor_name: str,
    actor_stats: CharacterStatsComponent,
    actor_block: int,
    play_cards_action: PlayCardsAction,
    target_stats: Dict[str, CharacterStatsComponent],
    target_blocks: Dict[str, int],
    current_round_number: int,
    actor_arbitration_effects: List[StatusEffect],
    target_arbitration_effects: Dict[str, List[StatusEffect]],
) -> str:
    target_lines = (
        "\n".join(
            f"- {name}（HP {stats.stats.hp}/{stats.stats.max_hp}，当前格挡 {target_blocks.get(name, 0)}）"
            for name, stats in target_stats.items()
        )
        if target_stats
        else "- 无目标"
    )

    def _fmt_duration(duration: int) -> str:
        return "永久" if duration == -1 else f"剩余{duration}回合"

    def _fmt_effects(effects: List[StatusEffect]) -> str:
        if not effects:
            return "  无"
        return "\n".join(
            f"  - {e.name}（{_fmt_duration(e.duration)}）: {e.description}"
            for e in effects
        )

    arbitration_effects_lines = (
        f"**出牌者 —— {actor_name}**:\n{_fmt_effects(actor_arbitration_effects)}"
    )
    for t_name, t_effects in target_arbitration_effects.items():
        arbitration_effects_lines += (
            f"\n\n**目标 —— {t_name}**:\n{_fmt_effects(t_effects)}"
        )

    action_line = (
        f"- 行动：{play_cards_action.action}"
        if play_cards_action.action
        else "- 行动：（未提供，请根据卡牌描述与战场情境自行演绎）"
    )

    return f"""# 第 {current_round_number} 回合：战斗结算（以 JSON 格式返回）

## 出牌者

{actor_name}（HP {actor_stats.stats.hp}/{actor_stats.stats.max_hp}，当前格挡 {actor_block}）

## 出牌

- 卡牌：{play_cards_action.card.name}
- damage_dealt：{play_cards_action.card.damage_dealt}（单次伤害）
- hit_count：{play_cards_action.card.hit_count}（攻击次数）
- block_gain：{play_cards_action.card.block_gain}
{action_line}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}

## 计算规则

**格挡优先消耗**：出牌者先获得 block_gain 格挡（出牌者结算后格挡 = 当前格挡 + block_gain）。
多段攻击逐段结算（hit_count 次）：
  每段实际伤害 = max(0, damage_dealt − 目标当前剩余 block)
  本段 block 消耗量 = min(damage_dealt, 目标当前剩余 block)
  每段命中后，目标 block -= 本段 block 消耗量（block 不低于 0）
  总伤害 = 各段实际伤害之和
目标 HP = max(0, min(当前 HP − 总伤害, 最大 HP))
若 hit_count = 1，按单段正常结算即可
若出牌者 HP 已为 0，跳过结算
仲裁状态效果中的数值修正（额外 hp 扣除、block 加成、伤害加成等）**叠加**到上述计算规则之上，体现在 final_stats 中。

## 输出格式

```json
{{
  "combat_log": "字符串",
  "final_stats": {{}},
  "narrative": "战斗演出"
}}
```

### combat_log（简名 = 全名最后一段）

正常：`[出牌者简名|卡牌→目标:damage Xx击_count次,伤害Z] HP:目标简名 旧→新`
多段示例：`[英雄|回旋镖→石缝蜥:3x3次,伤害7] HP:石缝蜥 15→8`
阵亡跳过：`[出牌者简名|已阵亡，卡牌无法执行]`

### final_stats

必须包含**出牌者与所有目标**，格式：
```json
{{"角色全名": {{"hp": 数值, "block": 数值}}}}
```
- hp：0 ≤ hp ≤ 最大 HP
- block：结算后剩余格挡（出牌者 = 当前格挡 + block_gain；目标 = 当前格挡 − 消耗量，不低于 0）

### narrative

80-150 字，第三人称外部视角，纯感官描写，无数字/术语/内心."""


###########################################################################################################################################
@final
class ArbitrationActionSystem(ReactiveProcessor):
    """战斗仲裁系统

    响应每次 PlayCardsAction 事件，立即对该单张出牌进行 AI 仲裁结算。
    每次 pipeline.process() 只有一个角色出牌，仲裁随即触发。
    """

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    #######################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(PlayCardsAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(PlayCardsAction) and entity.has(BlockComponent)

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:

        # 仅在战斗进行中时触发（is_ongoing 守卫）
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("ArbitrationActionSystem: 战斗未进行中，跳过仲裁")
            return

        # 开始处理仲裁。
        for entity in entities:
            stage_entity = self._game.resolve_stage_entity(entity)
            assert stage_entity is not None, f"无法获取 {entity.name} 所在场景实体！"
            logger.debug(f"ArbitrationActionSystem: [{entity.name}] 触发仲裁")
            await self._request_combat_arbitration(stage_entity, entity)

    #######################################################################################################################################
    async def _request_combat_arbitration(
        self, stage_entity: Entity, actor_entity: Entity
    ) -> None:

        action = actor_entity.get(PlayCardsAction)
        if action.card.name == "":
            # 空卡表示 EnemyPlayDecisionSystem 推理失败，记录放弃行动结果
            logger.warning(
                f"ArbitrationActionSystem: [{actor_entity.name}] 出牌为空卡，执行放弃行动"
            )
            self._apply_forfeit_result(stage_entity, actor_entity)
            return

        # 解析目标实体的当前 HP 与格挡
        target_stats: Dict[str, CharacterStatsComponent] = {}
        target_blocks: Dict[str, int] = {}

        for target_name in action.targets:

            target_entity = self._game.get_entity_by_name(target_name)
            assert target_entity is not None, f"无法找到目标实体: {target_name}"

            assert target_entity.has(
                CharacterStatsComponent
            ), f"目标实体 {target_name} 缺少 CharacterStatsComponent！"
            target_stats[target_name] = target_entity.get(CharacterStatsComponent)

            assert target_entity.has(
                BlockComponent
            ), f"目标实体 {target_name} 缺少 BlockComponent！"
            target_blocks[target_name] = target_entity.get(BlockComponent).block

        # 解析出牌者的当前 HP 与格挡
        assert actor_entity.has(
            CharacterStatsComponent
        ), f"出牌实体 {actor_entity.name} 缺少 CharacterStatsComponent！"
        assert actor_entity.has(
            BlockComponent
        ), f"出牌实体 {actor_entity.name} 缺少 BlockComponent！"
        actor_block = actor_entity.get(BlockComponent).block
        current_round_number = len(self._game.current_dungeon.current_rounds or [])

        # 读取出牌者的 arbitration 相位状态效果
        actor_status_comp = actor_entity.get(StatusEffectsComponent)
        actor_arbitration_effects: List[StatusEffect] = [
            e
            for e in (
                actor_status_comp.status_effects
                if actor_status_comp is not None
                else []
            )
            if e.phase == StatusEffectPhase.ARBITRATION
        ]

        # 读取所有目标的 arbitration 相位状态效果
        target_arbitration_effects: Dict[str, List[StatusEffect]] = {}
        for target_name in action.targets:
            t_entity = self._game.get_entity_by_name(target_name)
            assert t_entity is not None, f"无法找到目标实体: {target_name}"
            # if t_entity is None:
            #     continue
            t_status_comp = t_entity.get(StatusEffectsComponent)
            target_arbitration_effects[target_name] = [
                e
                for e in (
                    t_status_comp.status_effects if t_status_comp is not None else []
                )
                if e.phase == StatusEffectPhase.ARBITRATION
            ]

        # 构建仲裁提示词
        message = _generate_combat_arbitration_prompt(
            actor_entity.name,
            actor_entity.get(CharacterStatsComponent),
            actor_block,
            action,
            target_stats,
            target_blocks,
            current_round_number,
            actor_arbitration_effects,
            target_arbitration_effects,
        )

        # 输出仲裁提示词日志，包含出牌者、卡牌信息、目标信息和当前回合数
        chat_client = ChatClient(
            name=stage_entity.name,
            prompt=message,
            context=self._game.get_agent_context(stage_entity).context,
            timeout=60 * 2,
        )
        chat_client.chat()

        # 应用仲裁结果
        self._apply_arbitration_result(stage_entity, chat_client, actor_entity.name)

        # 处理生命值归零的实体，添加死亡组件
        self._process_zero_health_entities()

    #######################################################################################################################################
    def _apply_forfeit_result(self, stage_entity: Entity, actor_entity: Entity) -> None:
        """处理空卡（放弃行动）的默认结算结果。

        当 EnemyPlayDecisionSystem 推理失败保留空卡时，以"放弃行动"作为本次出牌结果，
        补全 combat_log 和 narrative，并广播到场景。
        """
        short_name = actor_entity.name.split(".")[-1]
        combat_log = f"[{short_name}|放弃行动]"
        narrative = f"{short_name}迟疑片刻，最终放弃了这回合的行动。"

        current_round_number = len(self._game.current_dungeon.current_rounds or [])
        self._game.broadcast_to_stage(
            entity=stage_entity,
            agent_event=CombatArbitrationEvent(
                message=_generate_combat_arbitration_broadcast(
                    combat_log,
                    narrative,
                    current_round_number,
                    actor_entity.name,
                ),
                stage=stage_entity.name,
                combat_log=combat_log,
                narrative=narrative,
            ),
            exclude_entities={stage_entity},
        )

        latest_round = self._game.current_dungeon.latest_round
        assert latest_round is not None, "current_rounds 不应为 None"
        latest_round.combat_log.append(combat_log)
        latest_round.narrative.append(narrative)

    #######################################################################################################################################
    def _apply_arbitration_result(
        self,
        stage_entity: Entity,
        chat_client: ChatClient,
        actor_name: str,
    ) -> None:
        try:
            format_response = ArbitrationResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            self._game.add_human_message(
                entity=stage_entity,
                message_content=chat_client.prompt,
            )
            self._game.add_ai_message(
                entity=stage_entity,
                ai_messages=chat_client.response_ai_messages,
            )

            current_round_number = len(self._game.current_dungeon.current_rounds or [])
            self._game.broadcast_to_stage(
                entity=stage_entity,
                agent_event=CombatArbitrationEvent(
                    message=_generate_combat_arbitration_broadcast(
                        format_response.combat_log,
                        format_response.narrative,
                        current_round_number,
                        actor_name,
                    ),
                    stage=stage_entity.name,
                    combat_log=format_response.combat_log,
                    narrative=format_response.narrative,
                ),
                exclude_entities={stage_entity},
            )

            # 遍历 final_stats，更新所有受影响角色（出牌者与目标）的 HP 与格挡, LLM 生成的 final_stats 中必须包含出牌者与所有目标，有可能会有错误！
            for entity_name, entity_stats in format_response.final_stats.items():
                entity = self._game.get_entity_by_name(entity_name)
                assert (
                    entity is not None
                ), f"无法找到 final_stats 中的实体: {entity_name}"
                if entity is None:
                    logger.warning(f"final_stats 中找不到实体: {entity_name}")
                    continue

                assert entity.has(
                    CharacterStatsComponent
                ), f"实体 {entity_name} 缺少 CharacterStatsComponent！"
                combat_stats = entity.get(CharacterStatsComponent)

                old_hp = combat_stats.stats.hp
                max_hp = combat_stats.stats.max_hp
                new_hp = int(max(0, min(entity_stats.hp, max_hp)))
                combat_stats.stats.hp = new_hp
                logger.info(
                    f"更新 {entity_name} HP: {old_hp} → {new_hp}/{max_hp}, block: {entity_stats.block}"
                )

                new_block = max(0, entity_stats.block)
                entity.replace(BlockComponent, entity_name, new_block)

                self._game.add_human_message(
                    entity=entity,
                    message_content=_generate_stats_update_notification(
                        new_hp, max_hp, new_block
                    ),
                )

            latest_round = self._game.current_dungeon.latest_round
            assert latest_round is not None, "current_rounds 不应为 None"
            latest_round.combat_log.append(format_response.combat_log)
            latest_round.narrative.append(format_response.narrative)

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
            Matcher(all_of=[CharacterStatsComponent], none_of=[DeathComponent])
        ).entities.copy()

        for entity in defeated_entities:
            combat_stats_comp = entity.get(CharacterStatsComponent)

            # 只有当 HP 小于等于 0 时才处理死亡
            if combat_stats_comp.stats.hp <= 0:
                logger.info(f"{entity.name} 已被击败，HP={combat_stats_comp.stats.hp}")
                self._game.add_human_message(entity, _generate_defeat_notification())
                entity.replace(DeathComponent, combat_stats_comp.name)

    #######################################################################################################################################
