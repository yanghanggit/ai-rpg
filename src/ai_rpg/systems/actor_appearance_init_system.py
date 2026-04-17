from typing import Final, List, final
from loguru import logger
from overrides import override
from ..deepseek import DeepSeekClient
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import (
    ActorComponent,
    AllyComponent,
    AppearanceComponent,
    EquipmentComponent,
    InventoryComponent,
)


#######################################################################################################################################
def _format_appearance_init_notification(appearance: str) -> str:
    """格式化外观初始化通知消息。

    Args:
        appearance: 完整的外观描述

    Returns:
        格式化后的通知消息字符串
    """
    return f"""# 你的外观信息已经初始化: 

{appearance}"""


#######################################################################################################################################
def _format_appearance_llm_notification(appearance: str) -> str:
    """格式化 LLM 合成外观通知消息。

    Args:
        appearance: LLM 合成后的完整外观描述

    Returns:
        格式化后的通知消息字符串
    """
    return f"""# 你的外观信息已经更新: 

{appearance}"""


#######################################################################################################################################
def _build_appearance_generation_prompt(
    base_body: str,
    weapons_desc: str,
    armor_desc: str,
    accessory_desc: str,
) -> str:
    """构造外观合成 Prompt。

    Args:
        base_body: 角色基础身体描述（仅着内衣状态）
        weapons_desc: 当前装备的武器视觉描述，无则传空字符串
        armor_desc: 当前装备的套装视觉描述，无则传空字符串
        accessory_desc: 当前装备的饰品视觉描述，无则传空字符串

    Returns:
        完整 prompt 字符串
    """
    weapons_line = weapons_desc if weapons_desc else "无"
    armor_line = armor_desc if armor_desc else "无"
    accessory_line = accessory_desc if accessory_desc else "无"

    return f"""## 角色基础身体
{base_body}

## 当前穿戴装备（视觉描述参考）
武器：{weapons_line}
套装：{armor_line}
饰品：{accessory_line}

## 任务
根据以上信息，生成一段角色当前的完整外观描述。要求：
- 第三人称，客观描述可见视觉特征，严禁主观词汇（如"优雅""坚毅""沧桑"）和角色名字
- 严禁提及任何装备或物品的名称（可描述其视觉效果，如颜色、材质、形状、纹路）
- 严格遵守物理遮挡逻辑：装备遮住的部位不出现在描述中，未被遮住的部位据实描述，装备的视觉特征自然融入整体
- 输出纯文字，不加任何标题或 Markdown 格式"""


