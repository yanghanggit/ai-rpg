"""副本插图系统：把风格与场景描述合成为插图提示词并归档。"""

from functools import partial
from typing import Any, Dict, Final, List, Optional, Sequence, final, override

from loguru import logger
from pydantic import BaseModel

from ..deepseek import ToolDefinition, ToolFunction, agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    AssetKey,
    ChatMessage,
    Dungeon,
    DungeonRoom,
    GenerateDungeonAction,
    IllustrationComponent,
    ImageMeta,
    SystemMessage,
)
from ..paths import DUNGEONS_DIR
from ..replicate import DEFAULT_IMAGE_MODEL, TextToImageSpec, batch_text_to_images
from ..utils import prompt_builder

####################################################################################################################################
# 图片生成规格（引擎级：尺寸 / 模型，与具体故事无关）
_IMAGE_WIDTH: Final[int] = 1344  # 16:9 横屏（nano-banana 原生宽高比）
_IMAGE_HEIGHT: Final[int] = 768

# 正向提示词最短长度保护：过短几乎必然是占位/偷懒输出
_MIN_PROMPT_LENGTH: Final[int] = 20
# LLM 偶发偷懒时会把字段填成这些占位值；命中即视为非法
_PLACEHOLDER_TOKENS: Final[frozenset[str]] = frozenset(
    {"placeholder", "todo", "tbd", "n/a", "na", "none", "null", "...", "同上"}
)


def _is_invalid_prompt(text: str) -> bool:
    """判断提示词是否为无效值（空 / 占位符 / 过短）。"""
    stripped = (text or "").strip()
    if not stripped:
        return True
    if stripped.lower().strip("。.") in _PLACEHOLDER_TOKENS:
        return True
    if "placeholder" in stripped.lower():
        return True
    return len(stripped) < _MIN_PROMPT_LENGTH


####################################################################################################################################
@final
class _ImagePrompt(BaseModel):
    """单张插图的最终提示词（LLM 工具产物）。"""

    target: str  # "cover" 或房间对应的场景全名
    prompt: str  # 正向提示词
    negative_prompt: str = ""  # 负面提示词


####################################################################################################################################
@final
class _ImagePromptsResult(BaseModel):
    """record_image_prompts handler 的结果容器。"""

    images: List[_ImagePrompt] = []


####################################################################################################################################
def _build_record_image_prompts_tool(room_targets: List[str]) -> ToolDefinition:
    """动态构建 record_image_prompts 工具定义。

    需覆盖 1 张封面（target="cover"）与 len(room_targets) 张房间插图
    （target 为对应场景全名）。
    """
    total = len(room_targets) + 1
    return ToolDefinition(
        function=ToolFunction(
            name="record_image_prompts",
            description=(
                f'一次性提交全部 {total} 张插图的最终文生图提示词：1 张副本封面（target="cover"）与 {len(room_targets)} 张房间插图（target 为对应场景全名）。每条含正向提示词与负面提示词。'
            ),
            parameters={
                "type": "object",
                "properties": {
                    "images": {
                        "type": "array",
                        "minItems": total,
                        "maxItems": total,
                        "items": {
                            "type": "object",
                            "properties": {
                                "target": {
                                    "type": "string",
                                    "enum": [AssetKey.COVER] + room_targets,
                                    "description": (
                                        '"cover" 为副本封面；其余为房间对应的场景全名，每个 target 恰好出现一次'
                                    ),
                                },
                                "prompt": {
                                    "type": "string",
                                    "description": "该图的最终正向提示词（中文，具体、视觉化，可被图像模型直接理解）",
                                },
                                "negative_prompt": {
                                    "type": "string",
                                    "description": "该图的负面提示词，列出需要排除的元素",
                                },
                            },
                            "required": ["target", "prompt", "negative_prompt"],
                        },
                    },
                },
                "required": ["images"],
            },
        )
    )


