"""工坊制作时装系统：由世界实体生成时装（不含卡牌），产物进储物箱。"""

from typing import Dict, Final, List, Optional, final

from loguru import logger
from overrides import override
from pydantic import BaseModel

from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    CostumeItem,
    CraftCostumeItemAction,
    MaterialItem,
    StorageComponent,
    append_item_with_stacking,
    deduct_materials,
)
from ..utils import extract_json, prompt_builder


#######################################################################################################################################
@final
class _CraftCostumeItemResponse(BaseModel):
    """工坊制作时装的 LLM 响应数据模型。"""

    name: str = ""
    description: str = ""


#######################################################################################################################################
@prompt_builder
def _build_craft_costume_prompt(materials: List[MaterialItem]) -> str:
    """构建制作时装的 LLM 提示词。"""
    material_lines = "\n".join(
        f"- **{m.name}**（数量 {m.count}）：{m.description}" for m in materials
    )

    return f"""# 任务：根据材料创意制作一件时装

## 投入材料

{material_lines}

## 要求

- **name**：时装全名，采用「时装.XXXX」命名格式，体现材料特性与服饰风格，简洁有辨识度
- **description**：时装描述，30-60字，**面向文生图，只写客观、可观察的外观**：颜色、材质、款式、轮廓、剪裁、可见的工艺痕迹（如锤痕、缝线、补丁）与装饰细节等用眼睛能看到的信息
- 必须站在**第三方旁观者**视角，用中性、平实的陈述句描述这件时装本身；不引入穿着者、不写穿了之后显得如何

## 禁忌

- 禁止心理活动、情绪、意图、性格或身份推断
- 禁止比喻、拟人、抒情等文学修辞
- 禁止背景故事、来历、遭遇、评价与判断
- 禁止引入场景、地点、环境、光线、天气
- 禁止气味、声音、触感等非视觉信息
- 禁止“与本地风俗对比”之类的相对描述
- 禁止依赖外部或时间条件的动态描写（如“风一吹便贴在身上”）

## 注意

- 时装**不改变任何战斗属性**，仅作为外观道具
- 命名和描述请复核「游戏设定」与你的自身设定，保持约束与风格一致

## 输出格式

```json
{{
  "name": "时装.XXX",
  "description": "..."
}}
```

严格按 JSON 格式输出，不要添加其他内容。"""


#######################################################################################################################################
@final
class CraftCostumeItemActionSystem(ReactiveProcessor):
    """工坊制作时装系统。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(CraftCostumeItemAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(CraftCostumeItemAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        assert len(entities) == 1, "同时存在多个 CraftCostumeItemAction，数据异常"
        entity = entities[0]
        await self._craft(entity)

    ####################################################################################################################################
    async def _craft(self, entity: Entity) -> None:
        """执行完整制作流程。"""
        action = entity.get(CraftCostumeItemAction)

        storage_entity = self._game.get_storage_entity()
        if storage_entity is None or not storage_entity.has(StorageComponent):
            logger.error(
                "[CraftCostumeItemActionSystem] 全局储物箱实体不存在或缺少 StorageComponent"
            )
            return

        # 材料列表由 activate_craft_costume_item 预填充（count = 本次使用量）
        materials = action.material_items

        # 调用 LLM 生成时装
        result = await self._call_llm(entity, materials)
        if result is None:
            return

        # 更新 StorageComponent：扣减材料 + 追加成品
        new_item = CostumeItem(
            name=result.name,
            description=result.description,
            resources=action.material_items,
        )
        self._update_storage(storage_entity, action.material_names, new_item)

        logger.info(
            f"[CraftCostumeItemActionSystem] 制作完成: {new_item.name} description={new_item.description[:30]}..."
        )

    ####################################################################################################################################
    async def _call_llm(
        self,
        entity: Entity,
        materials: List[MaterialItem],
    ) -> Optional[_CraftCostumeItemResponse]:
        """调用工坊 agent 推理生成时装属性。"""

        # 构建 LLM 提示并初始化 DeepSeekClient，用于与 LLM 进行交互
        prompt = _build_craft_costume_prompt(materials)
        chat_client = DeepSeekClient(
            label=entity.name,
            input_message=prompt,
            messages=self._game.get_agent_memory(entity).messages,
        )

        # 发起 LLM 请求，捕获异常以防止整个流程崩溃
        try:
            await chat_client.chat()
        except Exception as e:
            logger.error(f"[CraftCostumeItemActionSystem] LLM 请求失败: {e}")
            return None

        # 检查 LLM 是否返回了有效的消息对象，如果为空则记录错误并返回 None
        if chat_client.response_ai_message is None:
            logger.error("[CraftCostumeItemActionSystem] LLM 回复消息为空")
            return None

        # 尝试从 LLM 的回复中提取 JSON 并解析为 _CraftCostumeItemResponse 对象
        try:
            json_str = extract_json(chat_client.response_content)
            response = _CraftCostumeItemResponse.model_validate_json(json_str)
            assert response.name, "LLM 返回的 name 不能为空"
        except Exception as e:
            logger.error(
                f"[CraftCostumeItemActionSystem] 解析 LLM 响应失败: {e}\n原始内容:\n{chat_client.response_content}"
            )
            return None

        # 再次检查解析后的 response 对象的 name 字段是否为空，确保 LLM 返回的内容有效
        if not response.name:
            logger.error("[CraftCostumeItemActionSystem] LLM 返回的 name 为空")
            return None

        # 返回解析成功的 response 对象，供调用方使用
        return response

    ####################################################################################################################################
    def _update_storage(
        self,
        storage_entity: Entity,
        material_names: List[str],
        new_item: CostumeItem,
    ) -> None:
        """扣减已用材料（跨同名条目结转、归零移除），并入制作品到 StorageComponent。"""
        storage = storage_entity.get(StorageComponent)

        updated_items = deduct_materials(storage.items, material_names)
        updated_items = append_item_with_stacking(updated_items, new_item)

        storage_entity.replace(StorageComponent, storage.name, updated_items)
