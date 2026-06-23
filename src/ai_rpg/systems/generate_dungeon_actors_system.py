"""地下城怪物生成系统"""

from pathlib import Path
from typing import Dict, Final, List, final, override

from loguru import logger
from pydantic import BaseModel

from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.config import DUNGEON_PROCESS_DIR
from ..game.tcg_game import TCGGame
from ..models import (
    AssembleDungeonAction,
    DungeonGenerationComponent,
    GenerateDungeonActorsAction,
    WorldComponent,
)
from ..utils import extract_json_from_code_block
from .generate_dungeon_stages_system import DungeonStagesFile


####################################################################################################################################
def _build_dungeon_actor_prompt(
    dungeon_name: str, ecology: str, stage_name: str, stage_profile: str
) -> str:
    return f"""# 任务：为场景创作一个栖居怪物的设定

## 所在地下城

- **地下城名称**：{dungeon_name}
- **整体生态**：{ecology}

## 当前场景

- **场景名称**：{stage_name}
- **场景环境**：{stage_profile}

## 要求

- **actor_name**：角色全名，采用「常物/精怪/大妖.XXXX」格式，XXXX 体现该生物的特征
- **character_sheet_name**：角色英文标识，snake_case 格式（如 `bone_crawler`、`mist_spirit`）
- **profile**：第一人称 AI 扮演描述，50-100字，描述该生物的性格、行为倾向、与环境的关系
  - 禁忌：不出现战斗数值、技能名称、等级等游戏机制词汇
- **base_body**：第三人称外观描述，30-60字，描述该生物的形态、材质、动态特征
  - 禁忌：不出现战斗数值、技能名称、等级等游戏机制词汇

## 输出格式

```json
{{
  "actor_name": "怪物.XXX",
  "character_sheet_name": "snake_case_name",
  "profile": "...",
  "base_body": "..."
}}
```

严格按 JSON 格式输出，不要添加其他内容。"""


####################################################################################################################################
class _DungeonActorResponse(BaseModel):
    actor_name: str = ""
    character_sheet_name: str = ""
    profile: str = ""
    base_body: str = ""


####################################################################################################################################
class DungeonActorBlueprint(BaseModel):
    """地下城怪物实体创建所需的原始字段。供 assemble_dungeon_system 导入。"""

    actor_name: str = ""
    character_sheet_name: str = ""
    profile: str = ""
    base_body: str = ""


####################################################################################################################################
class DungeonStageBlueprint(BaseModel):
    """地下城单个场景实体创建所需的原始字段（包含配对的怪物蓝图）。供 assemble_dungeon_system 导入。"""

    stage_name: str = ""
    profile_name: str = ""
    profile: str = ""
    actor: DungeonActorBlueprint = DungeonActorBlueprint()
    image_url: str = ""


####################################################################################################################################
class DungeonBlueprint(BaseModel):
    """地下城完整蓝图，承载 Steps 1-3 的全部产出。供 assemble_dungeon_system 导入。

    Attributes:
        dungeon_name: 地下城全名，格式为「地下城.XXXX」
        ecology: 地下城整体生态环境描述
        stages: 已完整配对（场景+怪物）的场景蓝图列表
        image_url: 封面图片 URL，Step 3 写入时为空，由 IllustrateDungeonActionSystem 填充
    """

    dungeon_name: str = ""
    ecology: str = ""
    stages: List[DungeonStageBlueprint] = []
    image_url: str = ""


