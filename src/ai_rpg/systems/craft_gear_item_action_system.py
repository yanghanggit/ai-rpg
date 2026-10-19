"""工坊合成装备系统模块：两阶段（选型 + 设计）驱动装备工坊 agent 产出一件装备。

装备级被动只有 `speed`，其余效果走卡牌通道；两阶段都以工坊自身的 system message 作为
唯一且临时上下文，结束后不写回持久记忆。
"""

from typing import Any, Dict, Final, List, final

from loguru import logger
from overrides import override

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    CraftGearItemAction,
    GearItem,
    MaterialItem,
    StorageComponent,
    SystemMessage,
    append_item_with_stacking,
    deduct_materials,
)
from ..pgsql import list_card_prototype_index
from ..utils import prompt_builder
from .card_common import (
    CardDesign,
    materialize_candidate,
    run_card_design_session,
    run_card_selection_session,
)

#######################################################################################################################################
# 装备速度修正的护栏：速度可正可负，决定战斗回合行动顺序；装备的 damage/block 走卡牌通道，
# 速度是唯一的装备级被动。
GEAR_SPEED_MIN: Final[int] = -2
GEAR_SPEED_MAX: Final[int] = 3

# submit_card 的领域扩展字段：装备级 speed。范围交给 schema（minimum/maximum）。
GEAR_SPEED_PROPERTY: Final[Dict[str, Any]] = {
    "type": "integer",
    "minimum": GEAR_SPEED_MIN,
    "maximum": GEAR_SPEED_MAX,
    "description": (
        "装备级被动速度修正，可正可负：决定战斗回合行动顺序，数值越大越先出手。轻捷灵便取正值、沉重笨拙取负值，把握不准取 0。装备的伤害/格挡由卡牌承载，speed 是唯一的装备级被动。"
    ),
}


#######################################################################################################################################
def _material_lines(materials: List[MaterialItem]) -> str:
    """把投入材料渲染成提示词片段。"""
    return "\n".join(
        f"- **{m.name}**（数量 {m.count}）：{m.description}" for m in materials
    )


#######################################################################################################################################
@prompt_builder
def _build_gear_select_prompt(materials: List[MaterialItem]) -> str:
    """选型阶段提示词：结合投入材料，挑选恰好 1 个装备原型骨架。"""
    return f"""# 任务：为装备工坊挑选 1 个卡牌原型

## 投入材料

{_material_lines(materials)}

装备是一件在战斗中被转化为手牌的物品；卡牌骨架（是否可出牌、格挡、转移等）由原型给定。请结合材料特质，从装备原型中挑一个最合适的骨架。先 `list_card_prototypes` 纵览，再对候选 `get_card_prototype` 精读，最后 `select_cards` 提交恰好 1 个 prototype_id。"""


#######################################################################################################################################
def _build_gear_design_context(materials: List[MaterialItem]) -> str:
    """设计阶段的任务前言：投入材料 + 装备卡的固定约束与 speed 说明。"""
    return f"""## 投入材料

{_material_lines(materials)}

## 装备约束

- 为「装备工坊」制作一件奇幻世界的装备；`name` 采用「装备.XXXX」命名格式，`description` 说明外观、手感或穿戴感受（30-60 字），不出现数值与机制词。
- 卡牌骨架（flags / target_type）由所选原型给定，不要改动；数值与词缀在原型开放的槽位内设计。
- 词缀须贴合本次投入材料。"""


