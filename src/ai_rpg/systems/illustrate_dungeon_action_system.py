"""副本插图生成系统（Step 5）。

监听 IllustrateDungeonAction 添加事件，并发批量生成副本封面与各房间插图，
把生成的 ImageMeta 写回 ``dungeon.image`` / ``room.image`` 后重新落盘。

数据驱动：视觉风格与负面提示词来自 ``Blueprint.image_style`` /
``Blueprint.image_negative_prompt``（故事层，在 demo/ 注入）；本文件只保留
与故事无关的尺寸、模型与构图约束。
"""

from pathlib import Path
from typing import Dict, Final, List, Optional, final, override

from loguru import logger

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.config import DUNGEONS_DIR
from ..game.dbg_game import DBGGame
from ..models import Dungeon, DungeonRoom, IllustrateDungeonAction, ImageMeta
from ..replicate import TextToImageSpec, batch_text_to_images
from ..utils import prompt_builder


####################################################################################################################################
# 图片生成规格（引擎级：尺寸 / 模型 / 构图，与具体故事无关）
_IMAGE_WIDTH: Final[int] = 1344  # 16:9 横屏（nano-banana 原生宽高比）
_IMAGE_HEIGHT: Final[int] = 768
_IMAGE_MODEL: Final[str] = "nano-banana"

# 引擎级提示词框架
_PROMPT_LEAD: Final[str] = "根据以下场景设定绘制插图"
_COVER_COMPOSITION: Final[str] = (
    "纯环境场景，画面中不出现任何人物、生物或它们的剪影，只呈现空间、陈设与光线"
)
_ROOM_COMPOSITION: Final[str] = (
    "画面中只出现一只生物，位于中景，侧面朝向画面左侧，呈戒备或攻击姿态，环境占据画面主体"
)


####################################################################################################################################
def _compose_prompt(*parts: str) -> str:
    """按非空片段以句号拼接提示词，自动跳过空串。"""
    cleaned = [p.strip().strip("。，,；; ") for p in parts if p and p.strip()]
    return "。".join(cleaned)


####################################################################################################################################
@prompt_builder
def _build_dungeon_cover_image_prompt(image_style: str, profile: str) -> str:
    """构建副本封面提示词（纯环境，无生物）。

    Args:
        image_style: 来自 Blueprint 的全局视觉风格
        profile: 副本整体设定描述

    Returns:
        风格 + 设定 + 纯环境构图的提示词
    """
    return _compose_prompt(_PROMPT_LEAD, image_style, profile, _COVER_COMPOSITION)


####################################################################################################################################
@prompt_builder
def _build_room_image_prompt(
    image_style: str, dungeon_profile: str, room: DungeonRoom
) -> str:
    """构建副本房间插图提示词。

    战斗房注入怪物外观（单只生物构图）；开场房无怪物，退化为纯环境构图。

    Args:
        image_style: 来自 Blueprint 的全局视觉风格
        dungeon_profile: 副本整体设定（用于跨房间视觉一致性）
        room: 已填充 stage / actor 数据的副本房间

    Returns:
        风格 + 副本上下文 + 本房间环境 + 怪物外观 + 构图的提示词
    """
    stage_profile = room.stage.profile
    if room.stage.actors:
        base_body = room.stage.actors[0].base_body
        composition = _ROOM_COMPOSITION
    else:
        base_body = ""
        composition = _COVER_COMPOSITION

    return _compose_prompt(
        _PROMPT_LEAD,
        image_style,
        dungeon_profile,
        stage_profile,
        base_body,
        composition,
    )


