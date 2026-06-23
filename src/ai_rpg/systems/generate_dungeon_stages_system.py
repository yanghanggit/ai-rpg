"""地下城场景生成系统"""

from pathlib import Path
from typing import Any, Dict, Final, List, final, override
from loguru import logger
from pydantic import BaseModel
from ..deepseek import agent_loop, ToolDefinition, ToolFunction
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.config import DUNGEON_PROCESS_DIR
from ..game.tcg_game import TCGGame
from ..models import (
    DungeonGenerationComponent,
    GenerateDungeonActorsAction,
    GenerateDungeonStagesAction,
    WorldComponent,
)
from .generate_dungeon_ecology_system import DungeonEcologyFile


# _MAX_ROUNDS: Final[int] = 5


####################################################################################################################################
_READ_STAGES_FILE_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="read_stages_file",
        description="读取已写入磁盘的地下城场景中间文件，返回其 JSON 内容。",
        parameters={
            "type": "object",
            "properties": {
                "dungeon_name": {
                    "type": "string",
                    "description": "地下城全名，与 record_dungeon_stages 中填写的 dungeon_name 字段一致",
                },
            },
            "required": ["dungeon_name"],
        },
    )
)


####################################################################################################################################
def _build_stages_tool(stage_count: int) -> ToolDefinition:
    """动态构建 record_dungeon_stages 工具定义，将 minItems/maxItems 约束绑定到 stage_count。"""
    return ToolDefinition(
        function=ToolFunction(
            name="record_dungeon_stages",
            description=f"记录地下城全部 {stage_count} 个战斗场景的名称、英文标识、环境描写与生物种类数量。",
            parameters={
                "type": "object",
                "properties": {
                    "dungeon_name": {
                        "type": "string",
                        "description": "地下城全名，与 Step 1 ecology 文件中的 dungeon_name 一致",
                    },
                    "stages": {
                        "type": "array",
                        "minItems": stage_count,
                        "maxItems": stage_count,
                        "items": {
                            "type": "object",
                            "properties": {
                                "stage_name": {
                                    "type": "string",
                                    "description": "场景全名，采用「场景.XXXX」命名格式，体现该局部区域的地貌特征，所有场景名称不重复",
                                },
                                "profile_name": {
                                    "type": "string",
                                    "description": "场景英文标识，snake_case 格式（如 forest_edge、deep_pool），所有标识不重复",
                                },
                                "profile": {
                                    "type": "string",
                                    "description": "该场景的感官环境描写，50-100字，只描述「这里有什么」，禁止出现生物名称及威胁评价性词汇",
                                },
                                "actor_count": {
                                    "type": "integer",
                                    "enum": [1, 2],
                                    "description": "该场景内栖居生物的种类数量；入口区域为 1，深处场景可为 2",
                                },
                            },
                            "required": [
                                "stage_name",
                                "profile_name",
                                "profile",
                                "actor_count",
                            ],
                        },
                    },
                },
                "required": ["dungeon_name", "stages"],
            },
        )
    )


####################################################################################################################################
def _build_dungeon_stages_prompt(
    dungeon_name: str, ecology: str, total_stages: int
) -> str:
    return f"""# 任务：为地下城创作 {total_stages} 个战斗场景

## 地下城信息

- **地下城名称**：{dungeon_name}
- **整体生态**：{ecology}

## 场景顺序说明

按从入口到最深处的顺序排列，共 {total_stages} 个场景：
- 第 1 个：入口区域，相对开阔，生物活动痕迹疏散
- 第 {total_stages} 个：最深处，空间压迫，生物活动痕迹密集且强烈
- 中间场景：深度与复杂度介于入口与深处之间，逐步递进

## 每个场景的 profile 描写要求

只描述「这里有什么」，聚焦感官层面：
- 地形结构、光照、温湿度等直观感受
- 地面材质、植被或水体等自然要素
- 动物活动留下的痕迹（足迹、爪痕、巢穴残迹、骨骸），不直接点名生物
- 气味或声音等感官线索

工作流程：调用 record_dungeon_stages 写入全部场景数据，确认无误后结束本次对话。
如需核查已写入内容，可先调用 read_stages_file，再决定是否结束。"""


####################################################################################################################################
class _DungeonStageResponse(BaseModel):
    stage_name: str = ""
    profile_name: str = ""
    profile: str = ""
    actor_count: int = 1


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

        stages_file: DungeonStagesFile | None = None

        def _handle_record_dungeon_stages(dungeon_name: str, stages: List[Any]) -> str:
            nonlocal stages_file
            stage_responses = [_DungeonStageResponse(**s) for s in stages]
            stages_file = DungeonStagesFile(
                dungeon_name=dungeon_name,
                ecology=ecology_file.ecology,
                stage_responses=stage_responses,
            )
            file_path: Path = DUNGEON_PROCESS_DIR / f"{dungeon_name}_step2_stages.json"
            file_path.write_text(
                stages_file.model_dump_json(indent=4), encoding="utf-8"
            )
            for i, stage in enumerate(stage_responses, start=1):
                logger.info(
                    f"[GenerateDungeonStagesSystem] Stage {i}/{len(stage_responses)}:\n"
                    f"  stage_name:   {stage.stage_name}\n"
                    f"  profile_name: {stage.profile_name}\n"
                    f"  profile:      {stage.profile}"
                )
            logger.info(
                f"[GenerateDungeonStagesSystem] record_dungeon_stages 执行:\n"
                f"  dungeon_name: {dungeon_name}\n"
                f"  stage_count:  {len(stage_responses)}\n"
                f"  → {file_path}"
            )
            return (
                f"已记录地下城「{dungeon_name}」的 {len(stage_responses)} 个场景。"
                f"中间文件已写入: {file_path}"
            )

        def _handle_read_stages_file(dungeon_name: str) -> str:
            file_path: Path = DUNGEON_PROCESS_DIR / f"{dungeon_name}_step2_stages.json"
            if not file_path.exists():
                return f"错误：文件不存在 {file_path}"
            return file_path.read_text(encoding="utf-8")

        success = await agent_loop(
            name=world_system_entity.name,
            prompt=_build_dungeon_stages_prompt(
                dungeon_name=ecology_file.dungeon_name,
                ecology=ecology_file.ecology,
                total_stages=ecology_file.stage_count,
            ),
            context=self._game.get_agent_context(world_system_entity).context,
            tools=[
                _build_stages_tool(ecology_file.stage_count),
                _READ_STAGES_FILE_TOOL,
            ],
            handlers={
                "record_dungeon_stages": _handle_record_dungeon_stages,
                "read_stages_file": _handle_read_stages_file,
            },
            max_rounds=5,
        )

        if not success:
            logger.error("[GenerateDungeonStagesSystem] Step 2 agent_loop 失败，中止")
            return

        if stages_file is None:
            logger.error(
                "[GenerateDungeonStagesSystem] Step 2 LLM 已 stop "
                "但未调用 record_dungeon_stages，中止"
            )
            return

        logger.info(
            f"[GenerateDungeonStagesSystem] Step 2 完成:\n"
            f"  stages ({len(stages_file.stage_responses)}): "
            + ", ".join(s.stage_name for s in stages_file.stage_responses)
            + f"\n  → {DUNGEON_PROCESS_DIR / f'{dungeon_name}_step2_stages.json'}"
        )

        entity.replace(GenerateDungeonActorsAction, entity.name, dungeon_name)
        logger.info(
            f"[GenerateDungeonStagesSystem] 添加 GenerateDungeonActorsAction: dungeon={dungeon_name}"
        )
