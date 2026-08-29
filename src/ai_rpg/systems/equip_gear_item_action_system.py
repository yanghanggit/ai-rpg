"""装备转化系统模块：将 GearItem 转化为一张 Card 放入当前行动者手牌。"""

from typing import Dict, Final, List, Optional, final

from loguru import logger
from overrides import override
from pydantic import BaseModel

from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_combat_processor import compute_character_stats
from ..game.dbg_game import DBGGame
from ..models import (
    AgentEvent,
    Card,
    CharacterStats,
    EquipGearItemAction,
    GearItem,
    HandComponent,
    HumanMessage,
    InventoryComponent,
    PartyMemberComponent,
    TargetType,
)
from ..utils import extract_json, prompt_builder
from .card_prompt_builders import BUILD_CARD_FIELD_DESCRIPTION


#######################################################################################################################################
@final
class _GearCardResponse(BaseModel):
    """GearItem => Card 的 LLM 响应数据模型（单张卡牌）。"""

    name: str = ""  # 默认留空，沿用 GearItem.name；未来强化场景可改写
    description: str = ""  # 默认留空，沿用 GearItem.description；未来强化场景可改写
    on_play_affixes: List[str] = []
    on_hit_affixes: List[str] = []
    on_turn_end_affixes: List[str] = []
    playable: bool = True
    exhaust: bool = False
    retain: bool = False
    ethereal: bool = False
    cost: int = 1
    damage: int = 0
    hit_count: int = 1
    block: int = 0
    self_target: bool = False
    target_type: str = TargetType.SINGLE


#######################################################################################################################################
@prompt_builder
def _build_keyword_guide(keywords: List[str]) -> str:
    """取 GearItem.keywords[0] 作为完整的功能边界描述（数组为扩展预留）。"""
    return keywords[0] if keywords else "无"


#######################################################################################################################################
@prompt_builder
def _build_gear_card_prompt(gear: GearItem, actor_stats: CharacterStats) -> str:
    """生成 GearItem => Card 的完整提示词。"""
    keyword_guide = _build_keyword_guide(gear.keywords)

    return f"""# 装备转化为手牌：生成 1 张卡牌

## 装备

- 名称：{gear.name}
- 描述：{gear.description}

## 功能边界（keywords）

{keyword_guide}

## 你的当前属性

HP {actor_stats.hp}/{actor_stats.max_hp} | 攻击 {actor_stats.attack} | 防御 {actor_stats.defense}

## 设计约束

- name 与 description 默认与装备保持一致：请留空或原样输出装备的 name/description，不要另行创作（仅未来强化改造场景才可改写）
- keywords 即边界：要求的效果在对应字段体现；未提及即禁止
- 只输出 JSON，不附加任何说明文字

{BUILD_CARD_FIELD_DESCRIPTION}

```json
{{
  "name": "",
  "description": "",
  "on_play_affixes": [],
  "on_hit_affixes": [],
  "on_turn_end_affixes": [],
  "playable": true,
  "exhaust": false,
  "retain": false,
  "ethereal": false,
  "cost": 1,
  "damage": 0,
  "hit_count": 1,
  "block": 0,
  "self_target": false,
  "target_type": "single"
}}
```"""


#######################################################################################################################################
@prompt_builder
def _build_condensed_gear_card_prompt(
    gear: GearItem, actor_stats: CharacterStats
) -> str:
    """生成 GearItem => Card 的精简版提示词（写入对话历史）。"""
    keyword_guide = _build_keyword_guide(gear.keywords)

    return f"""# 装备转化为手牌

装备：{gear.name}（{gear.description}）

功能边界（keywords）：
{keyword_guide}

你的属性：HP {actor_stats.hp}/{actor_stats.max_hp} | 攻击 {actor_stats.attack} | 防御 {actor_stats.defense}"""


#######################################################################################################################################
@prompt_builder
def _build_gear_notice(
    actor_name: str,
    item_name: str,
    card_name: str,
    round_number: int,
) -> str:
    """生成装备转化广播通知。"""
    return (
        f"【第 {round_number} 回合 · 装备行动】\n"
        f"「{actor_name}」将「{item_name}」转化为手牌「{card_name}」。"
    )


