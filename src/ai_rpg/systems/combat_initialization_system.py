"""战斗初始化系统

在战斗触发阶段为参战角色注入战场上下文，转换战斗状态为进行中。
不进行 LLM 推理，仅通过 add_human_message 注入战斗上下文，
并以模拟 AI 回应保证 agent 对话连续性。
初始化末尾为所有参战角色添加 AddStatusEffectsAction，触发第一回合初始状态效果评估。
"""

from dataclasses import dataclass
from typing import Final, List, final, override, Set
from ..models.messages import AIMessage
from loguru import logger
from ..entitas import ExecuteProcessor, Entity
from ..game.tcg_game import TCGGame
from ..models import (
    AddStatusEffectsAction,
    StageDescriptionComponent,
    ExpeditionMemberComponent,
    EnemyComponent,
    AppearanceComponent,
    StatusEffectsComponent,
)
from ..models.entities import CharacterStats


###################################################################################################################################################################
@dataclass
class OtherActorInfo:
    """其他参战角色的信息"""

    actor_name: str  # 当前角色名称
    other_name: str  # 其他角色名称
    appearance: str  # 其他角色的外观描述
    camp: str  # 阵营关系（友方/敌方）


###################################################################################################################################################################
def _format_other_actors_info(other_actors_info: List[OtherActorInfo]) -> str:
    """格式化其他角色信息为 Markdown 列表

    Args:
        other_actors_info: 其他角色信息列表

    Returns:
        格式化后的 Markdown 字符串
    """
    if not other_actors_info:
        return "无"

    lines = []
    for info in other_actors_info:
        lines.append(f"- **{info.other_name}**（{info.camp}）: {info.appearance}")

    return "\n\n".join(lines)


###################################################################################################################################################################
def _generate_combat_init_prompt(
    stage_name: str,
    stage_description: str,
    other_actors_info: List[OtherActorInfo],
    actor_stats: CharacterStats,
) -> str:
    """生成战斗初始化上下文通知

    为角色生成战斗触发时的战场情境通知，同步场景、敌我、自身属性信息。
    不要求任何输出，仅作为上下文注入使用。

    Args:
        stage_name: 战斗场景名称
        stage_description: 战斗场景的环境描述
        other_actors_info: 其他参战角色的信息列表（包含名称、外观、阵营）
        actor_stats: 当前角色的属性数据（包含 hp/max_hp/attack/defense）

    Returns:
        战场情境通知文本
    """
    attrs_prompt = f"HP:{actor_stats.hp}/{actor_stats.max_hp} | 攻击:{actor_stats.attack} | 防御:{actor_stats.defense}"

    return f"""# 战斗触发通知

## 场景叙事

{stage_name} ｜ {stage_description}

## 其余角色

{_format_other_actors_info(other_actors_info)}

## 你的属性

{attrs_prompt}"""


###################################################################################################################################################################
def _generate_init_status_effects_task_hint() -> str:
    """生成战斗初始化阶段的 AddStatusEffectsAction task_hint 提示词"""
    return (
        "当前处于战斗初始化阶段，请根据战场环境、角色身份与当前处境，生成符合初始战场状态的状态效果。"
        "若追加数量上限大于1，draw 与 arbitration 相位各至少选一个；若上限为1，优先选 arbitration 相位。"
    )


