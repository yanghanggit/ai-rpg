import json
from typing import Final, final, override
from loguru import logger
from ..chat_client.client import ChatClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    WorldComponent,
    DungeonGenerationComponent,
    SetupDungeonAction,
)
from ..game.tcg_game import TCGGame
from ..utils import extract_json_from_code_block


####################################################################################################################################
def _build_dungeon_ecology_prompt() -> str:
    """构建地下城生态环境生成提示词。

    无需任何种子数据，完全由世界观框架驱动创作。
    世界观已通过调用方的 SystemMessage 提供给 LLM。

    Returns:
        要求 LLM 创作地下城 name 与 ecology 的提示词
    """
    return """# 任务：创作一个地下城的生态环境

请在当前世界观框架内，为一处自然地点生成名称与生态环境描写。

## 要求

- **name**：地下城全名，采用「地下城.XXXX」命名格式，体现地貌特征
- **ecology**：该地点的生态环境写照，100-200字，只描述「这里有什么」：
  - 地形结构与光照、温湿度等感官细节
  - 植被、土质、水文等自然要素
  - 动物活动留下的痕迹（足迹、爪痕、粪便、巢穴碎片、骨骸），不直接点名生物
  - 气味、声音等环境线索
  - 禁忌：不出现生物名称、不叙述故事、不描写角色行为、不使用「威胁」「挑战」「危险」等评价性词汇

## 输出格式

```json
{{
  "name": "地下城.XXX",
  "ecology": "..."
}}
```

严格按 JSON 格式输出，不要添加其他内容。"""


####################################################################################################################################
def _parse_dungeon_ecology(content: str) -> tuple[str, str]:
    """解析 LLM 返回的地下城生态环境 JSON。

    Args:
        content: LLM 响应的原始文本

    Returns:
        (name, ecology) 元组；解析失败时返回 ("", "")
    """
    try:
        json_str = extract_json_from_code_block(content)
        data = json.loads(json_str)
        name = data.get("name", "")
        ecology = data.get("ecology", "")
        return name, ecology
    except Exception as e:
        logger.error(
            f"[DungeonGenerationSystem] 解析地下城生态环境失败: {e}\n原始内容:\n{content}"
        )
        return "", ""


####################################################################################################################################
@final
class DungeonGenerationSystem(ReactiveProcessor):
    """地下城图片生成系统。

    反应式处理器，监听实体上 SetupDungeonAction 的添加事件，
    执行地下城的完整创建流程（文生图、数据初始化等）。

    工作流程：
        1. 监听实体上 SetupDungeonAction 动作组件的添加事件
        2. 获取地下城生成世界系统实体（包含 DungeonGenerationComponent）
        3. 依次执行地下城创建子任务（文生图、数据初始化等）
        4. 由 ActionCleanupSystem 自动清除 SetupDungeonAction

    Attributes:
        _game: 游戏实例引用

    Note:
        - SetupDungeonAction 由 home_actions.activate_setup_dungeon() 在家园状态下添加
        - 具体创建逻辑待后续填充，当前为骨架占位
    """

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        # 监听 SetupDungeonAction 的添加事件
        return {
            Matcher(SetupDungeonAction): GroupEvent.ADDED,
        }

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(SetupDungeonAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:

        # 获取地下城生成世界系统实体
        world_system_entities = self._game.get_group(
            Matcher(all_of=[WorldComponent, DungeonGenerationComponent])
        ).entities.copy()

        if not world_system_entities:
            logger.error("未找到地下城生成系统实体，无法执行地下城创建流程")
            return

        assert len(world_system_entities) == 1, "存在多个地下城生成系统实体，数据异常"
        world_system_entity = next(iter(world_system_entities))

        for entity in entities:
            await self._setup_dungeon(entity, world_system_entity)

    ####################################################################################################################################
    async def _setup_dungeon(self, entity: Entity, world_system_entity: Entity) -> None:
        """执行地下城创建流程（第一步：生成地下城概念）。

        Args:
            entity: 携带 SetupDungeonAction 的实体（玩家实体）
            world_system_entity: 地下城生成世界系统实体（其 SystemMessage 已含世界观）
        """
        logger.info(
            f"[DungeonGenerationSystem] 开始地下城概念生成: entity={entity.name}"
        )

        # Step 1: 调用 LLM 生成地下城 name + ecology
        chat_client = ChatClient(
            name=world_system_entity.name,
            prompt=_build_dungeon_ecology_prompt(),
            context=self._game.get_agent_context(world_system_entity).context,
        )
        await chat_client.async_chat()

        # Step 2: 解析结果
        dungeon_name, dungeon_ecology = _parse_dungeon_ecology(
            chat_client.response_content
        )

        logger.info(
            f"[DungeonGenerationSystem] 地下城生态环境生成完成:\n"
            f"  name: {dungeon_name}\n"
            f"  ecology: {dungeon_ecology}"
        )

    ####################################################################################################################################
