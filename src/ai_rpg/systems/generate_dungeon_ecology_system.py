"""地下城生态环境生成系统"""

from pathlib import Path
from typing import Dict, Final, List, final, override
from loguru import logger
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.config import DUNGEON_PROCESS_DIR
from ..game.tcg_game import TCGGame
from ..models import (
    DungeonGenerationComponent,
    GenerateDungeonAction,
    GenerateDungeonStagesAction,
    WorldComponent,
)
from ..utils import extract_json_from_code_block


####################################################################################################################################
def _build_dungeon_ecology_prompt() -> str:
    """构建地下城生态环境生成提示词。

    无需任何种子数据，完全由世界观框架驱动创作。
    世界观已通过调用方的 SystemMessage 提供给 LLM。
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
  "ecology": "...",
  "stage_count": 2
}}
```

- **stage_count**：该地下城应包含的战斗场景数量，依地形规模与层次丰富程度从 2 至 3 中选择。

严格按 JSON 格式输出，不要添加其他内容。"""


####################################################################################################################################
class _DungeonEcologyResponse(BaseModel):
    """LLM 返回的地下城生态环境 JSON 解析模型。"""

    name: str = ""
    ecology: str = ""
    stage_count: int = 2


####################################################################################################################################
class DungeonEcologyFile(BaseModel):
    """Step 1 中间文件数据模型，写入 _step1_ecology.json。"""

    dungeon_name: str = ""
    ecology: str = ""
    stage_count: int = 2


####################################################################################################################################
@final
class GenerateDungeonEcologySystem(ReactiveProcessor):
    """地下城生态环境生成系统

    Note:
        - GenerateDungeonAction 由 home_actions.activate_generate_dungeon() 在家园状态下添加
    """

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(GenerateDungeonAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(GenerateDungeonAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        world_system_entities = self._game.get_group(
            Matcher(all_of=[WorldComponent, DungeonGenerationComponent])
        ).entities.copy()

        if not world_system_entities:
            logger.error(
                "[GenerateDungeonEcologySystem] 未找到地下城生成系统实体，Step 1 中止"
            )
            return

        assert len(world_system_entities) == 1, "存在多个地下城生成系统实体，数据异常"
        world_system_entity = next(iter(world_system_entities))

        assert len(entities) == 1, "同时存在多个 GenerateDungeonAction，数据异常"
        entity = entities[0]

        await self._run(entity, world_system_entity)

    ####################################################################################################################################
    async def _run(self, entity: Entity, world_system_entity: Entity) -> None:
        logger.info(f"[GenerateDungeonEcologySystem] Step 1 开始: entity={entity.name}")

        chat_client = DeepSeekClient(
            name=world_system_entity.name,
            prompt=_build_dungeon_ecology_prompt(),
            context=self._game.get_agent_context(world_system_entity).context,
        )
        await chat_client.chat()

        try:
            response = _DungeonEcologyResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )
        except Exception as e:
            logger.error(
                f"[GenerateDungeonEcologySystem] Step 1 解析失败: {e}\n"
                f"原始内容:\n{chat_client.response_content}"
            )
            return

        ecology_file = DungeonEcologyFile(
            dungeon_name=response.name,
            ecology=response.ecology,
            stage_count=response.stage_count,
        )
        file_path: Path = DUNGEON_PROCESS_DIR / f"{response.name}_step1_ecology.json"
        file_path.write_text(ecology_file.model_dump_json(indent=4), encoding="utf-8")

        logger.info(
            f"[GenerateDungeonEcologySystem] Step 1 完成:\n"
            f"  dungeon_name: {response.name}\n"
            f"  ecology:      {response.ecology}\n"
            f"  → {file_path}"
        )

        entity.replace(GenerateDungeonStagesAction, entity.name, response.name)
        logger.info(
            f"[GenerateDungeonEcologySystem] 添加 GenerateDungeonStagesAction: dungeon={response.name}"
        )