#######################################################################################################################################
@final
class ActorAppearanceInitSystem(ExecuteProcessor):
    """角色外观初始化系统（Init 语义）。

    在每帧执行时，将 base_body 赋值给 appearance，作为初始外观。
    仅处理 base_body 不为空且 appearance 为空的角色实体，天然幂等。

    后续可在此系统之后接入 LLM 生成系统，将 base_body + 装备信息合成
    更完整的 appearance 描述，覆盖此处的初始值。

    Attributes:
        _game: TCG游戏上下文，用于访问实体和游戏状态
    """

    def __init__(self, game: TCGGame) -> None:
        self._game: Final[TCGGame] = game

    #######################################################################################################################################
    @override
    async def execute(self) -> None:

        # Step 1: 所有角色 appearance == "" → base_body（含 Enemy）
        self._initialize_appearances()

        # Step 2: 仅盟友，LLM 合成 base_body + 装备 → appearance
        await self._generate_ally_appearances_with_llm()

    #######################################################################################################################################
    def _initialize_appearances(self) -> None:
        """将 base_body 赋值给 appearance，作为初始外观。

        筛选条件：base_body 不为空 且 appearance 为空。

        Args:
            actor_entities: 所有角色实体的集合
        """
        actor_entities = self._game.get_group(
            Matcher(all_of=[ActorComponent, AppearanceComponent])
        ).entities.copy()

        for actor_entity in actor_entities:

            appearance_comp = actor_entity.get(AppearanceComponent)
            assert (
                appearance_comp.base_body != ""
            ), f"角色 {actor_entity.name} 的 base_body 不能为空"

            if appearance_comp.appearance != "":
                continue

            actor_entity.replace(
                AppearanceComponent,
                appearance_comp.name,
                appearance_comp.base_body,
                appearance_comp.base_body,  # appearance 初始值 = base_body
            )

            self._game.add_human_message(
                actor_entity,
                _format_appearance_init_notification(appearance_comp.base_body),
            )

            logger.info(
                f"✅ 角色 {actor_entity.name} 外观已初始化（base_body → appearance）"
            )

    #######################################################################################################################################
    async def _generate_ally_appearances_with_llm(self) -> None:
        """LLM 合成盟友角色外观：base_body + 装备描述 → appearance。

        仅处理 AllyComponent 角色，且满足：
          - appearance == base_body（已初始化但未 LLM 增强）
          - EquipmentComponent 至少一个槽非空（有实际装备）

        天然幂等：LLM 写入后 appearance != base_body，不会二次触发。
        """
        ally_entities = self._game.get_group(
            Matcher(
                all_of=[
                    ActorComponent,
                    AppearanceComponent,
                    AllyComponent,
                    EquipmentComponent,
                    InventoryComponent,
                ]
            )
        ).entities.copy()

        chat_clients: List[DeepSeekClient] = []
        pending_entities: List[Entity] = []

        for actor_entity in ally_entities:
            appearance_comp = actor_entity.get(AppearanceComponent)
            equip_comp = actor_entity.get(EquipmentComponent)

            # 幂等：已 LLM 增强则跳过
            if appearance_comp.appearance != appearance_comp.base_body:
                continue

            # 无任何装备则跳过（base_body 即完整外观）
            has_equipment = (
                len(equip_comp.weapons) > 0
                or len(equip_comp.armor) > 0
                or len(equip_comp.accessory) > 0
            )
            if not has_equipment:
                continue

            inventory_comp = actor_entity.get(InventoryComponent)

            def _collect_desc(slot_names: List[str]) -> str:
                parts = [
                    item.description
                    for name in slot_names
                    for item in inventory_comp.items
                    if item.name == name and item.description
                ]
                return "；".join(parts)

            weapons_desc = _collect_desc(equip_comp.weapons)
            armor_desc = _collect_desc(equip_comp.armor)
            accessory_desc = _collect_desc(equip_comp.accessory)

            prompt = _build_appearance_generation_prompt(
                base_body=appearance_comp.base_body,
                weapons_desc=weapons_desc,
                armor_desc=armor_desc,
                accessory_desc=accessory_desc,
            )

            chat_clients.append(
                DeepSeekClient(
                    name=actor_entity.name,
                    prompt=prompt,
                    context=self._game.get_agent_context(actor_entity).context,
                    temperature=1.5,
                )
            )
            pending_entities.append(actor_entity)

        if not chat_clients:
            return

        await DeepSeekClient.batch_chat(clients=chat_clients)

        for actor_entity, chat_client in zip(pending_entities, chat_clients):
            new_appearance = chat_client.response_content.strip()
            if not new_appearance:
                logger.warning(
                    f"⚠️ 角色 {actor_entity.name} LLM 外观合成返回空内容，保留 base_body"
                )
                continue

            appearance_comp = actor_entity.get(AppearanceComponent)
            actor_entity.replace(
                AppearanceComponent,
                appearance_comp.name,
                appearance_comp.base_body,
                new_appearance,
            )

            self._game.add_human_message(
                actor_entity,
                _format_appearance_llm_notification(new_appearance),
            )

            logger.info(
                f"✅ 角色 {actor_entity.name} 外观已 LLM 合成（base_body + 装备 → appearance）"
            )

    #######################################################################################################################################
