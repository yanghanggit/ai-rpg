"""地下城生态环境生成系统"""

import json
from pathlib import Path
from typing import Callable, Dict, Final, List, Optional, final, override
from loguru import logger
from pydantic import BaseModel
from ..deepseek import DeepSeekClient, ToolDefinition, ToolFunction
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.config import DUNGEON_PROCESS_DIR
from ..game.tcg_game import TCGGame
from ..models import (
    DungeonGenerationComponent,
    GenerateDungeonAction,
    GenerateDungeonStagesAction,
    WorldComponent,
)
from ..models.messages import BaseMessage, HumanMessage, ToolMessage


####################################################################################################################################
_ECOLOGY_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="record_dungeon_ecology",
        description="记录地下城的名称、生态环境描写与场景数量。",
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "地下城全名，采用「地下城.XXXX」命名格式，体现地貌特征",
                },
                "ecology": {
                    "type": "string",
                    "description": "该地点的生态环境写照，100-200字，只描述「这里有什么」，禁止出现生物名称、威胁评价性词汇",
                },
                "stage_count": {
                    "type": "integer",
                    "enum": [2, 3],
                    "description": "该地下城应包含的战斗场景数量，依地形规模与层次丰富程度选择",
                },
            },
            "required": ["name", "ecology", "stage_count"],
        },
    )
)


####################################################################################################################################
_READ_ECOLOGY_FILE_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="read_ecology_file",
        description="读取已写入磁盘的地下城生态环境中间文件，返回其 JSON 内容。",
        parameters={
            "type": "object",
            "properties": {
                "dungeon_name": {
                    "type": "string",
                    "description": "地下城全名，与 record_dungeon_ecology 中填写的 name 字段一致",
                },
            },
            "required": ["dungeon_name"],
        },
    )
)

_MAX_ROUNDS: Final[int] = 5


####################################################################################################################################
def _build_dungeon_ecology_prompt() -> str:
    """构建地下城生态环境生成提示词。

    无需任何种子数据，完全由世界观框架驱动创作。
    世界观已通过调用方的 SystemMessage 提供给 LLM。
    """
    return """# 任务：创作一个地下城的生态环境

请在当前世界观框架内，为一处自然地点生成名称与生态环境描写。

生态环境描写只描述「这里有什么」，聚焦感官层面：
- 地形结构与光照、温湿度等直观感受
- 植被、土质、水文等自然要素
- 动物活动留下的痕迹（足迹、爪痕、粪便、巢穴碎片、骨骸），不直接点名生物
- 气味、声音等环境线索

工作流程：调用 record_dungeon_ecology 写入生态数据，确认无误后结束本次对话。
如需核查已写入内容，可先调用 read_ecology_file，再决定是否结束。"""


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

        ecology_file: Optional[DungeonEcologyFile] = None

        def _handle_record_dungeon_ecology(
            name: str, ecology: str, stage_count: int
        ) -> str:
            nonlocal ecology_file
            ecology_file = DungeonEcologyFile(
                dungeon_name=name,
                ecology=ecology,
                stage_count=stage_count,
            )
            file_path: Path = DUNGEON_PROCESS_DIR / f"{name}_step1_ecology.json"
            file_path.write_text(
                ecology_file.model_dump_json(indent=4), encoding="utf-8"
            )
            logger.info(
                f"[GenerateDungeonEcologySystem] record_dungeon_ecology 执行:\n"
                f"  dungeon_name: {name}\n"
                f"  stage_count:  {stage_count}\n"
                f"  → {file_path}"
            )
            return (
                f"已记录地下城「{name}」，共 {stage_count} 个战斗场景。"
                f"中间文件已写入: {file_path}"
            )

        def _handle_read_ecology_file(dungeon_name: str) -> str:
            file_path: Path = DUNGEON_PROCESS_DIR / f"{dungeon_name}_step1_ecology.json"
            if not file_path.exists():
                return f"错误：文件不存在 {file_path}"
            return file_path.read_text(encoding="utf-8")

        handlers: Dict[str, Callable[..., str]] = {
            "record_dungeon_ecology": _handle_record_dungeon_ecology,
            "read_ecology_file": _handle_read_ecology_file,
        }
        tools = [_ECOLOGY_TOOL, _READ_ECOLOGY_FILE_TOOL]

        # 浅拷贝 context，不污染原始队列
        history: List[BaseMessage] = list(
            self._game.get_agent_context(world_system_entity).context
        )
        prompt = _build_dungeon_ecology_prompt()

        for round_num in range(1, _MAX_ROUNDS + 1):
            logger.info(
                f"[GenerateDungeonEcologySystem] Step 1 第 {round_num}/{_MAX_ROUNDS} 轮"
            )
            client = DeepSeekClient(
                name=world_system_entity.name,
                prompt=prompt,
                context=history,
                tools=tools,
                tool_choice="auto",
            )
            await client.chat()

            if client.finish_reason == "stop":
                logger.info(
                    f"[GenerateDungeonEcologySystem] Step 1 LLM 完成（stop），第 {round_num} 轮"
                )
                break

            if client.finish_reason != "tool_calls" or not client.tool_calls:
                logger.error(
                    f"[GenerateDungeonEcologySystem] Step 1 意外的 "
                    f"finish_reason={client.finish_reason!r}，中止"
                )
                return

            # 追加本轮消息到 history
            if prompt:
                history.append(HumanMessage(content=prompt))
                prompt = ""  # 后续轮次使用 continuation 模式

            # 追加 LLM 回复到 history
            ai_message = client.response_ai_message
            assert (
                ai_message is not None
            ), "[GenerateDungeonEcologySystem] Step 1 LLM 回复消息为空"
            history.append(ai_message)

            # 按名称分发 tool calls
            for tc in client.tool_calls:

                handler = handlers.get(tc.function.name)
                if handler is None:
                    logger.warning(
                        f"[GenerateDungeonEcologySystem] 未知工具: {tc.function.name!r}"
                    )
                    result = f"错误：未知工具 {tc.function.name!r}"
                else:
                    try:
                        result = handler(**json.loads(tc.function.arguments))
                    except Exception as e:
                        logger.error(
                            f"[GenerateDungeonEcologySystem] 工具 "
                            f"{tc.function.name!r} 执行失败: {e}"
                        )
                        result = f"错误：工具执行失败 {e}"

                # 追加工具执行结果到 history
                history.append(ToolMessage(content=result, tool_call_id=tc.id))
        else:
            logger.error(
                f"[GenerateDungeonEcologySystem] Step 1 达到最大轮次限制 "
                f"{_MAX_ROUNDS}，中止"
            )
            return

        if ecology_file is None:
            logger.error(
                "[GenerateDungeonEcologySystem] Step 1 LLM 已 stop "
                "但未调用 record_dungeon_ecology，中止"
            )
            return

        logger.info(
            f"[GenerateDungeonEcologySystem] Step 1 完成:\n"
            f"  dungeon_name: {ecology_file.dungeon_name}\n"
            f"  ecology:      {ecology_file.ecology}"
        )
        entity.replace(
            GenerateDungeonStagesAction, entity.name, ecology_file.dungeon_name
        )
        logger.info(
            f"[GenerateDungeonEcologySystem] 添加 GenerateDungeonStagesAction: "
            f"dungeon={ecology_file.dungeon_name}"
        )
