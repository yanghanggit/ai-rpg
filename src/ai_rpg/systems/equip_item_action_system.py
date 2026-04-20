from typing import Final, List, final, override
from loguru import logger
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    AppearanceUpdateEvent,
    EquipItemAction,
    InventoryComponent,
    EquipmentComponent,
    AppearanceComponent,
)
from ..game.tcg_game import TCGGame
from .actor_appearance_init_system import (
    _build_appearance_generation_prompt,
    _format_appearance_llm_notification,
)


#######################################################################################################################################
def _collect_desc(slot_name: str, inventory_comp: InventoryComponent) -> str:
    """从背包中查找指定槽位物品的视觉描述。

    Args:
        slot_name: 槽位中当前装备的物品名称
        inventory_comp: 角色背包组件（物品来源）

    Returns:
        匹配物品的 description，无匹配时返回空字符串
    """
    if not slot_name:
        return ""
    for item in inventory_comp.items:
        if item.name == slot_name and item.description:
            return item.description
    return ""


#######################################################################################################################################
def _format_item_not_found_notification(actor_name: str, item_name: str) -> str:
    """格式化装备不存在时的提示消息。

    Args:
        actor_name: 角色名称
        item_name: 未找到的物品名称

    Returns:
        格式化后的提示消息，引导 Agent 下一轮使用 inspect_self 确认背包内容
    """
    return (
        f"# 提示\n\n"
        f"{actor_name} 背包中不存在名为「{item_name}」的装备，装备操作已取消。\n"
        f"如需确认背包中的物品全名，请下一轮使用 `inspect_self` 查阅背包与属性。"
    )


#######################################################################################################################################
def _format_appearance_llm_notification_for_others(
    actor_name: str, appearance: str
) -> str:
    """格式化 LLM 合成外观通知消息（广播给场景内其他实体）。

    Args:
        actor_name: 发生外观变化的角色名称
        appearance: LLM 合成后的完整外观描述

    Returns:
        格式化后的通知消息字符串
    """
    return f"""# {actor_name} 外观信息已经更新: 

{appearance}"""


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

            # 对自身：「你的外观已更新」
            self._game.add_human_message(
                entity,
                _format_appearance_llm_notification(new_appearance),
            )

            # 对场景内其他实体：第三人称广播
            self._game.broadcast_to_stage(
                entity,
                AppearanceUpdateEvent(
                    message=_format_appearance_llm_notification_for_others(
                        entity.name, new_appearance
                    ),
                    actor=entity.name,
                    appearance=new_appearance,
                ),
                exclude_entities={entity},
            )

            logger.info(f"✅ {entity.name} 外观已重新合成（装备后）")

    #######################################################################################################################################
    def _equip_item(self, entity: Entity) -> bool:
        """根据 EquipItemAction 更新装备槽位。

        每个字段：None 表示不更换该槽；"" 表示脱掉该槽；非空字符串表示装备该物品。

        Returns:
            True 表示装备成功；False 表示有槽位物品不在背包中，已截断并注入提示
        """
        action = entity.get(EquipItemAction)
        inventory_comp = entity.get(InventoryComponent)

        # 验证所有非空槽位的物品是否存在于背包
        for slot_name in (action.weapon, action.armor, action.accessory):
            if not slot_name:  # None（不更换）或 ""（脱掉）均跳过
                continue
            if not any(item.name == slot_name for item in inventory_comp.items):
                self._game.add_human_message(
                    entity,
                    _format_item_not_found_notification(entity.name, slot_name),
                )
                logger.warning(
                    f"⚠️ {entity.name} 尝试装备「{slot_name}」，但背包中不存在该物品，操作已截断"
                )
                return False

        equip_comp = entity.get(EquipmentComponent)

        new_weapon = action.weapon if action.weapon is not None else equip_comp.weapon
        new_armor = action.armor if action.armor is not None else equip_comp.armor
        new_accessory = (
            action.accessory if action.accessory is not None else equip_comp.accessory
        )

        entity.replace(
            EquipmentComponent,
            equip_comp.name,
            new_weapon,
            new_armor,
            new_accessory,
        )

        if new_weapon != equip_comp.weapon:
            logger.info(
                f"⚔️ {entity.name} 武器槽: {equip_comp.weapon!r} → {new_weapon!r}"
            )
        if new_armor != equip_comp.armor:
            logger.info(f"🛡️ {entity.name} 套装槽: {equip_comp.armor!r} → {new_armor!r}")
        if new_accessory != equip_comp.accessory:
            logger.info(
                f"💍 {entity.name} 饰品槽: {equip_comp.accessory!r} → {new_accessory!r}"
            )

        return True

    #######################################################################################################################################
    def _build_appearance_client(self, entity: Entity) -> DeepSeekClient:
        """构建外观合成 LLM 客户端。"""
        appearance_comp = entity.get(AppearanceComponent)
        equip_comp = entity.get(EquipmentComponent)
        inventory_comp = entity.get(InventoryComponent)

        prompt = _build_appearance_generation_prompt(
            base_body=appearance_comp.base_body,
            weapons_desc=_collect_desc(equip_comp.weapon, inventory_comp),
            armor_desc=_collect_desc(equip_comp.armor, inventory_comp),
            accessory_desc=_collect_desc(equip_comp.accessory, inventory_comp),
        )

        return DeepSeekClient(
            name=entity.name,
            prompt=prompt,
            context=self._game.get_agent_context(entity).context,
            temperature=1.0,
        )
