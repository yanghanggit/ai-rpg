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

from typing import Dict, Final, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..chat_client.client import ChatClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    PlayCardsAction,
    CharacterStatsComponent,
    DeathComponent,
    CombatArbitrationEvent,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class ArbitrationResponse(BaseModel):
    combat_log: str
    final_hp: Dict[str, float]
    narrative: str


#######################################################################################################################################
def _generate_hp_update_notification(final_hp: int, max_hp: int) -> str:
    """生成HP更新通知消息

    Args:
        final_hp: 更新后的当前HP
        max_hp: 最大HP

    Returns:
        str: 格式化的HP更新通知消息
    """
    return f"""# 你的生命值已更新

当前HP: {final_hp}/{max_hp}"""


#######################################################################################################################################
def _generate_defeat_notification() -> str:
    """生成角色被击败通知消息

    Returns:
        str: 击败通知消息
    """
    return """# 你的HP已归零，失去战斗能力！"""


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

    return f"""# 第 {current_round_number} 回合结算

## 战斗演出

{narrative}

## 数据日志

{combat_log}"""


#######################################################################################################################################
def _generate_combat_arbitration_prompt(
    actor_name: str,
    actor_stats: CharacterStatsComponent,
    action: PlayCardsAction,
    target_stats: Dict[str, CharacterStatsComponent],
    current_round_number: int,
) -> str:
    target_lines = (
        "\n".join(
            f"- {name}（HP {stats.stats.hp}/{stats.stats.max_hp}）"
            for name, stats in target_stats.items()
        )
        if target_stats
        else "- 无目标"
    )

    return f"""# 第 {current_round_number} 回合：战斗结算（以 JSON 格式返回）

## 出牌者

{actor_name}（HP {actor_stats.stats.hp}/{actor_stats.stats.max_hp}）

## 出牌

- 卡牌：{action.card.name}
- damage_dealt：{action.card.damage_dealt}（单次伤害）
- hit_count：{action.card.hit_count}（攻击次数）
- block_gain：{action.card.block_gain}
- 行动：{action.card.action}

## 目标

{target_lines}

## 计算规则

多段攻击逐段结算（hit_count 次）：
  每段实际伤害 = max(1, damage_dealt − 目标当前剩余 block)
  每段命中后，目标 block 减去本段消耗量（block 不低于 0）
  总伤害 = 各段实际伤害之和
目标 HP = max(0, min(当前 HP − 总伤害, 最大 HP))
若 hit_count = 1，按单段正常结算即可
若出牌者 HP 已为 0，跳过结算

## 输出格式

```json
{{
  "combat_log": "字符串",
  "final_hp": {{}},
  "narrative": "战斗演出"
}}
```

### combat_log（简名 = 全名最后一段）

正常：`[出牌者简名|卡牌→目标:damage Xx击_count次,伤害Z] HP:目标简名 旧→新`
多段示例：`[英雄|回旋镖→石缝蜥:3x3次,伤害7] HP:石缝蜥 15→8`
阵亡跳过：`[出牌者简名|已阵亡，卡牌无法执行]`

### final_hp

所有 HP 发生变化的角色，格式 `{{"角色全名": 数值}}`，0 ≤ HP ≤ 最大 HP。

### narrative

80-150 字，第三人称外部视角，纯感官描写，无数字/术语/内心。"""


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
        return entity.has(PlayCardsAction)

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("ArbitrationActionSystem: 战斗未进行中，跳过仲裁")
            return

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

        # 解析目标实体的当前 HP
        target_stats: Dict[str, CharacterStatsComponent] = {}
        for target_name in action.targets:
            target_entity = self._game.get_entity_by_name(target_name)
            if target_entity is not None:
                target_stats[target_name] = target_entity.get(CharacterStatsComponent)
            else:
                logger.warning(f"无法找到目标实体: {target_name}")

        current_round_number = len(self._game.current_dungeon.current_rounds or [])
        message = _generate_combat_arbitration_prompt(
            actor_entity.name,
            actor_entity.get(CharacterStatsComponent),
            action,
            target_stats,
            current_round_number,
        )

        chat_client = ChatClient(
            name=stage_entity.name,
            prompt=message,
            context=self._game.get_agent_context(stage_entity).context,
            timeout=60 * 2,
        )
        chat_client.chat()

        self._apply_arbitration_result(stage_entity, chat_client)
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
                ),
                stage=stage_entity.name,
                combat_log=combat_log,
                narrative=narrative,
            ),
            exclude_entities={stage_entity},
        )

        latest_round = self._game.current_dungeon.latest_round
        assert latest_round is not None
        latest_round.combat_log.append(combat_log)
        latest_round.narrative.append(narrative)

    #######################################################################################################################################
    def _apply_arbitration_result(
        self,
        stage_entity: Entity,
        chat_client: ChatClient,
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
                    ),
                    stage=stage_entity.name,
                    combat_log=format_response.combat_log,
                    narrative=format_response.narrative,
                ),
                exclude_entities={stage_entity},
            )

            # 遍历 final_hp，更新所有受影响角色（出牌者与目标）
            for entity_name, final_hp in format_response.final_hp.items():
                entity = self._game.get_entity_by_name(entity_name)
                if entity is None:
                    logger.warning(f"final_hp 中找不到实体: {entity_name}")
                    continue

                combat_stats = entity.get(CharacterStatsComponent)
                if combat_stats is None:
                    logger.warning(f"角色 {entity_name} 缺少 CombatStatsComponent")
                    continue

                old_hp = combat_stats.stats.hp
                max_hp = combat_stats.stats.max_hp
                combat_stats.stats.hp = int(max(0, min(final_hp, max_hp)))
                logger.info(
                    f"更新 {entity_name} HP: {old_hp} → {int(final_hp)}/{max_hp}"
                )

                self._game.add_human_message(
                    entity=entity,
                    message_content=_generate_hp_update_notification(
                        int(final_hp), max_hp
                    ),
                )

            latest_round = self._game.current_dungeon.latest_round
            assert latest_round is not None
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
            if combat_stats_comp.stats.hp <= 0:

                # logger.warning(f"{combat_stats_comp.name} is dead")
                self._game.add_human_message(entity, _generate_defeat_notification())
                entity.replace(DeathComponent, combat_stats_comp.name)

    #######################################################################################################################################