#######################################################################################################################################
@final
class CraftGearItemActionSystem(ReactiveProcessor):
    """工坊合成装备系统。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(CraftGearItemAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(CraftGearItemAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        assert len(entities) == 1, "同时存在多个 CraftGearItemAction，数据异常"
        entity = entities[0]
        await self._craft(entity)

    ####################################################################################################################################
    async def _craft(self, entity: Entity) -> None:
        """执行完整合成流程：选型 → 设计（含 speed）→ 组装 → 入库。

        Args:
            entity: 携带 CraftGearItemAction 的工坊世界实体
        """
        action = entity.get(CraftGearItemAction)

        storage_entity = self._game.get_storage_entity()
        if storage_entity is None or not storage_entity.has(StorageComponent):
            logger.error(
                "[CraftGearItemActionSystem] 全局储物箱实体不存在或缺少 StorageComponent"
            )
            return

        # 材料列表由 activate_craft_gear_item 预填充（count = 本次使用量）
        materials = action.material_items

        # 装备原型库
        try:
            index = list_card_prototype_index(card_type="装备")
        except Exception as e:
            logger.error(f"[CraftGearItemActionSystem] 拉取装备原型失败: {e}")
            return
        if not index:
            logger.error("[CraftGearItemActionSystem] 装备原型库为空，中止")
            return

        # 上下文隔离：仅取世界实体的首条 SystemMessage 作为「设定」，
        # 每个阶段都用一份全新列表（agent_loop 原地追加），结束后不写回持久记忆。
        agent_memory = self._game.get_agent_memory(entity)
        assert agent_memory.messages, "装备工坊世界实体缺少首条 SystemMessage"
        assert isinstance(
            agent_memory.messages[0], SystemMessage
        ), "装备工坊世界实体 AI 记忆的第一条消息必须是 SystemMessage"
        system_message = agent_memory.messages[0]

        # 阶段一：选型（共用能力，恰好选 1 个原型）
        selection = await run_card_selection_session(
            entity.name,
            index,
            [system_message],
            size=1,
            prompt=_build_gear_select_prompt(materials),
            max_rounds=8,
        )
        if not selection:
            logger.error("[CraftGearItemActionSystem] 选型失败，中止")
            return

        # 物化选中原型为候选卡；装备成品只是储物箱中的模板，source 留空
        # （真正的持有者 source 由 EquipGearItemActionSystem 物化为手牌时回填）
        candidate = materialize_candidate(selection.selected[0], "")
        if candidate is None:
            logger.error(
                f"[CraftGearItemActionSystem] 物化原型 {selection.selected[0]!r} 失败，中止"
            )
            return

        # 捕获 submit_card 扩展字段里的装备级 speed
        captured: Dict[str, int] = {}

        def _capture_speed(edit: CardDesign) -> None:
            value = (edit.model_extra or {}).get("speed")
            if isinstance(value, int):
                captured["speed"] = value

        # 阶段二：设计（带投入材料上下文 + speed 扩展字段）
        outcome = await run_card_design_session(
            entity.name,
            [candidate],
            [system_message],
            max_rounds=8,
            context=_build_gear_design_context(materials),
            extra_properties={"speed": GEAR_SPEED_PROPERTY},
            extra_required=["speed"],
            on_design=_capture_speed,
        )
        if not outcome.ok or outcome.designed != 1:
            logger.error(
                f"[CraftGearItemActionSystem] 设计未完成（{outcome.designed}/1），中止"
            )
            return

        # speed 兜底收敛到护栏内
        speed = min(max(captured.get("speed", 0), GEAR_SPEED_MIN), GEAR_SPEED_MAX)

        card = candidate.card

        # 更新 StorageComponent：扣减材料 + 追加成品
        new_item = GearItem(
            name=card.name,
            description=card.description,
            speed=speed,
            resources=action.material_items,
            cards=[card],
        )
        self._update_storage(storage_entity, action.material_names, new_item)

        logger.info(
            f"[CraftGearItemActionSystem] 合成完成: {new_item.name} speed={speed} cards={new_item.cards}"
        )

    ####################################################################################################################################
    def _update_storage(
        self,
        storage_entity: Entity,
        material_names: List[str],
        new_item: GearItem,
    ) -> None:
        """扣减已用材料（跨同名条目结转、归零移除），并入合成品到 StorageComponent。"""
        storage = storage_entity.get(StorageComponent)

        updated_items = deduct_materials(storage.items, material_names)
        updated_items = append_item_with_stacking(updated_items, new_item)

        storage_entity.replace(StorageComponent, storage.name, updated_items)
