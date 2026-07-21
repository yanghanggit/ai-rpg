"""战斗初始化系统（角色侧）：战斗触发后，为参战角色初始化临时牌堆/状态效果组件、注入战场上下文并触发初始牌库生成。"""

from dataclasses import dataclass
from typing import Final, List, final, override, Set
from ..models.messages import AIMessage, HumanMessage
from loguru import logger
from ..entitas import ExecuteProcessor, Entity
from ..game.dbg_game import DBGGame
from ..game.dbg_combat_processor import (
    get_alive_actors_in_stage,
    determine_camp_relationship,
    get_cards_per_combat,
)
from ..game.dbg_combat_processor import (
    compute_character_stats,
)
from ..models import (
    GenerateDeckAction,
    StageDescriptionComponent,
    StatusEffectsComponent,
    DrawPileComponent,
    DiscardPileComponent,
    ExhaustPileComponent,
    CharacterStats,
    AppearanceComponent,
)


###################################################################################################################################################################
@dataclass
class OtherActorInfo:
    """其他参战角色的信息"""

    other_name: str  # 其他角色名称
    appearance: str  # 其他角色的外观描述
    camp: str  # 阵营关系（友方/敌方）


###################################################################################################################################################################
def _format_other_actors_info(other_actors_info: List[OtherActorInfo]) -> str:
    """格式化其他角色信息为 Markdown 列表"""
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
    """生成战斗初始化上下文通知"""
    attrs_prompt = f"HP:{actor_stats.hp}/{actor_stats.max_hp} | 攻击:{actor_stats.attack} | 防御:{actor_stats.defense}"

    return f"""# 战斗触发通知

## 场景叙事

{stage_name} ｜ {stage_description}

## 其余角色

{_format_other_actors_info(other_actors_info)}

## 你的属性

{attrs_prompt}"""


###################################################################################################################################################################
@final
class CombatInitActorSystem(ExecuteProcessor):
    """战斗初始化系统（角色侧）：初始化战斗临时牌堆/状态效果组件，为参战角色注入战场上下文，触发初始牌库生成。"""

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ###################################################################################################################################################################
    @override
    async def execute(self) -> None:

        if not self._game.current_combat_room.combat.is_initializing:
            logger.debug("当前战斗状态非 initializing，跳过战斗初始化（角色侧）")
            return

        logger.info(
            "战斗初始化（角色侧）开始，正在为参战角色初始化牌堆/状态效果并注入战场上下文..."
        )

        assert self._game.is_player_in_dungeon_stage, "战斗初始化阶段玩家必须在场景中！"
        assert (
            len(self._game.current_combat_room.combat.rounds or []) == 0
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
        actor_entities = get_alive_actors_in_stage(self._game, player_entity)
        assert len(actor_entities) > 0, "不可能出现没人参与战斗的情况！"

        # 为所有参战角色初始化战斗临时牌堆（DrawPile / DiscardPile / ExhaustPile）与空的状态效果组件
        self._initialize_piles_and_status_effects(actor_entities)

        # 为每个角色注入战场上下文（无 LLM 调用）
        self._add_context(
            actor_entities=actor_entities,
            stage_name=current_stage_entity.name,
            stage_description=stage_description_comp.narrative,
        )

        # 为所有参战角色添加 GenerateDeckAction，触发初始牌库生成
        self._trigger_deck_generation(actor_entities)

    ###################################################################################################################################################################
    def _initialize_piles_and_status_effects(self, actor_entities: Set[Entity]) -> None:
        """为所有参战角色初始化战斗临时牌堆（DrawPile / DiscardPile / ExhaustPile）与空的 StatusEffectsComponent。"""
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

            # 如果没有状态效果组件则先添加一个空的，以保证后续系统（AddStatusEffectsActionSystem / PostArbitrationActionSystem）能正常工作
            assert (
                not actor_entity.has(StatusEffectsComponent)
                or len(actor_entity.get(StatusEffectsComponent).status_effects) == 0
            ), f"角色 {actor_entity.name} 已有非空状态效果列表，理论上不应该出现这种情况！如果确实出现了，请检查之前的系统是否正确清理了状态效果。"
            actor_entity.replace(
                StatusEffectsComponent,
                actor_entity.name,
                [],
            )
            logger.debug(f"[{actor_entity.name}] 状态效果组件初始化完成（空）")

    ###################################################################################################################################################################
    def _trigger_deck_generation(self, actor_entities: Set[Entity]) -> None:
        """为所有参战角色挂载 GenerateDeckAction，触发 DeckGenerationSystem 生成初始牌库。"""
        for actor_entity in actor_entities:
            cards_per_combat = get_cards_per_combat(actor_entity)
            actor_entity.replace(
                GenerateDeckAction, actor_entity.name, cards_per_combat
            )
            logger.debug(
                f"[{actor_entity.name}] 已添加 GenerateDeckAction（cards_per_combat={cards_per_combat}）"
            )

    ###################################################################################################################################################################
    def _add_context(
        self,
        actor_entities: Set[Entity],
        stage_name: str,
        stage_description: str,
    ) -> None:
        """为所有参战角色注入战场上下文（human message + 模拟 AI 回应），无 LLM 调用。"""

        for actor_entity in actor_entities:

            # 生成其他角色信息（包含外观和阵营）
            copy_entities = actor_entities.copy()
            copy_entities.remove(actor_entity)

            # 生成其他角色信息列表
            other_actors_info: List[OtherActorInfo] = []
            for other_entity in copy_entities:

                appearance_comp = other_entity.get(AppearanceComponent)
                assert appearance_comp is not None, "每个参战角色都必须有外观组件！"

                # 生成其他角色信息
                other_actors_info.append(
                    OtherActorInfo(
                        other_name=other_entity.name,
                        appearance=appearance_comp.appearance,
                        camp=determine_camp_relationship(actor_entity, other_entity),
                    )
                )

            # 计算角色有效属性（含装备加成）
            actor_stats = compute_character_stats(actor_entity)

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
