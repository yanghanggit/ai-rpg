"""使用装备仲裁系统模块。

响应 UseGearItemAction 事件，调用 LLM 生成装备事件叙述并广播到场景。
装备的属性加成已由系统确定性应用，本系统仅负责叙事广播。
"""

from typing import Final, List, final
from loguru import logger
from overrides import override
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    UseGearItemAction,
    RoundStatsComponent,
    CharacterStats,
    CombatArbitrationEvent,
    AddStatusEffectsAction,
)


#######################################################################################################################################
def _fmt_stat_bonuses(stats: CharacterStats) -> str:
    return (
        f"HP {stats.hp:+d} | MAX_HP {stats.max_hp:+d} | ATK {stats.attack:+d} | "
        f"DEF {stats.defense:+d} | ENERGY {stats.energy:+d} | SPD {stats.speed:+d}"
    )


#######################################################################################################################################
def _generate_gear_equip_narrative_prompt(
    actor_name: str,
    action: UseGearItemAction,
    current_round_number: int,
) -> str:
    actor_short = actor_name.split(".")[-1]
    targets_str = "、".join(t.split(".")[-1] for t in action.targets) or actor_short
    item = action.item
    return (
        f"第 {current_round_number} 回合，{actor_short} 为 {targets_str} 装备了【{item.name}】。\n\n"
        f"装备描述：{item.description}\n"
        f"属性加成：{_fmt_stat_bonuses(item.stat_bonuses)}\n\n"
        f"请用 60-120 字、第三人称感官视角，描述装备更换的瞬间画面。"
    )


#######################################################################################################################################
def _build_gear_combat_log(actor_name: str, action: UseGearItemAction) -> str:
    actor_short = actor_name.split(".")[-1]
    targets_str = "→".join(t.split(".")[-1] for t in action.targets) or actor_short
    return f"[{actor_short}|装备{action.item.name}→{targets_str}]"


#######################################################################################################################################
def _generate_gear_equip_broadcast(
    actor_name: str,
    action: UseGearItemAction,
    current_round_number: int,
    narrative: str,
    combat_log: str,
) -> str:
    actor_short = actor_name.split(".")[-1]
    return (
        f"# 第 {current_round_number} 回合 · {actor_short} 装备 {action.item.name}\n\n"
        f"## 战斗演出\n\n{narrative}\n\n"
        f"## 数据日志\n\n{combat_log}"
    )


#######################################################################################################################################
def _generate_gear_task_hint(
    actor_name: str,
    action: UseGearItemAction,
    entity_name: str,
) -> str:
    item = action.item
    actor_short = actor_name.split(".")[-1]
    targets_str = "、".join(t.split(".")[-1] for t in action.targets) or "无"
    effects_line = (
        "- 延迟词缀：\n" + "\n".join(f"  - {a}" for a in item.affixes)
        if item.affixes
        else ""
    )
    item_info = (
        f"- 装备：{item.name}（{item.description}）\n"
        f"- 属性加成：{_fmt_stat_bonuses(item.stat_bonuses)}"
        + (f"\n{effects_line}" if effects_line else "")
    )
    if entity_name == actor_name:
        return (
            f"装备使用结算完成。你本回合使用了：\n{item_info}\n- 作用目标：{targets_str}\n"
            f"请根据以上使用结果，结合战斗上下文，评估是否追加状态效果。"
        )
    return (
        f"装备使用结算完成。你本回合被 {actor_short} 使用装备影响：\n{item_info}\n"
        f"请根据以上情况，结合战斗上下文，评估是否追加状态效果。"
    )


#######################################################################################################################################
@final
class UseGearItemArbitrationSystem(ReactiveProcessor):
    """响应 UseGearItemAction 事件，调用 LLM 生成装备叙述并广播到场景。"""

    def __init__(self, game: TCGGame, use_compressed_prompt: bool = True) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game
        self._use_compressed_prompt: Final[bool] = use_compressed_prompt

    #######################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(UseGearItemAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(UseGearItemAction) and entity.has(RoundStatsComponent)

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:

        if not self._game.current_dungeon.is_ongoing:
            logger.debug("UseGearItemArbitrationSystem: 战斗未进行中，跳过仲裁")
            return

        for entity in entities:
            stage_entity = self._game.resolve_stage_entity(entity)
            assert (
                stage_entity is not None
            ), f"UseGearItemArbitrationSystem: 无法获取 {entity.name} 所在场景实体！"

            logger.debug(f"UseGearItemArbitrationSystem: [{entity.name}] 广播装备事件")
            await self._broadcast_gear_equip(stage_entity, entity)

    #######################################################################################################################################
    async def _broadcast_gear_equip(
        self, stage_entity: Entity, actor_entity: Entity
    ) -> None:

        action = actor_entity.get(UseGearItemAction)
        current_round_number = len(self._game.current_dungeon.current_rounds or [])

        prompt = _generate_gear_equip_narrative_prompt(
            actor_name=actor_entity.name,
            action=action,
            current_round_number=current_round_number,
        )

        chat_client = DeepSeekClient(
            name=stage_entity.name,
            prompt=prompt,
            compressed_prompt=prompt if self._use_compressed_prompt else None,
            context=self._game.get_agent_context(stage_entity).context,
            timeout=60 * 2,
        )
        chat_client.chat()

        narrative = chat_client.response_content.strip()
        combat_log = _build_gear_combat_log(actor_entity.name, action)

        if self._use_compressed_prompt:
            self._game.add_human_message(
                entity=stage_entity,
                message_content=chat_client.compressed_prompt,
                combat_arbitration_full_prompt=chat_client.prompt,
            )
        else:
            self._game.add_human_message(
                entity=stage_entity,
                message_content=chat_client.prompt,
            )
        assert chat_client.response_ai_message is not None
        self._game.add_ai_message(
            entity=stage_entity,
            ai_message=chat_client.response_ai_message,
        )

        self._game.broadcast_to_stage(
            entity=stage_entity,
            agent_event=CombatArbitrationEvent(
                message=_generate_gear_equip_broadcast(
                    actor_name=actor_entity.name,
                    action=action,
                    current_round_number=current_round_number,
                    narrative=narrative,
                    combat_log=combat_log,
                ),
                stage=stage_entity.name,
                combat_log=combat_log,
                narrative=narrative,
            ),
            exclude_entities={stage_entity},
        )

        latest_round = self._game.current_dungeon.latest_round
        assert latest_round is not None, "latest_round 不应为 None"
        latest_round.combat_log.append(combat_log)
        latest_round.narrative.append(narrative)

        self._trigger_add_status_effects(
            actor_entity, action, list(dict.fromkeys(action.targets))
        )

    #######################################################################################################################################
    def _trigger_add_status_effects(
        self,
        actor_entity: Entity,
        action: UseGearItemAction,
        affected_entity_names: List[str],
    ) -> None:
        """装备仲裁结算后为使用者与所有目标添加 AddStatusEffectsAction。item.affixes 为空时跳过。"""
        if not action.item.affixes:
            logger.debug(
                f"[{actor_entity.name}] 装备 affixes 为空，跳过 AddStatusEffectsAction"
            )
            return

        for entity_name in affected_entity_names:
            entity = self._game.get_entity_by_name(entity_name)
            assert entity is not None, f"无法找到实体: {entity_name}"

            task_hint = _generate_gear_task_hint(
                actor_name=actor_entity.name,
                action=action,
                entity_name=entity_name,
            )
            entity.replace(AddStatusEffectsAction, entity_name, task_hint)
            logger.debug(f"[{entity_name}] 装备仲裁后添加 AddStatusEffectsAction")
