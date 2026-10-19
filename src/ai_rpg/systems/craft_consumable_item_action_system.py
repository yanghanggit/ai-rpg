"""工坊合成消耗品系统模块：两阶段（选型 + 设计）驱动消耗品工坊 agent 产出一件消耗品。

消耗品携带一张内置伤害卡牌，固定 0 费、一次性；两阶段都以工坊自身的 system message
作为唯一且临时上下文，结束后不写回持久记忆。
"""

from typing import Any, Dict, Final, List, final

from loguru import logger
from overrides import override

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    ConsumableItem,
    CraftConsumableItemAction,
    MaterialItem,
    StorageComponent,
    SystemMessage,
    append_item_with_stacking,
    deduct_materials,
)
from ..pgsql import list_card_prototype_index
from ..utils import prompt_builder
from .card_common import (
    materialize_candidate,
    run_card_design_session,
    run_card_selection_session,
)

#######################################################################################################################################
# 消耗品卡护栏：0 费、一次性、纯伤害（本阶段只做伤害型）。
CONSUMABLE_DAMAGE_MIN: Final[int] = 1
CONSUMABLE_DAMAGE_MAX: Final[int] = 8
CONSUMABLE_HIT_COUNT_MAX: Final[int] = 3

# 把「0 费 / 无格挡 / 数值区间」交给 submit_card 的 schema，设计提示词不再复述。
CONSUMABLE_CARD_PROPERTIES: Final[Dict[str, Any]] = {
    "cost": {
        "type": "integer",
        "const": 0,
        "description": "消耗品固定 0 费，恒为 0。",
    },
    "block": {
        "type": "integer",
        "const": 0,
        "description": "消耗品不提供格挡，恒为 0。",
    },
    "damage": {
        "type": "integer",
        "minimum": CONSUMABLE_DAMAGE_MIN,
        "maximum": CONSUMABLE_DAMAGE_MAX,
        "description": (
            f"单段伤害（{CONSUMABLE_DAMAGE_MIN}..{CONSUMABLE_DAMAGE_MAX}）；总伤害由 damage × hit_count 决定。"
        ),
    },
    "hit_count": {
        "type": "integer",
        "minimum": 1,
        "maximum": CONSUMABLE_HIT_COUNT_MAX,
        "description": f"攻击段数（1..{CONSUMABLE_HIT_COUNT_MAX}）。",
    },
}


#######################################################################################################################################
def _material_lines(materials: List[MaterialItem]) -> str:
    """把投入材料渲染成提示词片段。"""
    return "\n".join(
        f"- **{m.name}**（数量 {m.count}）：{m.description}" for m in materials
    )


#######################################################################################################################################
@prompt_builder
def _build_consumable_select_prompt(materials: List[MaterialItem]) -> str:
    """选型阶段提示词：结合投入材料，挑选恰好 1 个消耗品原型骨架。"""
    return f"""# 任务：为消耗品工坊挑选 1 个卡牌原型

## 投入材料

{_material_lines(materials)}

消耗品卡固定 0 费、一次性、只做伤害。请结合材料特质，从消耗品原型中挑一个最合适的骨架（单体 / 全体 / 散射）。先 `list_card_prototypes` 纵览，再对候选 `get_card_prototype` 精读，最后 `select_cards` 提交恰好 1 个 prototype_id。"""


#######################################################################################################################################
def _build_consumable_design_context(materials: List[MaterialItem]) -> str:
    """设计阶段的任务前言：投入材料 + 消耗品卡的固定约束。"""
    return f"""## 投入材料

{_material_lines(materials)}

## 消耗品约束

- 为「消耗品工坊」制作一件消耗品；`name` 采用「消耗品.XXXX」命名格式，`description` 说明外观、气味或使用感受（30-60 字），不出现数值与机制词。
- 这是一次性、只做伤害的消耗品。
- 词缀只能追加伤害类效果，且须贴合本次投入材料。"""


