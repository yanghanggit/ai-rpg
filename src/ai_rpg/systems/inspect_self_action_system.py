from typing import Final, final, override
from loguru import logger
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    InspectSelfAction,
    InventoryComponent,
    CharacterStats,
    EquipmentComponent,
)
from ..game.tcg_game import TCGGame


#############################################################################################################################
def _format_equipment(entity: Entity) -> str:
    """格式化角色当前装备槽位信息为可读文本。"""
    if not entity.has(EquipmentComponent):
        return "（无装备数据）"

    equip = entity.get(EquipmentComponent)
    weapon_line = equip.weapon if equip.weapon else "（未装备）"
    armor_line = equip.armor if equip.armor else "（未装备）"
    accessory_line = equip.accessory if equip.accessory else "（未装备）"
    return f"武器：{weapon_line}\n套装：{armor_line}\n饰品：{accessory_line}"


#############################################################################################################################
def _format_inventory(entity: Entity) -> str:
    """格式化角色背包物品列表为可读文本。"""
    if not entity.has(InventoryComponent):
        return "（无背包数据）"

    items = entity.get(InventoryComponent).items
    if not items:
        return "（背包为空）"

    lines = []
    for item in items:
        lines.append(f"- {item.name}（x{item.count}）: {item.description}")
    return "\n".join(lines)


#############################################################################################################################
def _format_stats(stats: CharacterStats) -> str:
    """格式化角色战斗属性为可读文本。"""
    return (
        f"HP: {stats.hp}/{stats.max_hp} | "
        f"攻击: {stats.attack} | 防御: {stats.defense} | "
        f"速度: {stats.speed} | 行动次数: {stats.energy}"
    )


#############################################################################################################################
def _build_inspect_self_message(
    actor: str, inventory_text: str, stats_text: str, equipment_text: str
) -> str:
    """构建自我审视结果的提示词消息。"""
    return f"""# {actor} 自我审视

## 当前已装备

{equipment_text}

## 当前背包

{inventory_text}

## 当前战斗属性

{stats_text}

## 提示

- 以上是你目前的真实状态，可根据需要参考。"""


#############################################################################################################################
@final
class InspectSelfActionSystem(ReactiveProcessor):
    """自我审视动作处理系统。

    响应式处理器，监听 InspectSelfAction 组件触发，
    将角色的背包物品与战斗属性格式化后注入 LLM context。
    """

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    #############################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(InspectSelfAction): GroupEvent.ADDED}

    #############################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(InspectSelfAction)

    #############################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_action(entity)

    #############################################################################################################################
    def _process_action(self, entity: Entity) -> None:
        inventory_text = _format_inventory(entity)
        stats_text = _format_stats(self._game.compute_character_stats(entity))
        equipment_text = _format_equipment(entity)

        logger.success(
            f"🔍 {entity.name} 发起自我审视 | 背包物品数: "
            f"{len(entity.get(InventoryComponent).items) if entity.has(InventoryComponent) else 0}"
        )

        message = _build_inspect_self_message(
            actor=entity.name,
            inventory_text=inventory_text,
            stats_text=stats_text,
            equipment_text=equipment_text,
        )
        self._game.add_human_message(entity, message)


#############################################################################################################################