####################################################################################################################################
def _handle_record_image_prompts(
    result: _ImagePromptsResult, expected_targets: List[str], images: List[Any]
) -> str:
    """处理 record_image_prompts 工具调用：严格校验 target 覆盖后暂存提示词。"""
    items = [_ImagePrompt.model_validate(item) for item in images]
    got = [item.target for item in items]
    missing = [target for target in expected_targets if target not in got]
    unexpected = [target for target in got if target not in expected_targets]
    duplicated = sorted({target for target in got if got.count(target) > 1})
    if missing or unexpected or duplicated:
        return f"错误：target 集合与要求不符。缺失={missing}，多余={unexpected}，重复={duplicated}。必须恰好覆盖：{expected_targets}"

    # 内容合法性校验：拒绝空值、占位符与过短提示词，避免把垃圾提示词送进图像模型
    invalid = [item.target for item in items if _is_invalid_prompt(item.prompt)]
    if invalid:
        return f"错误：以下 target 的 prompt 为空、占位符或过短：{invalid}。必须为每个 target 写出完整、具体、可独立送进图像模型的中文正向提示词，请修正后重新调用 record_image_prompts。"

    result.images = items
    for item in items:
        logger.info(
            f"[IllustrateDungeonSystem] record_image_prompts: target={item.target!r}, prompt={item.prompt!r}"
        )
    return result.model_dump_json(ensure_ascii=False)


####################################################################################################################################
@prompt_builder
def _build_image_prompts_prompt(
    dungeon_name: str, dungeon_profile: str, rooms: Sequence[DungeonRoom]
) -> str:
    """构建插图提示词编排的 LLM 提示词：列出封面与各房间的场景事实。"""

    total = len(rooms) + 1
    sections: List[str] = [
        '### 封面（target="cover"）',
        "- 依据：上面的副本整体设定，呈现副本的整体空间与氛围（纯环境）。",
    ]
    for index, room in enumerate(rooms, start=1):
        sections.append(
            f'### 房间 {index}：{room.stage.name}（target="{room.stage.name}"）\n- 场景设定：{room.stage.profile}'
        )

    scenes = "\n\n".join(sections)
    return f"""# 任务：为副本「{dungeon_name}」编排全部插图的文生图提示词

本次共需出图 {total} 张：1 张副本封面与 {len(rooms)} 张房间插图。所有插图一律为纯环境画面，只描绘场景本身，不得出现任何人物、动物、怪物或其他生物（包括其剪影与残影）。请依据你的视觉方向与提示词写作要求，分别为每一张图写一条正向提示词与一条负面提示词。

## 副本整体设定

{dungeon_profile}

## 需要出图的画面

{scenes}

## 工作流程

调用 record_image_prompts 一次性提交全部 {total} 条提示词（每条含 target / prompt / negative_prompt），target 必须与上面的标注一一对应，确认无误后结束本次对话。"""


