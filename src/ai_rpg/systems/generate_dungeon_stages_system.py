"""地下城场景生成系统"""

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
    GenerateDungeonActorsAction,
    GenerateDungeonStagesAction,
    WorldComponent,
)
from ..utils import extract_json_from_code_block
from .generate_dungeon_ecology_system import DungeonEcologyFile

####################################################################################################################################
# 每次地下城生成的场景数量
_STAGE_COUNT: Final[int] = 2


####################################################################################################################################
def _build_dungeon_stages_prompt(
    dungeon_name: str, ecology: str, total_stages: int
) -> str:
    return f"""# 任务：为地下城一次性创作 {total_stages} 个战斗场景

## 地下城信息

- **地下城名称**：{dungeon_name}
- **整体生态**：{ecology}

## 场景顺序说明

按从入口到最深处的顺序排列，共 {total_stages} 个场景：
- 第 1 个：入口区域，相对开阔，生物活动痕迹疏散
- 第 {total_stages} 个：最深处，空间压迫，生物活动痕迹密集且强烈
- 中间场景：深度与复杂度介于入口与深处之间，逐步递进

## 每个场景的要求

- **stage_name**：场景全名，采用「场景.XXXX」命名格式，体现该局部区域的地貌特征，所有场景名称不重复
- **profile_name**：场景英文标识，snake_case 格式（如 `forest_edge`、`deep_pool`），所有标识不重复
- **profile**：该场景的感官环境描写，50-100字，只描述「这里有什么」：
  - 地形结构、光照、温湿度等直观感受
  - 地面材质、植被或水体等自然要素
  - 动物活动留下的痕迹（足迹、爪痕、巢穴残迹、骨骸），不直接点名生物
  - 气味或声音等感官线索
  - 禁忌：不出现生物名称、不叙述故事、不描写角色行为、不使用「威胁」「挑战」「危险」等评价性词汇

## 输出格式

```json
{{
  "stages": [
    {{
      "stage_name": "场景.XXX",
      "profile_name": "snake_case_name",
      "profile": "..."
    }}
  ]
}}
```

严格按 JSON 格式输出，stages 数组中包含恰好 {total_stages} 个元素，不要添加其他内容。"""


####################################################################################################################################
class _DungeonStageResponse(BaseModel):
    stage_name: str = ""
    profile_name: str = ""
    profile: str = ""


####################################################################################################################################
class _DungeonStagesResponse(BaseModel):
    stages: List[_DungeonStageResponse] = []


####################################################################################################################################
class DungeonStagesFile(BaseModel):
    """Step 2 中间文件数据模型，写入 _step2_stages.json。"""

    dungeon_name: str = ""
    ecology: str = ""
    stage_responses: List[_DungeonStageResponse] = []


####################################################################################################################################
@final
class GenerateDungeonStagesSystem(ReactiveProcessor):
    """地下城场景生成系统"""

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(GenerateDungeonStagesAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(GenerateDungeonStagesAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        world_system_entities = self._game.get_group(
            Matcher(all_of=[WorldComponent, DungeonGenerationComponent])
        ).entities.copy()

        if not world_system_entities:
            logger.error(
                "[GenerateDungeonStagesSystem] 未找到地下城生成系统实体，Step 2 中止"
            )
            return

        assert len(world_system_entities) == 1, "存在多个地下城生成系统实体，数据异常"
        world_system_entity = next(iter(world_system_entities))

        assert len(entities) == 1, "同时存在多个 GenerateDungeonStagesAction，数据异常"
        entity = entities[0]

        await self._run(entity, world_system_entity)

    ####################################################################################################################################
    async def _run(self, entity: Entity, world_system_entity: Entity) -> None:
        action_comp = entity.get(GenerateDungeonStagesAction)
        dungeon_name = action_comp.dungeon_name

        logger.info(
            f"[GenerateDungeonStagesSystem] Step 2 开始: dungeon={dungeon_name}"
        )

        # 读取 Step 1 中间文件
        ecology_file_path: Path = (
            DUNGEON_PROCESS_DIR / f"{dungeon_name}_step1_ecology.json"
        )
        try:
            ecology_file = DungeonEcologyFile.model_validate_json(
                ecology_file_path.read_text(encoding="utf-8")
            )
        except Exception as e:
            logger.error(
                f"[GenerateDungeonStagesSystem] 读取 Step 1 文件失败: {e}\n"
                f"  path: {ecology_file_path}"
            )
            return

        # 调用 LLM 批量生成场景设定
        chat_client = DeepSeekClient(
            name=world_system_entity.name,
            prompt=_build_dungeon_stages_prompt(
                dungeon_name=ecology_file.dungeon_name,
                ecology=ecology_file.ecology,
                total_stages=_STAGE_COUNT,
            ),
            context=self._game.get_agent_context(world_system_entity).context,
        )
        await chat_client.chat()

        try:
            stages_response = _DungeonStagesResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )
        except Exception as e:
            logger.error(
                f"[GenerateDungeonStagesSystem] Step 2 解析失败: {e}\n"
                f"原始内容:\n{chat_client.response_content}"
            )
            return

        for i, stage in enumerate(stages_response.stages, start=1):
            logger.info(
                f"[GenerateDungeonStagesSystem] Stage {i}/{len(stages_response.stages)} 解析完成:\n"
                f"  stage_name:   {stage.stage_name}\n"
                f"  profile_name: {stage.profile_name}\n"
                f"  profile:      {stage.profile}"
            )

        # 写入 Step 2 中间文件
        stages_file = DungeonStagesFile(
            dungeon_name=ecology_file.dungeon_name,
            ecology=ecology_file.ecology,
            stage_responses=stages_response.stages,
        )
        file_path: Path = DUNGEON_PROCESS_DIR / f"{dungeon_name}_step2_stages.json"
        file_path.write_text(stages_file.model_dump_json(indent=4), encoding="utf-8")

        logger.info(
            f"[GenerateDungeonStagesSystem] Step 2 完成:\n"
            f"  stages ({len(stages_response.stages)}): "
            + ", ".join(s.stage_name for s in stages_response.stages)
            + f"\n  → {file_path}"
        )

        entity.replace(GenerateDungeonActorsAction, entity.name, dungeon_name)
        logger.info(
            f"[GenerateDungeonStagesSystem] 添加 GenerateDungeonActorsAction: dungeon={dungeon_name}"
        )