####################################################################################################################################
@final
class GenerateDungeonActorsSystem(ReactiveProcessor):
    """地下城怪物生成系统"""

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(GenerateDungeonActorsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(GenerateDungeonActorsAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        world_system_entities = self._game.get_group(
            Matcher(all_of=[WorldComponent, DungeonGenerationComponent])
        ).entities.copy()

        if not world_system_entities:
            logger.error(
                "[GenerateDungeonActorsSystem] 未找到地下城生成系统实体，Step 3 中止"
            )
            return

        assert len(world_system_entities) == 1, "存在多个地下城生成系统实体，数据异常"
        world_system_entity = next(iter(world_system_entities))

        assert len(entities) == 1, "同时存在多个 GenerateDungeonActorsAction，数据异常"
        entity = entities[0]

        await self._run(entity, world_system_entity)

    ####################################################################################################################################
    async def _run(self, entity: Entity, world_system_entity: Entity) -> None:
        action_comp = entity.get(GenerateDungeonActorsAction)
        dungeon_name = action_comp.dungeon_name

        logger.info(
            f"[GenerateDungeonActorsSystem] Step 3 开始: dungeon={dungeon_name}"
        )

        # 读取 Step 2 中间文件
        stages_file_path: Path = (
            DUNGEON_PROCESS_DIR / f"{dungeon_name}_step2_stages.json"
        )
        try:
            stages_file = DungeonStagesFile.model_validate_json(
                stages_file_path.read_text(encoding="utf-8")
            )
        except Exception as e:
            logger.error(
                f"[GenerateDungeonActorsSystem] 读取 Step 2 文件失败: {e}\n"
                f"  path: {stages_file_path}"
            )
            return

        if not stages_file.stage_responses:
            logger.error(
                f"[GenerateDungeonActorsSystem] Step 2 文件中 stage_responses 为空: {stages_file_path}"
            )
            return

        context = self._game.get_agent_context(world_system_entity).context
        clients: List[DeepSeekClient] = [
            DeepSeekClient(
                name=stage.stage_name,
                prompt=_build_dungeon_actor_prompt(
                    dungeon_name=stages_file.dungeon_name,
                    ecology=stages_file.ecology,
                    stage_name=stage.stage_name,
                    stage_profile=stage.profile,
                ),
                context=context,
            )
            for stage in stages_file.stage_responses
        ]

        await DeepSeekClient.batch_chat(clients)

        # 组装 DungeonBlueprint
        blueprint = DungeonBlueprint(
            dungeon_name=stages_file.dungeon_name,
            ecology=stages_file.ecology,
        )

        for i, (client, stage) in enumerate(
            zip(clients, stages_file.stage_responses), start=1
        ):
            try:
                actor_response = _DungeonActorResponse.model_validate_json(
                    extract_json_from_code_block(client.response_content)
                )
            except Exception as e:
                logger.error(
                    f"[GenerateDungeonActorsSystem] Stage '{stage.stage_name}' 解析怪物失败，该场景不纳入 blueprint: {e}\n"
                    f"原始内容:\n{client.response_content}"
                )
                continue

            stage_bp = DungeonStageBlueprint(
                stage_name=stage.stage_name,
                profile_name=stage.profile_name,
                profile=stage.profile,
                actor=DungeonActorBlueprint(
                    actor_name=actor_response.actor_name,
                    character_sheet_name=actor_response.character_sheet_name,
                    profile=actor_response.profile,
                    base_body=actor_response.base_body,
                ),
            )
            blueprint.stages.append(stage_bp)
            logger.info(
                f"[GenerateDungeonActorsSystem] Stage+Actor {i}/{len(stages_file.stage_responses)} 写入 blueprint:\n"
                f"  stage_name:           {stage_bp.stage_name}\n"
                f"  profile_name:         {stage_bp.profile_name}\n"
                f"  actor_name:           {stage_bp.actor.actor_name}\n"
                f"  character_sheet_name: {stage_bp.actor.character_sheet_name}"
            )

        if not blueprint.stages:
            logger.error(
                "[GenerateDungeonActorsSystem] 所有场景怪物解析均失败，blueprint.stages 为空，Step 3 中止"
            )
            return

        # 写入 Step 3 中间文件
        file_path: Path = DUNGEON_PROCESS_DIR / f"{dungeon_name}_step3_blueprint.json"
        file_path.write_text(blueprint.model_dump_json(indent=4), encoding="utf-8")

        logger.info(
            f"[GenerateDungeonActorsSystem] Step 3 完成:\n"
            f"  dungeon_name: {blueprint.dungeon_name}\n"
            f"  stages ({len(blueprint.stages)}): "
            + ", ".join(
                f"{s.stage_name}({s.actor.actor_name})" for s in blueprint.stages
            )
            + f"\n  → {file_path}"
        )

        entity.replace(AssembleDungeonAction, entity.name, dungeon_name)
        logger.info(
            f"[GenerateDungeonActorsSystem] 添加 AssembleDungeonAction: dungeon={dungeon_name}"
        )
