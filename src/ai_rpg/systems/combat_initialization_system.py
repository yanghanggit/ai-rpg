"""战斗初始化系统：战斗触发后、第一回合开始前，注入战场上下文并触发初始状态效果评估。"""

from dataclasses import dataclass
from typing import Final, List, Optional, final, override, Set
from pydantic import BaseModel
from ..models.messages import AIMessage, HumanMessage
from loguru import logger
from ..deepseek import DeepSeekClient
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
    PostArbitrationAction,
    StageDescriptionComponent,
    StatusEffectsComponent,
    DrawPileComponent,
    DiscardPileComponent,
    ExhaustPileComponent,
    CharacterStats,
    AppearanceComponent,
)
from ..utils import extract_json_from_code_block


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
class CombatInitInteractionResponse(BaseModel):
    """战斗初始化阶段场景干预判定响应"""

    interaction_summary: str = (
        ""  # 非空时触发 PostArbitrationAction，作为该系统推理的依据文本；无干预依据则为空字符串
    )


###################################################################################################################################################################
def _generate_combat_init_interaction_prompt(
    stage_name: str,
    stage_description: str,
    actor_entities: Set[Entity],
) -> str:
    """生成战斗初始化阶段场景干预判定提示词"""

    actor_lines = "\n".join(f"- {actor.name}" for actor in actor_entities)

    return f"""# 战斗初始化 — 场景干预判定

## 场景叙事

{stage_name} ｜ {stage_description}

## 参战角色

{actor_lines}

## 任务

请判断以上战斗开始时的场景叙事中，是否存在**已明确描述、可转化为具体物理干预**的场景要素（如遍布的浓烟、松动的碎石、可借力的断柱、灼热的地面等），且该要素**合理推断可在战斗开始时就对参战角色产生状态效果或提供可拾取卡牌**。

判断规则：

- 仅当叙事中**明确描述**了此类场景要素时，才用一句话（20-40 字）概括**具体是哪个场景要素、可能产生何种影响**；
- 若叙事平淡、无明显可利用的环境要素，**必须输出空字符串 `""`**，不得凭空引入场景中未出现的要素；
- 禁止：勇气、恐惧、神圣、复仇、祝福、诅咒等角色内在情绪或来源不明的魔法效果。

## 输出格式

```json
{{
  "interaction_summary": ""
}}
```

只输出 JSON。"""


###################################################################################################################################################################
def _generate_compressed_combat_init_interaction_prompt(
    stage_name: str,
    stage_description: str,
    actor_entities: Set[Entity],
) -> str:
    """生成压缩版战斗初始化阶段场景干预判定提示词（仅动态感知部分，省略静态规则/格式说明）"""

    actor_lines = "\n".join(f"- {actor.name}" for actor in actor_entities)

    return f"""# 战斗初始化 — 场景干预判定

## 场景叙事

{stage_name} ｜ {stage_description}

## 参战角色

{actor_lines}"""


###################################################################################################################################################################
@final
class CombatInitializationSystem(ExecuteProcessor):
    """战斗初始化系统"""

    def __init__(self, game: DBGGame, use_compressed_prompt: bool = True) -> None:
        self._game: Final[DBGGame] = game
        self._use_compressed_prompt: Final[bool] = use_compressed_prompt

    ###################################################################################################################################################################
    @override
    async def execute(self) -> None:

        if not self._game.current_combat_room.combat.is_initializing:
            logger.debug("当前战斗状态非 initializing，跳过战斗初始化")
            return

        logger.info("战斗初始化开始，正在为参战角色注入战场上下文并转换战斗状态...")

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

        # 设置战斗为进行中（第一回合将由 CombatRoundTransitionSystem 创建）
        self._game.current_combat_room.combat.transition_to_ongoing()
        assert (
            self._game.current_combat_room.combat.is_ongoing
        ), "战斗状态转换失败，当前状态非 ONGOING！"

        # 为所有参战角色添加 GenerateDeckAction，触发初始牌库生成
        self._trigger_deck_generation(actor_entities)

        # 让 stage agent 推理一次，判定战斗开始时是否存在场景干预依据；
        # 若有，则挂载 PostArbitrationAction，交由 PostArbitrationActionSystem 生成具体的状态效果/塞牌
        await self._evaluate_stage_post_arbitration(
            stage_entity=current_stage_entity,
            actor_entities=actor_entities,
            stage_name=current_stage_entity.name,
            stage_description=stage_description_comp.narrative,
        )

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
    async def _evaluate_stage_post_arbitration(
        self,
        stage_entity: Entity,
        actor_entities: Set[Entity],
        stage_name: str,
        stage_description: str,
    ) -> None:
        """让 stage agent 推理一次，判定战斗开始时是否存在可转化为状态效果/塞牌的场景干预依据；
        若有，则挂载 PostArbitrationAction，交由 PostArbitrationActionSystem 在本轮内完成具体干预。"""

        prompt = _generate_combat_init_interaction_prompt(
            stage_name=stage_name,
            stage_description=stage_description,
            actor_entities=actor_entities,
        )

        compressed_message: Optional[str] = None
        if self._use_compressed_prompt:
            compressed_message = _generate_compressed_combat_init_interaction_prompt(
                stage_name=stage_name,
                stage_description=stage_description,
                actor_entities=actor_entities,
            )

        chat_client = DeepSeekClient(
            name=stage_entity.name,
            prompt=prompt,
            compressed_prompt=compressed_message,
            context=self._game.get_agent_context(stage_entity).context,
        )

        logger.debug(f"[{stage_entity.name}] 战斗初始化场景干预判定开始")

        # 发起 LLM 请求，捕获异常以防止整个战斗初始化流程崩溃
        try:
            await chat_client.chat()
        except Exception as e:
            logger.error(
                f"[{stage_entity.name}] 战斗初始化场景干预判定 LLM 请求失败: {e}"
            )
            return

        if chat_client.response_ai_message is None:
            logger.warning(
                f"[{stage_entity.name}] 战斗初始化场景干预判定 LLM 响应为空，跳过"
            )
            return

        try:
            response = CombatInitInteractionResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )
        except Exception as e:
            logger.error(
                f"[{stage_entity.name}] 解析战斗初始化场景干预判定响应失败: {e}"
            )
            logger.error(f"原始响应: {chat_client.response_content}")
            return

        # 将本轮判定写入 stage entity 的对话历史，便于后续回顾与调试
        if self._use_compressed_prompt:
            self._game.add_human_message(
                entity=stage_entity,
                human_message=HumanMessage(
                    content=chat_client.compressed_prompt,
                    combat_init_post_arbitration_full_prompt=chat_client.prompt,
                ),
            )
        else:
            self._game.add_human_message(
                entity=stage_entity,
                human_message=HumanMessage(content=chat_client.prompt),
            )

        # 将 LLM 回复写入 stage entity 的对话历史，便于后续回顾与调试
        self._game.add_ai_message(
            entity=stage_entity,
            ai_message=chat_client.response_ai_message,
        )

        # 若 LLM 判定存在场景干预依据，则挂载 PostArbitrationAction，交由 PostArbitrationActionSystem 在本轮内完成具体干预
        if response.interaction_summary:
            logger.debug(
                f"[{stage_entity.name}] 战斗初始化判定存在场景干预依据，触发 PostArbitrationAction: {response.interaction_summary}"
            )
            stage_entity.replace(
                PostArbitrationAction,
                stage_entity.name,
                response.interaction_summary,
            )
        else:
            logger.debug(f"[{stage_entity.name}] 战斗初始化判定无场景干预依据")

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