#######################################################################################################################################
@final
class EquipGearItemActionSystem(ReactiveProcessor):
    """装备转化系统：把团队背包内的 GearItem 转化为 Card 放入当前行动者手牌。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(EquipGearItemAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(EquipGearItemAction) and entity.has(HandComponent)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("EquipGearItemActionSystem: 战斗未进行中，跳过")
            return

        assert (
            len(entities) == 1
        ), f"EquipGearItemActionSystem: 同一时间不应有多个实体触发 EquipGearItemAction，当前数量: {len(entities)}"

        entity = entities[0]
        action = entity.get(EquipGearItemAction)
        item = action.item
        assert isinstance(
            item, GearItem
        ), f"EquipGearItemActionSystem: action.item 应为 GearItem，但实际类型为 {type(item)}"

        assert entity.has(HandComponent), f"{entity.name} 缺少 HandComponent"
        assert entity.has(PartyMemberComponent), f"{entity.name} 不是友方角色"

        # 用发起穿装备的 Actor 上下文做推理，将 GearItem 转化为一张 Card
        card = await self._generate_card(entity, item)
        if card is None:
            logger.error(f"[EquipGearItemActionSystem] {entity.name} 转化装备失败")
            return

        # 团队背包：装备统一由 player 持有，从 player 背包移除（移动语义）
        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "玩家实体不存在！"
        assert player_entity.has(InventoryComponent), "玩家实体缺少 InventoryComponent"
        inventory = player_entity.get(InventoryComponent)
        inventory.items[:] = [
            inventory_item
            for inventory_item in inventory.items
            if inventory_item is not item
        ]

        # 将生成的卡牌放入当前行动者手牌
        hand_comp = entity.get(HandComponent)
        hand_comp.cards.append(card)
        logger.debug(
            f"EquipGearItemActionSystem: [{entity.name}] 将 '{item.name}' 转化为手牌 '{card.name}'"
        )

        # 记录本回合装备使用结果（供 TUI 展示）
        latest_round = self._game.current_dungeon_combat_room.combat.latest_round
        if latest_round is not None:
            latest_round.gear_combat_log.append(
                f"[{entity.name} 装备 {item.name}] 生成手牌「{card.name}」"
            )
            latest_round.gear_narrative.append(card.description)
            latest_round.gear_equip_count += 1

        # 向场景内其他角色广播装备转化通知
        round_number = len(self._game.current_dungeon_combat_room.combat.rounds)
        stage_entity = self._game.resolve_stage_entity(entity)
        assert (
            stage_entity is not None
        ), f"EquipGearItemActionSystem: 无法找到 {entity.name} 所在的场景实体"
        self._game.broadcast_to_stage(
            entity=entity,
            agent_event=AgentEvent(
                message=_build_gear_notice(
                    entity.name,
                    item.name,
                    card.name,
                    round_number,
                )
            ),
            exclude_entities={stage_entity},
        )

    ####################################################################################################################################
    async def _generate_card(
        self,
        entity: Entity,
        gear: GearItem,
    ) -> Optional[Card]:
        """用发起穿装备的 Actor 上下文，将 GearItem 转化为一张 Card。"""

        actor_stats = compute_character_stats(entity)
        prompt = _build_gear_card_prompt(gear, actor_stats)
        condensed_prompt = _build_condensed_gear_card_prompt(gear, actor_stats)

        chat_client = DeepSeekClient(
            name=entity.name,
            full_prompt=prompt,
            condensed_prompt=condensed_prompt,
            messages=self._game.get_agent_memory(entity).messages,
        )

        try:
            await chat_client.chat()
        except Exception as e:
            logger.error(f"[EquipGearItemActionSystem] LLM 请求失败: {e}")
            return None

        if chat_client.response_ai_message is None:
            logger.error("[EquipGearItemActionSystem] LLM 返回空响应")
            return None

        try:
            response = _GearCardResponse.model_validate_json(
                extract_json(chat_client.response_content)
            )
        except Exception as e:
            logger.error(
                f"[EquipGearItemActionSystem] 解析 LLM 响应失败: {e}\n"
                f"{chat_client.response_content}"
            )
            return None

        valid_target_types = {t.value for t in TargetType}
        if response.target_type not in valid_target_types:
            logger.warning(
                f"[EquipGearItemActionSystem] target_type 无效: {response.target_type!r}"
            )
            return None

        card = Card(
            name=response.name or gear.name,
            description=response.description or gear.description,
            on_play_affixes=response.on_play_affixes,
            on_hit_affixes=response.on_hit_affixes,
            on_turn_end_affixes=response.on_turn_end_affixes,
            playable=response.playable,
            exhaust=response.exhaust,
            retain=response.retain,
            ethereal=response.ethereal,
            cost=response.cost,
            damage=response.damage,
            hit_count=response.hit_count,
            block=response.block,
            self_target=response.self_target,
            target_type=TargetType(response.target_type),
            source=entity.name,
            gear_item=gear,
        )

        # 计算端强制：GearItem 转化的卡牌跨回合保留在手牌（不进入弃牌堆）
        card.retain = True

        # 沿用 fill_draw_pile_system 的思路：卡牌自身值非 0 时，叠加当前行动者属性
        if card.damage != 0:
            card.damage += actor_stats.attack
        if card.block != 0:
            card.block += actor_stats.defense

        # 将本轮任务提示词与 LLM 回复写入发起穿装备的 Actor 上下文
        self._game.add_human_message(
            entity=entity,
            human_message=HumanMessage(
                content=chat_client.condensed_prompt,
                full_prompt=chat_client.full_prompt,
            ),
        )
        self._game.add_ai_message(
            entity=entity, ai_message=chat_client.response_ai_message
        )

        return card
