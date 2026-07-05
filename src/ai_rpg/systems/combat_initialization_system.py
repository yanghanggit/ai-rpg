"""战斗初始化系统：战斗触发后、第一回合开始前，注入战场上下文并触发初始状态效果评估。"""

from dataclasses import dataclass
from typing import Final, List, final, override, Set
from ..models.messages import AIMessage, HumanMessage
from loguru import logger
from ..entitas import ExecuteProcessor, Entity
from ..game.dbg_game import DBGGame
from ..models import (
    GenerateDeckAction,
    StageDescriptionComponent,
    PartyMemberComponent,
    MonsterComponent,
    AppearanceComponent,
    StatusEffectsComponent,
    DrawPileComponent,
    DiscardPileComponent,
    ExhaustPileComponent,
)
from ..models import CharacterStats


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
def _generate_init_status_effects_task_hint() -> List[str]:
    """生成战斗初始化阶段的 AddStatusEffectsAction task_hints 提示词列表"""
    return [
        "当前处于战斗初始化阶段，请根据战场环境、角色身份与当前处境，生成一个适用于抽牌或回合末阶段（draw / round_end）的初始状态效果。",
        "当前处于战斗初始化阶段，请根据战场环境、角色身份与当前处境，生成一个适用于出牌结算阶段（arbitration）的初始状态效果，优先考虑条件触发或反伤类效果。",
    ]


###################################################################################################################################################################
@final
class CombatInitializationSystem(ExecuteProcessor):
    """战斗初始化系统"""

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ###################################################################################################################################################################
    @override
    async def execute(self) -> None:

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

        # 为所有参战角色初始化战斗临时牌堆（DrawPile / DiscardPile / ExhaustPile）
        self._initialize_actor_piles(actor_entities)

        # 为每个角色注入战场上下文（无 LLM 调用）
        self._add_context_for_all_actors(
            actor_entities=actor_entities,
            stage_name=current_stage_entity.name,
            stage_description=stage_description_comp.narrative,
        )

        # 设置战斗为进行中（第一回合将由 CombatRoundTransitionSystem 创建）
        self._game.current_dungeon.transition_to_ongoing()
        assert (
            self._game.current_dungeon.is_ongoing
        ), "战斗状态转换失败，当前状态非 ONGOING！"

        # 为所有参战角色添加 GenerateDeckAction，触发初始牌库生成
        self._trigger_actor_deck_generation(actor_entities)

        # 为所有参战角色添加 AddStatusEffectsAction，触发初始状态效果生成
        self._initialize_actor_status_effects(actor_entities)

        # 第一回合由 CombatRoundTransitionSystem 在本 pipeline tick 末创建（同帧创建）

    ###################################################################################################################################################################
    def _initialize_actor_piles(self, actor_entities: Set[Entity]) -> None:
        """为所有参战角色初始化战斗临时牌堆：DrawPile / DiscardPile / ExhaustPile。"""
        for actor_entity in actor_entities:
            assert not actor_entity.has(
                DrawPileComponent
            ), f"角色 {actor_entity.name} 已存在 DrawPileComponent，战斗初始化不应重复挂载！"
            actor_entity.replace(DrawPileComponent, actor_entity.name, [])
            actor_entity.replace(DiscardPileComponent, actor_entity.name, [])
            actor_entity.replace(ExhaustPileComponent, actor_entity.name, [])
            logger.debug(
                f"[{actor_entity.name}] 战斗临时牌堆初始化完成（DrawPile / DiscardPile / ExhaustPile）"
            )

    ###################################################################################################################################################################
    def _trigger_actor_deck_generation(self, actor_entities: Set[Entity]) -> None:
        """为所有参战角色挂载 GenerateDeckAction，触发 DeckGenerationSystem 生成初始牌库。"""
        for actor_entity in actor_entities:
            if actor_entity.has(PartyMemberComponent):
                cards_per_combat = 3
            else:
                # MonsterComponent 与 PartyMemberComponent 全局互斥，此处默认怪物
                assert actor_entity.has(
                    MonsterComponent
                ), f"角色 {actor_entity.name} 既无 PartyMemberComponent 也无 MonsterComponent！"
                cards_per_combat = 1
            actor_entity.replace(
                GenerateDeckAction, actor_entity.name, cards_per_combat
            )
            logger.debug(
                f"[{actor_entity.name}] 已添加 GenerateDeckAction（cards_per_combat={cards_per_combat}）"
            )

    ###################################################################################################################################################################
    def _initialize_actor_status_effects(self, actor_entities: Set[Entity]) -> None:
        """为所有参战角色初始化状态效果：注入空 StatusEffectsComponent 并挂载 AddStatusEffectsAction。"""
        for actor_entity in actor_entities:

            # 如果没有状态效果组件则先添加一个空的，以保证 AddStatusEffectsActionSystem 能正常工作
            assert (
                not actor_entity.has(StatusEffectsComponent)
                or len(actor_entity.get(StatusEffectsComponent).status_effects) == 0
            ), f"角色 {actor_entity.name} 已有非空状态效果列表，理论上不应该出现这种情况！如果确实出现了，请检查之前的系统是否正确清理了状态效果。"
            actor_entity.replace(
                StatusEffectsComponent,
                actor_entity.name,
                [],
            )

            logger.debug(
                f"为角色 {actor_entity.name} 添加 AddStatusEffectsAction 以触发初始状态效果评估"
            )

            # 添加 AddStatusEffectsAction，触发 AddStatusEffectsActionSystem 评估初始状态效果
            self._game.accumulate_status_effects_action(
                actor_entity,
                _generate_init_status_effects_task_hint(),
            )

    ###################################################################################################################################################################
    def _add_context_for_all_actors(
        self,
        actor_entities: Set[Entity],
        stage_name: str,
        stage_description: str,
    ) -> None:
        """为所有参战角色注入战场上下文（human message + 模拟 AI 回应），无 LLM 调用。"""
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
                human_message=HumanMessage(
                    content=combat_init_prompt,
                    combat_initialization=stage_name,
                ),
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
        """返回两角色间的阵营关系：'友方' 或 '敌方'。"""
        actor_is_ally = actor_entity.has(PartyMemberComponent)
        actor_is_enemy = actor_entity.has(MonsterComponent)
        other_is_ally = other_entity.has(PartyMemberComponent)
        other_is_enemy = other_entity.has(MonsterComponent)

        # 同是友方或同是敌方
        if (actor_is_ally and other_is_ally) or (actor_is_enemy and other_is_enemy):
            return "友方"

        return "敌方"

    ###################################################################################################################################################################
    def _generate_other_actors_info(
        self, actor_entity: Entity, actor_entities: Set[Entity]
    ) -> List[OtherActorInfo]:
        """生成除自身外所有参战角色的信息列表（名称、外观、阵营）。"""
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
