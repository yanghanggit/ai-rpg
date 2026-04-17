from typing import Final, List, final, override
from loguru import logger
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    AgentEvent,
    EquipItemAction,
    InventoryComponent,
    EquipmentComponent,
    AppearanceComponent,
    WeaponItem,
    EquipmentItem,
    EquipmentType,
)
from ..game.tcg_game import TCGGame
from .actor_appearance_init_system import (
    _build_appearance_generation_prompt,
    _format_appearance_llm_notification,
)


#######################################################################################################################################
def _collect_desc(slot_names: List[str], inventory_comp: InventoryComponent) -> str:
    """从背包中收集指定槽位名称对应物品的视觉描述。

    Args:
        slot_names: 槽位中已装备物品的名称列表
        inventory_comp: 角色背包组件（物品来源）

    Returns:
        物品描述用「；」连接的字符串，无匹配时返回空字符串
    """
    parts = [
        item.description
        for name in slot_names
        for item in inventory_comp.items
        if item.name == name and item.description
    ]
    return "；".join(parts)


#######################################################################################################################################
@final
class EquipItemActionSystem(ReactiveProcessor):
    """装备物品动作处理系统。

    响应式处理器，监听 EquipItemAction 组件触发，将背包中指定物品装备到
    对应槽位（EquipmentComponent），然后通过 LLM 重新合成 AppearanceComponent。

    槽位路由规则：
        - WeaponItem              → weapons（最多 2 件，超出则替换 index 0）
        - EquipmentItem(ARMOR)    → armor（单槽，覆盖）
        - EquipmentItem(ACCESSORY)→ accessory（单槽，覆盖）
        - 其他类型                → 跳过并记录警告
    """

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    #######################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(EquipItemAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(EquipItemAction)
            and entity.has(InventoryComponent)
            and entity.has(EquipmentComponent)
            and entity.has(AppearanceComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        chat_clients: List[DeepSeekClient] = []
        pending_entities: List[Entity] = []

        for entity in entities:
            if not self._equip_item(entity):
                continue

            chat_client = self._build_appearance_client(entity)
            # if chat_client is None:
            #     continue

            chat_clients.append(chat_client)
            pending_entities.append(entity)

        if not chat_clients:
            return

        await DeepSeekClient.batch_chat(clients=chat_clients)

        for entity, chat_client in zip(pending_entities, chat_clients):
            new_appearance = chat_client.response_content.strip()
            if not new_appearance:
                logger.warning(f"⚠️ {entity.name} 装备后外观合成返回空内容，保留旧外观")
                continue

            appearance_comp = entity.get(AppearanceComponent)
            entity.replace(
                AppearanceComponent,
                appearance_comp.name,
                appearance_comp.base_body,
                new_appearance,
            )

            self._game.broadcast_to_stage(
                entity,
                AgentEvent(message=_format_appearance_llm_notification(new_appearance)),
            )

            logger.info(f"✅ {entity.name} 外观已重新合成（装备后）")

    #######################################################################################################################################
    def _equip_item(self, entity: Entity) -> bool:
        """根据 EquipItemAction 将物品装备到对应槽位。

        Returns:
            True 表示装备成功，False 表示跳过（物品不存在或类型不支持）。
        """
        action = entity.get(EquipItemAction)
        item_name = action.item_name

        inventory_comp = entity.get(InventoryComponent)
        target_item = next(
            (item for item in inventory_comp.items if item.name == item_name),
            None,
        )

        if target_item is None:
            logger.warning(f"⚠️ {entity.name} 尝试装备不在背包中的物品: {item_name}")
            return False

        equip_comp = entity.get(EquipmentComponent)

        if isinstance(target_item, WeaponItem):
            weapons = list(equip_comp.weapons)
            if len(weapons) < 2:
                weapons.append(item_name)
            else:
                weapons[0] = item_name
            entity.replace(
                EquipmentComponent,
                equip_comp.name,
                weapons,
                list(equip_comp.armor),
                list(equip_comp.accessory),
            )
            logger.info(f"⚔️ {entity.name} 装备武器: {item_name}")
            return True

        if isinstance(target_item, EquipmentItem):
            if target_item.equipment_type == EquipmentType.ARMOR:
                entity.replace(
                    EquipmentComponent,
                    equip_comp.name,
                    list(equip_comp.weapons),
                    [item_name],
                    list(equip_comp.accessory),
                )
                logger.info(f"🛡️ {entity.name} 装备套装: {item_name}")
                return True

            if target_item.equipment_type == EquipmentType.ACCESSORY:
                entity.replace(
                    EquipmentComponent,
                    equip_comp.name,
                    list(equip_comp.weapons),
                    list(equip_comp.armor),
                    [item_name],
                )
                logger.info(f"💍 {entity.name} 装备饰品: {item_name}")
                return True

        logger.warning(f"⚠️ {entity.name} 物品 {item_name} 类型不支持装备，跳过")
        return False

    #######################################################################################################################################
    def _build_appearance_client(self, entity: Entity) -> DeepSeekClient:
        """构建外观合成 LLM 客户端。"""
        appearance_comp = entity.get(AppearanceComponent)
        equip_comp = entity.get(EquipmentComponent)
        inventory_comp = entity.get(InventoryComponent)

        prompt = _build_appearance_generation_prompt(
            base_body=appearance_comp.base_body,
            weapons_desc=_collect_desc(equip_comp.weapons, inventory_comp),
            armor_desc=_collect_desc(equip_comp.armor, inventory_comp),
            accessory_desc=_collect_desc(equip_comp.accessory, inventory_comp),
        )

        return DeepSeekClient(
            name=entity.name,
            prompt=prompt,
            context=self._game.get_agent_context(entity).context,
            temperature=1.5,
        )