#######################################################################################################################################
@final
class CraftConsumableItemActionSystem(ReactiveProcessor):
    """工坊合成消耗品系统。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(CraftConsumableItemAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(CraftConsumableItemAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        assert len(entities) == 1, "同时存在多个 CraftConsumableAction，数据异常"
        entity = entities[0]
        await self._craft(entity)

    ####################################################################################################################################
    async def _craft(self, entity: Entity) -> None:
        """执行完整合成流程：选型 → 设计 → 组装 → 入库。

        Args:
            entity: 携带 CraftConsumableItemAction 的工坊世界实体
        """
        action = entity.get(CraftConsumableItemAction)

        storage_entity = self._game.get_storage_entity()
        if storage_entity is None or not storage_entity.has(StorageComponent):
            logger.error(
                "[CraftConsumableItemActionSystem] 全局储物箱实体不存在或缺少 StorageComponent"
            )
            return

        # 材料列表由 activate_craft_consumable 预填充（count = 本次使用量）
        materials = action.material_items

        # 消耗品原型库
        try:
            index = list_card_prototype_index(card_type="消耗品")
        except Exception as e:
            logger.error(f"[CraftConsumableItemActionSystem] 拉取消耗品原型失败: {e}")
            return
        if not index:
            logger.error("[CraftConsumableItemActionSystem] 消耗品原型库为空，中止")
            return

        # 上下文隔离：仅取世界实体的首条 SystemMessage 作为「设定」，
        # 每个阶段都用一份全新列表（agent_loop 原地追加），结束后不写回持久记忆。
        agent_memory = self._game.get_agent_memory(entity)
        assert agent_memory.messages, "消耗品工坊世界实体缺少首条 SystemMessage"
        assert isinstance(
            agent_memory.messages[0], SystemMessage
        ), "消耗品工坊世界实体 AI 记忆的第一条消息必须是 SystemMessage"
        system_message = agent_memory.messages[0]

        # 阶段一：选型（共用能力，恰好选 1 个原型）
        selection = await run_card_selection_session(
            entity.name,
            index,
            [system_message],
            size=1,
            prompt=_build_consumable_select_prompt(materials),
            max_rounds=8,
        )
        if not selection:
            logger.error("[CraftConsumableItemActionSystem] 选型失败，中止")
            return

        # 物化选中原型为候选卡
        candidate = materialize_candidate(selection.selected[0], entity.name)
        if candidate is None:
            logger.error(
                f"[CraftConsumableItemActionSystem] 物化原型 {selection.selected[0]!r} 失败，中止"
            )
            return

        # 阶段二：设计（带投入材料上下文；0 费 / 数值区间由 submit_card schema 约束）
        outcome = await run_card_design_session(
            entity.name,
            [candidate],
            [system_message],
            max_rounds=8,
            context=_build_consumable_design_context(materials),
            extra_properties=CONSUMABLE_CARD_PROPERTIES,
        )
        if not outcome.ok or outcome.designed != 1:
            logger.error(
                f"[CraftConsumableItemActionSystem] 设计未完成（{outcome.designed}/1），中止"
            )
            return

        # 消耗品卡兜底收敛：固定 0 费、一次性、纯伤害，数值落回护栏内
        card = candidate.card
        card.cost = 0
        card.block = 0
        card.exhaust = True
        card.playable = True
        card.damage = min(
            max(card.damage, CONSUMABLE_DAMAGE_MIN), CONSUMABLE_DAMAGE_MAX
        )
        card.hit_count = min(max(card.hit_count, 1), CONSUMABLE_HIT_COUNT_MAX)

        # 更新 StorageComponent：扣减材料 + 追加成品
        new_item = ConsumableItem(
            name=card.name,
            description=card.description,
            cards=[card],
            resources=action.material_items,
        )
        self._update_storage(storage_entity, action.material_names, new_item)

        logger.info(
            f"[CraftConsumableItemActionSystem] 合成完成: {new_item.name} cards={new_item.cards}"
        )

    ####################################################################################################################################
    def _update_storage(
        self,
        storage_entity: Entity,
        material_names: List[str],
        new_item: ConsumableItem,
    ) -> None:
        """扣减已用材料（跨同名条目结转、归零移除），并入合成品到 StorageComponent。"""
        storage = storage_entity.get(StorageComponent)

        updated_items = deduct_materials(storage.items, material_names)
        updated_items = append_item_with_stacking(updated_items, new_item)

        storage_entity.replace(StorageComponent, storage.name, updated_items)
