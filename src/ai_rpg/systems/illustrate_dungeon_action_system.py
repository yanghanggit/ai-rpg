from typing import Final, List, final, override
from pathlib import Path
from loguru import logger
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import IllustrateDungeonAction, Dungeon, DungeonRoom
from ..game.tcg_game import TCGGame
from ..game.config import DUNGEONS_DIR
from ..image_client.client import ImageClient


####################################################################################################################################
# 图片生成规格常量
_IMAGE_WIDTH: Final[int] = 768
_IMAGE_HEIGHT: Final[int] = 1344
_IMAGE_MODEL: Final[str] = "nano-banana"

# 通用负面提示词（封面与房间共用基础部分）
_IMAGE_NEGATIVE_BASE: Final[str] = (
    "人脸，人脸特写，3D渲染，照片写实，高清，抗锯齿，平滑，模糊，渐变，油画，水彩，"
    "文字，汉字，英文字母，UI界面，框架，边框，天空，蓝天，云层，户外，外部景色，现代元素，"
    "bird's eye view，overhead view，top-down view，isometric view，aerial perspective，"
    "俯瞰视角，鸟瞰图，等轴测视角，留白过多"
)

# 房间插图额外负面提示词（排除多余角色）
_IMAGE_NEGATIVE_STAGE: Final[str] = (
    _IMAGE_NEGATIVE_BASE
    + "，多个角色，多个人物，玩家角色，猎人角色，额外人物，crowds，multiple characters"
)


####################################################################################################################################
def _detect_scene_type(profile: str) -> str:
    """根据场景描述推断场景类型（室内/室外）。

    通过关键词匹配判断是否为封闭洞穴类场景。

    Args:
        profile: 场景感官环境描写文本

    Returns:
        'indoor' 表示封闭洞穴场景，'outdoor' 表示开阔场景
    """
    indoor_keywords = ["顶", "穴", "洞", "廊", "坑", "岩", "壁", "石", "缝", "隙", "巢"]
    for keyword in indoor_keywords:
        if keyword in profile:
            return "indoor"
    return "outdoor"


####################################################################################################################################
def _build_dungeon_cover_image_prompt(dungeon_name: str, ecology: str) -> str:
    """构建地下城封面图片生成提示词（7+1段式，无怪物）。

    Args:
        dungeon_name: 地下城全名
        ecology: 地下城整体生态描述

    Returns:
        适合像素艺术风格洞穴场景的封面提示词
    """
    return (
        "pixel art style，side view，2D game scene illustration，"
        "dark cave dungeon entrance，"
        f"{ecology}，"
        "atmospheric depth，layered rock formations，"
        "bioluminescent minerals glowing faintly，"
        "damp stone floor with scattered debris，"
        "dramatic shadow and dim light contrast，"
        "mysterious and foreboding atmosphere，"
        "no characters，no figures，environment only，"
        f"dungeon named {dungeon_name}"
    )


####################################################################################################################################
def _build_room_image_prompt(dungeon_name: str, ecology: str, room: DungeonRoom) -> str:
    """构建地下城房间战斗插图生成提示词（7+1段式，第5段插入怪物外观）。

    Args:
        dungeon_name: 地下城全名
        ecology: 地下城整体生态描述
        room: 已填充 stage/actor 数据的地下城房间

    Returns:
        包含场景环境与怪物形象的战斗插图提示词
    """
    profile = room.stage.stage_profile.profile
    base_body = (
        room.stage.actors[0].character_sheet.base_body if room.stage.actors else ""
    )
    scene_type = _detect_scene_type(profile)
    cave_tag = "enclosed cave tunnel" if scene_type == "indoor" else "open cave chamber"

    return (
        "pixel art style，side view，2D game battle scene illustration，"
        f"{cave_tag}，"
        f"{profile}，"
        f"{ecology}，"
        "dramatic shadow and dim light contrast，"
        "atmospheric depth，layered rock formations，"
        f"{base_body}，"
        "single creature in mid-ground，facing left，combat ready pose，"
        "mysterious and dangerous atmosphere，"
        f"dungeon stage {room.stage.name} in {dungeon_name}"
    )


