"""
战斗初始化系统
负责在战斗触发阶段为每个参战角色生成初始上下文提示词，包含场景叙事、其他角色外观、自身属性和状态效果。
执行后将战斗状态从 starting 转换为 ongoing，并启动第一回合。
"""

from dataclasses import dataclass
from typing import List, final, override, Set
from loguru import logger
from ..entitas import ExecuteProcessor, Entity
from ..game.tcg_game import TCGGame
from ..models import (
    EnvironmentComponent,
    CombatStatsComponent,
    AllyComponent,
    EnemyComponent,
    AppearanceComponent,
)
from langchain_core.messages import AIMessage


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

    return "\n".join(lines)


###################################################################################################################################################################
def _generate_combat_init_prompt(
    stage_name: str,
    stage_description: str,
    other_actors_info: List[OtherActorInfo],
    attrs_prompt: str,
    status_effects_prompt: str,
) -> str:
    """生成战斗开始时的提示词

    为角色生成战斗触发时的完整上下文信息，包含场景叙事、其他参战角色、
    自身属性和状态效果，帮助 AI 角色理解战斗环境并做出决策。

    Args:
        stage_name: 战斗场景名称
        stage_description: 战斗场景的环境描述
        other_actors_info: 其他参战角色的信息列表（包含名称、外观、阵营）
        attrs_prompt: 当前角色的属性提示词（HP、攻击、防御等）
        status_effects_prompt: 当前角色的状态效果提示词

    Returns:
        格式化的战斗开始提示词，包含所有必要的战斗上下文信息
    """
    return f"""# 通知！战斗触发！如下是当前场景的信息，请你基于这些信息，准备好战斗！
            
## 场景叙事

{stage_name} ｜ {stage_description}

## 其余角色

{_format_other_actors_info(other_actors_info)}

## 你的**属性**

{attrs_prompt}

## 你的**状态效果(status_effects)**

{status_effects_prompt}"""


###################################################################################################################################################################
@final
class CombatInitializationSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###################################################################################################################################################################
    @override
    async def execute(self) -> None:
        """执行战斗初始化流程。

        在战斗触发阶段(starting)为所有参战角色生成初始战斗提示词，包含场景信息、
        其他角色外观、自身属性和状态效果，然后将战斗状态转换为进行中(ongoing)并启动第一回合。

        流程：
        1. 检查战斗是否处于触发阶段，否则直接返回
        2. 获取玩家实体、当前场景实体和场景环境组件
        3. 获取所有参战的存活角色
        4. 为每个角色生成战斗开始提示词并追加到其对话上下文
        5. 转换战斗状态为进行中
        6. 启动第一回合
        """
        # 分析阶段
        if not self._game.current_combat_sequence.is_initializing:
            # 非战斗触发阶段，直接返回
            return

        assert (
            len(self._game.current_combat_sequence.current_rounds) == 0
        ), "战斗触发阶段不允许有回合数！"

        # 获取玩家实体, player在的场景就是战斗发生的场景！
        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        # 获取当前场景实体
        current_stage_entity = self._game.resolve_stage_entity(player_entity)
        assert current_stage_entity is not None

        # 获取场景环境组件
        environment_comp = current_stage_entity.get(EnvironmentComponent)
        assert environment_comp is not None

        # 参与战斗的角色实体列表
        actor_entities = self._game.get_alive_actors_on_stage(player_entity)
        assert len(actor_entities) > 0, "不可能出现没人参与战斗的情况！"
        for actor_entity in actor_entities:

            # 获取角色属性组件
            combat_stats_comp = actor_entity.get(CombatStatsComponent)
            assert combat_stats_comp is not None

            # 生成其他角色信息（包含外观和阵营）
            other_actors_info = _generate_other_actors_info(
                actor_entity, actor_entities
            )

            # 生成提示词
            combat_init_prompt = _generate_combat_init_prompt(
                stage_name=current_stage_entity.name,
                stage_description=environment_comp.description,
                other_actors_info=other_actors_info,
                attrs_prompt=combat_stats_comp.stats_prompt,
                status_effects_prompt=combat_stats_comp.status_effects_prompt,
            )

            # 追加提示词到角色对话中
            self._game.add_human_message(
                actor_entity,
                combat_init_prompt,
                combat_initialization=current_stage_entity.name,
            )

            # TODO, 追加 AI 准备好消息, 模拟角色回应，准备战斗, 其实在这里可以模拟塞入战斗风格与策略等内容，从而影响后续战斗决策。
            self._game.add_ai_message(
                entity=actor_entity,
                ai_messages=[AIMessage(content="我准备好了，等待战斗开始！")],
            )

        # 设置战斗为进行中
        self._game.current_combat_sequence.transition_to_ongoing()

        # 设置第一回合
        if not self._game.create_next_round():
            logger.error(f"not web_game.setup_round()")
            assert False, "无法启动战斗的第一回合！"


###################################################################################################################################################################
def _determine_camp_relationship(actor_entity: Entity, other_entity: Entity) -> str:
    """判断两个角色之间的阵营关系

    Args:
        actor_entity: 当前角色实体
        other_entity: 其他角色实体

    Returns:
        阵营关系字符串："友方" 或 "敌方"

    规则：
        - 同是 AllyComponent 或 同是 EnemyComponent 就是友方
        - 否则是敌方
    """
    actor_is_ally = actor_entity.has(AllyComponent)
    actor_is_enemy = actor_entity.has(EnemyComponent)
    other_is_ally = other_entity.has(AllyComponent)
    other_is_enemy = other_entity.has(EnemyComponent)

    # 同是友方或同是敌方
    if (actor_is_ally and other_is_ally) or (actor_is_enemy and other_is_enemy):
        return "友方"

    return "敌方"


###################################################################################################################################################################
def _generate_other_actors_info(
    actor_entity: Entity, actor_entities: Set[Entity]
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
            camp=_determine_camp_relationship(actor_entity, other_entity),
        )

        other_actors_info_list.append(other_actor_info)

    return other_actors_info_list


###################################################################################################################################################################