####################################################################################################################################
@final
class IllustrateDungeonActionSystem(ReactiveProcessor):
    """副本图片生成系统（Step 5）。

    反应式处理器，监听 IllustrateDungeonAction 的添加事件，从磁盘读取
    Dungeon JSON，并发生成封面与各房间插图，将生成的 ImageMeta 写入
    dungeon.image / room.image 后重新保存 dungeon 文件。

    工作流程：
        1. 监听 IllustrateDungeonAction 添加事件
        2. 从 DUNGEONS_DIR/{dungeon_name}.json 加载 Dungeon
        3. 读取 Blueprint 的视觉风格，并发批量生成封面图（1张）+ 各房间插图（N张）
        4. 将返回的 ImageMeta 写入 dungeon.image / room.image（失败项保持为空）
        5. 将更新后的 dungeon 重新保存到磁盘
        6. 动作由 ActionCleanupSystem 自动清除

    Attributes:
        _game: 游戏实例引用

    Note:
        - IllustrateDungeonAction 由 AssembleDeckSystem（Step 4.5）在写盘后添加
        - 视觉风格/负面提示词来自 Blueprint（故事层），本系统不含具体故事内容
        - 若 dungeon 文件不存在或解析失败，静默 return（不中断流程）
        - 批量失败隔离：单张失败返回 None，不影响其他图片
    """

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {
            Matcher(IllustrateDungeonAction): GroupEvent.ADDED,
        }

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(IllustrateDungeonAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        logger.debug(
            f"[IllustrateDungeonActionSystem] react: 收到 IllustrateDungeonAction 事件，准备生成图片，entities count={len(entities)}"
        )
        for entity in entities:
            # TODO: 这里可以添加对实体的预处理逻辑，例如检查实体状态或准备生成图片的上下文
            logger.debug(f"[IllustrateDungeonActionSystem] react: 处理实体 {entity.name}")
            # await self._generate_images(entity)

    ####################################################################################################################################
    async def _generate_images(self, entity: Entity) -> None:
        """为实体触发的副本执行图片并发生成。

        从磁盘加载 Dungeon，读取 Blueprint 中的视觉风格，生成封面 + 各房间插图，
        写入 ImageMeta 字段后重新保存 dungeon 文件。

        Args:
            entity: 携带 IllustrateDungeonAction 的实体（玩家实体）
        """
        action = entity.get(IllustrateDungeonAction)
        dungeon_path: Path = DUNGEONS_DIR / f"{action.dungeon_name}.json"

        if not dungeon_path.exists():
            logger.error(
                f"[IllustrateDungeonActionSystem] Dungeon 文件不存在: {dungeon_path}"
            )
            return

        try:
            dungeon = Dungeon.model_validate_json(
                dungeon_path.read_text(encoding="utf-8")
            )
        except Exception as e:
            logger.error(
                f"[IllustrateDungeonActionSystem] 解析 Dungeon 失败: {e}\n"
                f"路径: {dungeon_path}"
            )
            return

        # 视觉风格来自故事层（demo/ 注入的 Blueprint），引擎不硬编码画风
        image_style = self._game._world.blueprint.image_style
        image_negative = self._game._world.blueprint.image_negative_prompt

        # 封面任务（index 0）
        cover_spec = TextToImageSpec(
            model=_IMAGE_MODEL,
            prompt=_build_dungeon_cover_image_prompt(
                image_style=image_style,
                profile=dungeon.profile,
            ),
            negative_prompt=image_negative,
            width=_IMAGE_WIDTH,
            height=_IMAGE_HEIGHT,
        )

        # 每个房间各一个任务（index 1..N）
        room_specs: List[TextToImageSpec] = [
            TextToImageSpec(
                model=_IMAGE_MODEL,
                prompt=_build_room_image_prompt(
                    image_style=image_style,
                    dungeon_profile=dungeon.profile,
                    room=room,
                ),
                negative_prompt=image_negative,
                width=_IMAGE_WIDTH,
                height=_IMAGE_HEIGHT,
            )
            for room in dungeon.rooms
        ]

        # 并发批量生成；返回值与 all_specs 顺序一一对应，失败项为 None
        all_specs: List[TextToImageSpec] = [cover_spec] + room_specs
        metas: List[Optional[ImageMeta]] = await batch_text_to_images(specs=all_specs)

        # 写入封面 ImageMeta（完整对象落库，保留全部生成溯源字段）
        cover_meta = metas[0]
        if cover_meta is not None:
            dungeon.image = cover_meta
            logger.info(
                f"[IllustrateDungeonActionSystem][Step 5] 封面图片生成完成: {cover_meta.local_path}"
            )
        else:
            logger.warning(
                f"[IllustrateDungeonActionSystem][Step 5] 封面图片生成失败: {dungeon.name}"
            )

        # 写入各房间 ImageMeta（失败项保持默认为空图）
        for room, meta in zip(dungeon.rooms, metas[1:]):
            if meta is not None:
                room.image = meta
                logger.info(
                    f"[IllustrateDungeonActionSystem][Step 5] 房间插图生成完成: "
                    f"{room.stage.name} -> {meta.local_path}"
                )
            else:
                logger.warning(
                    f"[IllustrateDungeonActionSystem][Step 5] 房间插图生成失败: {room.stage.name}"
                )

        # 将更新后的 dungeon（含 image 数据）重新保存到磁盘
        dungeon_path.write_text(dungeon.model_dump_json(indent=4), encoding="utf-8")
        logger.info(
            f"[IllustrateDungeonActionSystem] Dungeon 已更新（含 image 数据）: {dungeon_path}"
        )