####################################################################################################################################
@final
class IllustrateDungeonSystem(ReactiveProcessor):
    """副本图片生成系统"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {
            Matcher(GenerateDungeonAction): GroupEvent.ADDED,
        }

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(GenerateDungeonAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        # 插图生成当前禁用，仅监听入口 action
        pass

    ####################################################################################################################################
    async def _generate_images(self) -> None:
        """为当前副本执行图片并发生成（当前禁用，未挂入 react）。"""
        draft = self._game._dungeon_draft
        if draft is None or not draft.dungeon_name:
            logger.error("[IllustrateDungeonSystem] 中间过程数据缺失，跳过插图生成")
            return
        dungeon_path = DUNGEONS_DIR / f"{draft.dungeon_name}.json"

        if not dungeon_path.exists():
            logger.error(
                f"[IllustrateDungeonSystem] Dungeon 文件不存在: {dungeon_path}"
            )
            return

        try:
            dungeon = Dungeon.model_validate_json(
                dungeon_path.read_text(encoding="utf-8")
            )
        except Exception as e:
            logger.error(
                f"[IllustrateDungeonSystem] 解析 Dungeon 失败: {e}\n路径: {dungeon_path}"
            )
            return

        # 定位唯一的插图提示词世界实体
        prompt_entities = self._game.get_group(
            Matcher(all_of=[IllustrationComponent])
        ).entities.copy()
        if len(prompt_entities) != 1:
            logger.error(
                f"[IllustrateDungeonSystem] 插图提示词实体数量异常: {len(prompt_entities)}，跳过插图生成"
            )
            return

        # 获取唯一的插图提示词实体
        prompt_entity = next(iter(prompt_entities))

        # LLM 编排提示词（失败则跳过，不阻塞主流程）
        prompts = await self._compose_prompts(prompt_entity, dungeon)
        if prompts is None:
            logger.warning(
                f"[IllustrateDungeonSystem]提示词编排失败，跳过插图: {dungeon.name}"
            )
            return

        # 组装生成任务：封面（index 0）+ 各房间（index 1..N）
        by_target = {item.target: item for item in prompts}
        specs: List[TextToImageSpec] = [self._to_spec(by_target[AssetKey.COVER])] + [
            self._to_spec(by_target[room.stage.name]) for room in dungeon.rooms
        ]

        # 并发批量生成；返回值与 specs 顺序一一对应，失败项为 None
        metas: List[Optional[ImageMeta]] = await batch_text_to_images(specs=specs)

        # 写入封面资源地址（只落 meta 路径，ImageMeta 对象由 replicate 层写入 .assets/image/*.meta）
        cover_meta = metas[0]
        if cover_meta is not None:
            dungeon.assets[AssetKey.COVER] = str(cover_meta.meta_path)
            logger.info(
                f"[IllustrateDungeonSystem]封面图片生成完成: {cover_meta.local_path}"
            )
        else:
            logger.warning(f"[IllustrateDungeonSystem]封面图片生成失败: {dungeon.name}")

        # 写入各房间资源地址（失败项不写入，保持 stage.assets 原状）
        for room, meta in zip(dungeon.rooms, metas[1:]):
            if meta is not None:
                room.stage.assets[AssetKey.ILLUSTRATION] = str(meta.meta_path)
                logger.info(
                    f"[IllustrateDungeonSystem]房间插图生成完成: {room.stage.name} -> {meta.local_path}"
                )
            else:
                logger.warning(
                    f"[IllustrateDungeonSystem]房间插图生成失败: {room.stage.name}"
                )

        # 将更新后的 dungeon（含 assets 地址）重新保存到磁盘
        dungeon_path.write_text(dungeon.model_dump_json(indent=4), encoding="utf-8")
        logger.info(
            f"[IllustrateDungeonSystem] Dungeon 已更新（含 assets 地址）: {dungeon_path}"
        )

    ####################################################################################################################################
    async def _compose_prompts(
        self, prompt_entity: Entity, dungeon: Dungeon
    ) -> Optional[List[_ImagePrompt]]:
        """让「世界.插图提示词」实体为封面与全部房间编排提示词。

        使用隔离记忆（仅该实体的 system prompt），避免跨副本累积污染上下文。
        返回 None 表示编排失败。
        """
        expected_targets = [AssetKey.COVER] + [
            room.stage.name for room in dungeon.rooms
        ]
        result = _ImagePromptsResult()

        memory = self._game.get_agent_memory(prompt_entity).messages
        assert memory and isinstance(
            memory[0], SystemMessage
        ), f"{prompt_entity.name} 缺少 system message"
        # 隔离记忆：每副本一份全新上下文（agent_loop 原地追加，用完即弃）
        messages: List[ChatMessage] = [SystemMessage(content=memory[0].content)]
        image_prompts_tool = _build_record_image_prompts_tool(expected_targets[1:])

        ok = await agent_loop(
            name=prompt_entity.name,
            input_message=_build_image_prompts_prompt(
                dungeon_name=dungeon.name,
                dungeon_profile=dungeon.profile,
                rooms=dungeon.rooms,
            ),
            messages=messages,
            tools=[image_prompts_tool],
            handlers={
                image_prompts_tool.function.name: partial(
                    _handle_record_image_prompts, result, expected_targets
                )
            },
            max_rounds=5,
        )

        if not ok:
            logger.error(
                f"[IllustrateDungeonSystem] 提示词编排 agent_loop 失败: {dungeon.name}"
            )
            return None

        if len(result.images) != len(expected_targets):
            logger.error(
                f"[IllustrateDungeonSystem] 提示词数量不符：期望 {len(expected_targets)}，实际 {len(result.images)}"
            )
            return None

        return result.images

    ####################################################################################################################################
    def _to_spec(self, item: _ImagePrompt) -> TextToImageSpec:
        """把 LLM 产出的单条提示词映射为文生图输入规格。"""
        return TextToImageSpec(
            model=DEFAULT_IMAGE_MODEL,
            prompt=item.prompt,
            negative_prompt=item.negative_prompt or None,
            width=_IMAGE_WIDTH,
            height=_IMAGE_HEIGHT,
        )