###################################################################################################################################################################
@final
class CombatInitializationSystem(ExecuteProcessor):
    """战斗初始化系统

    在战斗触发阶段为参战角色注入战场上下文，转换战斗状态为进行中。
    不进行 LLM 推理，仅 add_human_message + 模拟 AI 回应以维护 agent 对话连续性。
    初始化末尾为所有参战角色添加 AddStatusEffectsAction，
    触发 AddStatusEffectsActionSystem 完成第一回合初始状态效果评估。

    执行时机：
        战斗序列状态为 initializing 时执行，在战斗触发后、第一回合开始前。
    """

    def __init__(self, game: TCGGame) -> None:
        self._game: Final[TCGGame] = game

    ###################################################################################################################################################################
    @override
    async def execute(self) -> None:
        """执行战斗初始化

        为参战角色注入战场上下文（human message + 模拟 AI 回应），
        转换战斗状态为进行中，并为所有参战角色添加 AddStatusEffectsAction
        以触发第一回合初始状态效果评估。不进行 LLM 推理。
        """
        if not self._game.current_dungeon.is_initializing:
            logger.debug("当前战斗状态非 initializing，跳过战斗初始化")
            return

        logger.info("战斗初始化开始，正在为参战角色注入战场上下文并转换战斗状态...")

        assert self._game.is_player_in_dungeon_stage, "战斗初始化阶段玩家必须在场景中！"
        assert (
            len(self._game.current_dungeon.current_rounds or []) == 0
        ), "战斗触发阶段不允许有回合数！"

        # 获取玩家实体，player 所在场景即战斗场景
        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "无法找到玩家实体！"

        # 获取当前场景实体
        current_stage_entity = self._game.resolve_stage_entity(player_entity)
        assert current_stage_entity is not None, "无法找到当前场景实体！"
        assert current_stage_entity.has(
            StageDescriptionComponent
        ), "当前场景实体缺少 StageDescriptionComponent 组件！"

        # 获取场景环境组件
        stage_description_comp = current_stage_entity.get(StageDescriptionComponent)

        # 参与战斗的角色实体列表
        actor_entities = self._game.get_alive_actors_in_stage(player_entity)
        assert len(actor_entities) > 0, "不可能出现没人参与战斗的情况！"

        # 为每个角色注入战场上下文（无 LLM 调用）
        self._add_context_for_all_actors(
            actor_entities=actor_entities,
            stage_name=current_stage_entity.name,
            stage_description=stage_description_comp.narrative,
        )

        # 设置战斗为进行中（第一回合将由 CombatRoundTransitionSystem 创建）
        self._game.current_dungeon.transition_to_ongoing()

        # 为所有参战角色添加 AddStatusEffectsAction，触发初始状态效果生成
        self._add_status_effects_actions_for_all_actors(actor_entities)

    ###################################################################################################################################################################
    def _add_status_effects_actions_for_all_actors(
        self, actor_entities: Set[Entity]
    ) -> None:
        """为所有参战角色添加 AddStatusEffectsAction，触发初始状态效果评估。

        若角色缺少 StatusEffectsComponent，先注入空组件以保证系统正常运行。

        Args:
            actor_entities: 所有参战角色实体集合
        """
        for actor_entity in actor_entities:

            # 如果没有状态效果组件则先添加一个空的，以保证 AddStatusEffectsActionSystem 能正常工作
            if not actor_entity.has(StatusEffectsComponent):
                actor_entity.replace(
                    StatusEffectsComponent,
                    actor_entity.name,
                    [],
                )

            logger.debug(
                f"为角色 {actor_entity.name} 添加 AddStatusEffectsAction 以触发初始状态效果评估"
            )

            # 添加 AddStatusEffectsAction，触发 AddStatusEffectsActionSystem 评估初始状态效果
            actor_entity.replace(
                AddStatusEffectsAction,
                actor_entity.name,
                _generate_init_status_effects_task_hint(),
            )

    ###################################################################################################################################################################
    def _add_context_for_all_actors(
        self,
        actor_entities: Set[Entity],
        stage_name: str,
        stage_description: str,
    ) -> None:
        """为所有参战角色注入战场上下文

        为每个角色生成战斗初始化提示词并添加到对话上下文（human message），
        随后注入一条模拟 AI 回应以维护 Human↔AI 交替的 agent 对话结构。
        不进行任何 LLM 调用。

        Args:
            actor_entities: 所有参战角色实体集合
            stage_name: 战斗场景名称
            stage_description: 战斗场景的环境描述
        """
        for actor_entity in actor_entities:

            # 计算角色有效属性（含装备加成）
            actor_stats = self._game.compute_character_stats(actor_entity)

            # 生成其他角色信息（包含外观和阵营）
            other_actors_info = self._generate_other_actors_info(
                actor_entity, actor_entities
            )

            # 生成战场上下文提示词
            combat_init_prompt = _generate_combat_init_prompt(
                stage_name=stage_name,
                stage_description=stage_description,
                other_actors_info=other_actors_info,
                actor_stats=actor_stats,
            )

            # 注入战场上下文
            self._game.add_human_message(
                entity=actor_entity,
                message_content=combat_init_prompt,
                combat_initialization=stage_name,
            )

            # 注入模拟 AI 回应，维护 Human↔AI 交替结构
            self._game.add_ai_message(
                entity=actor_entity,
                ai_message=AIMessage(content="已感知战场环境，进入战斗准备状态。"),
            )

            logger.debug(f"[{actor_entity.name}] 战斗上下文注入完成（无 LLM 推理）")

    ###################################################################################################################################################################
    def _determine_camp_relationship(
        self, actor_entity: Entity, other_entity: Entity
    ) -> str:
        """判断两个角色之间的阵营关系

        Args:
            actor_entity: 当前角色实体
            other_entity: 其他角色实体

        Returns:
            阵营关系字符串："友方" 或 "敌方"
        """
        actor_is_ally = actor_entity.has(ExpeditionMemberComponent)
        actor_is_enemy = actor_entity.has(EnemyComponent)
        other_is_ally = other_entity.has(ExpeditionMemberComponent)
        other_is_enemy = other_entity.has(EnemyComponent)

        # 同是友方或同是敌方
        if (actor_is_ally and other_is_ally) or (actor_is_enemy and other_is_enemy):
            return "友方"

        return "敌方"

    ###################################################################################################################################################################
    def _generate_other_actors_info(
        self, actor_entity: Entity, actor_entities: Set[Entity]
    ) -> List[OtherActorInfo]:
        """为指定角色生成其他所有参战角色的信息列表

        Args:
            actor_entity: 当前角色实体
            actor_entities: 所有参战角色实体集合

        Returns:
            其他角色的信息列表，包含名称、外观和阵营关系
        """
        # copy生成其他参战角色的列表，但是移除自己
        copy_entities = actor_entities.copy()
        copy_entities.remove(actor_entity)

        # 生成返回数据列表！
        other_actors_info_list: List[OtherActorInfo] = []

        # 生成数据列表
        for other_entity in copy_entities:

            appearance_comp = other_entity.get(AppearanceComponent)
            assert appearance_comp is not None, "每个参战角色都必须有外观组件！"

            other_actor_info = OtherActorInfo(
                actor_name=actor_entity.name,
                other_name=other_entity.name,
                appearance=appearance_comp.appearance,
                camp=self._determine_camp_relationship(actor_entity, other_entity),
            )

            other_actors_info_list.append(other_actor_info)

        return other_actors_info_list


###################################################################################################################################################################
