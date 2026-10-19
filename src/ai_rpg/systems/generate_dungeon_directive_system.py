"""副本生成指令系统：世界导演先给出本次副本的创作方向。"""

from typing import Dict, Final, List, final, override

from loguru import logger

from ..deepseek import DEEPSEEK_SERVICE, DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..llm import ChatCompletionRequest
from ..models import (
    AIMessage,
    DungeonDraft,
    GenerateDungeonAction,
    HumanMessage,
    WorldDirectorComponent,
)
from ..utils import prompt_builder


####################################################################################################################################
@prompt_builder
def _build_directive_prompt(generator_name: str) -> str:
    """构建世界导演的副本创作指令提示词。

    执行方实体名由引擎注入：导演只输出一段指令，真正驱动生成的是携带
    `GenerateDungeonAction` 的那个实体（即 `generator_name`）。故事层 prompt 里不写这个名字，
    所以实体改名不会让导演的人设描述失效。
    """

    return f"""你输出的这段指令会直接交给「{generator_name}」执行——由它据此生成副本的名称、整体设定、房间与怪物。你不需要指定接收方，也不需要调用任何工具，只输出指令本身。

请回顾你的人设，并理解当前的世界变化，为下一步的副本创作下达一条指令：这个新副本应呈现怎样的方向、主题、氛围与关键冲突？保持开放——不必续写刚刚结束的副本；请指出你希望这个世界如何进一步推进与演变。若尚未收到任何世界变化的通知（无已归档副本），也必须基于现有世界观给出倾向性指令，不得拒绝下指令或等待补充材料。"""


####################################################################################################################################
@final
class GenerateDungeonDirectiveSystem(ReactiveProcessor):
    """副本生成指令系统"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

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
        assert len(entities) == 1, "同时存在多个 GenerateDungeonAction，数据异常"
        await self._run(entities[0].name)

    ####################################################################################################################################
    async def _run(self, generator_name: str) -> None:
        logger.info("[GenerateDungeonDirectiveSystem] 开始：世界导演推理副本创作指令")

        # 新建副本生成的中间过程数据，供本次流程后续系统依次填充
        draft = DungeonDraft()
        self._game._dungeon_draft = draft

        # 1. 查找世界导演实体（允许缺失时降级为空指令）
        director_entities = self._game.get_group(
            Matcher(all_of=[WorldDirectorComponent])
        ).entities.copy()

        assert len(director_entities) == 1, "存在多个世界导演实体，数据异常"
        director_entity = next(iter(director_entities))

        # 2. 让世界导演推理一次（执行方实体名由引擎注入）
        prompt = _build_directive_prompt(generator_name)
        request = ChatCompletionRequest(
            label=director_entity.name,
            input_message=prompt,
            messages=self._game.get_agent_memory(director_entity).messages,
            model=DeepSeekClient.MODEL_FLASH,
            # thinking=False,
        )
        result = await DEEPSEEK_SERVICE.complete(request)

        # 默认指令为空，防止世界导演未返回时流程中断
        directive = ""

        # 3. 检查世界导演是否返回指令
        if result.ai_message is None:
            logger.warning(
                "[GenerateDungeonDirectiveSystem] 世界导演未返回指令，跳过注入"
            )
        else:
            directive = result.ai_message.content
            logger.info(
                f"[GenerateDungeonDirectiveSystem] 世界导演创作指令:\n{directive}"
            )

            # 4. 持久化导演 Q&A 到导演记忆
            self._game.add_human_message(
                director_entity,
                HumanMessage(content=prompt, dungeon_directive=director_entity.name),
            )
            self._game.add_ai_message(
                director_entity,
                AIMessage(content=directive),
            )

        # 5. 写入中间过程数据，供 GenerateDungeonProfileSystem 读取
        #    （无论是否获得指令都写入，保证流程持续推进；不写入副本生成系统记忆）
        draft.directive = directive
        logger.info(
            f"[GenerateDungeonDirectiveSystem] 已写入 directive，长度={len(directive)}"
        )