####################################################################################################################################
@final
class IllustrateDungeonActionSystem(ReactiveProcessor):
    """地下城图片生成系统（Step 5）。

    反应式处理器，监听 IllustrateDungeonAction 的添加事件，从磁盘读取
    Dungeon JSON，并发生成封面与各房间插图，将结果写入 GeneratedImage
    字段后重新保存 dungeon 文件。

    工作流程：
        1. 监听 IllustrateDungeonAction 添加事件
        2. 从 DUNGEONS_DIR/{dungeon_name}.json 加载 Dungeon
        3. 并发生成封面图（1张）+ 各房间插图（N张）
        4. 将 local_path/prompt/model 写入 dungeon.image / room.image
        5. 将更新后的 dungeon 重新保存到磁盘
        6. 动作由 ActionCleanupSystem 自动清除

    Attributes:
        _game: 游戏实例引用

    Note:
        - IllustrateDungeonAction 由 GenerateDungeonActionSystem 在文本数据生成成功后添加
        - 若 dungeon 文件不存在或解析失败，静默 return（不中断流程）
    """

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {
            Matcher(IllustrateDungeonAction): GroupEvent.ADDED,
        }

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(IllustrateDungeonAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        logger.debug(
            f"[IllustrateDungeonActionSystem] react: 收到 IllustrateDungeonAction 事件，准备生成图片，entities count={len(entities)}"
        )
        # for entity in entities:
        #     await self._generate_images(entity)

    ####################################################################################################################################
    async def _generate_images(self, entity: Entity) -> None:
        """为实体触发的地下城执行图片并发生成。

        从磁盘加载 Dungeon，生成封面 + 各房间插图，
        写入 GeneratedImage 字段后重新保存 dungeon 文件。

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

        # 封面客户端（index 0）
        cover_prompt = _build_dungeon_cover_image_prompt(
            dungeon_name=dungeon.name,
            ecology=dungeon.ecology,
        )
        cover_client = ImageClient(
            name=f"{dungeon.name}.cover",
            prompt=cover_prompt,
            negative_prompt=_IMAGE_NEGATIVE_BASE,
            width=_IMAGE_WIDTH,
            height=_IMAGE_HEIGHT,
            model=_IMAGE_MODEL,
        )

        # 每个房间各一个客户端（index 1..N）
        room_prompts: List[str] = [
            _build_room_image_prompt(
                dungeon_name=dungeon.name,
                ecology=dungeon.ecology,
                room=room,
            )
            for room in dungeon.rooms
        ]
        room_clients: List[ImageClient] = [
            ImageClient(
                name=f"{room.stage.name}.illustration",
                prompt=prompt,
                negative_prompt=_IMAGE_NEGATIVE_STAGE,
                width=_IMAGE_WIDTH,
                height=_IMAGE_HEIGHT,
                model=_IMAGE_MODEL,
            )
            for room, prompt in zip(dungeon.rooms, room_prompts)
        ]

        all_clients: List[ImageClient] = [cover_client] + room_clients
        await ImageClient.batch_generate(all_clients)

        # 写入封面 GeneratedImage（直接赋值 response 对象，保留全部字段）
        if cover_client.response.images:
            dungeon.image = cover_client.response.images[0]
            logger.info(
                f"[IllustrateDungeonActionSystem][Step 5] 封面图片生成完成: {dungeon.image.local_path}"
            )
        else:
            logger.warning(
                f"[IllustrateDungeonActionSystem][Step 5] 封面图片生成失败: {dungeon.name}"
            )

        # 写入各房间 GeneratedImage（直接赋值 response 对象，保留全部字段）
        for room, client in zip(dungeon.rooms, room_clients):
            if client.response.images:
                room.image = client.response.images[0]
                logger.info(
                    f"[IllustrateDungeonActionSystem][Step 5] 房间插图生成完成: "
                    f"{room.stage.name} -> {room.image.local_path}"
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
