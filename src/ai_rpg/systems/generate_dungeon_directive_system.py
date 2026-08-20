"""副本生成指令系统（世界导演在副本生成时执行）"""

from typing import Dict, Final, List, final, override
from loguru import logger
from ..deepseek import DeepSeekClient, MODEL_FLASH
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    AIMessage,
    GenerateDungeonAction,
    HumanMessage,
    WorldDirectorComponent,
)


####################################################################################################################################
def _build_directive_prompt() -> str:
    """构建世界导演的副本创作指令提示词。"""

    return (
        "请为下一步的副本创作下达一条指令："
        "这个新副本应呈现怎样的方向、主题、氛围与关键冲突？"
        "保持开放——不必续写刚刚结束的副本；梦魇世界广大，"
        "请指出你希望被进一步搅动的疯癫之处。"
    )


####################################################################################################################################
@final
class GenerateDungeonDirectiveSystem(ReactiveProcessor):
    """副本生成指令系统

    在副本生成流程的最前面，由世界导演（桌游 GM）执行一次推理，下达副本创作指令，
    并注入到「世界系统.副本生成系统」的上下文，引导后续的副本生成。
    """

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
        generation_entity = entities[0]
        await self._run(generation_entity)

    ####################################################################################################################################
    async def _run(self, generation_entity: Entity) -> None:
        logger.info("[GenerateDungeonDirectiveSystem] 开始：世界导演推理副本创作指令")

        # 1. 查找世界导演实体
        director_entities = self._game.get_group(
            Matcher(all_of=[WorldDirectorComponent])
        ).entities.copy()
        if not director_entities:
            logger.warning(
                "[GenerateDungeonDirectiveSystem] 未找到世界导演实体，跳过指令注入"
            )
            return
        director_entity = next(iter(director_entities))

        # 2. 让世界导演推理一次
        prompt = _build_directive_prompt()
        client = DeepSeekClient(
            name="world_director:directive",
            prompt=prompt,
            context=self._game.get_agent_context(director_entity).context,
            model=MODEL_FLASH,
            thinking=False,
        )
        await client.chat()

        directive = client.response_content
        if not directive:
            logger.warning(
                "[GenerateDungeonDirectiveSystem] 世界导演未返回指令，跳过注入"
            )
            return

        logger.info(f"[GenerateDungeonDirectiveSystem] 世界导演创作指令:\n{directive}")

        # 3. 持久化导演 Q&A 到导演上下文
        self._game.add_human_message(
            director_entity,
            HumanMessage(content=prompt),
        )
        self._game.add_ai_message(
            director_entity,
            AIMessage(content=directive),
        )

        # 4. 注入指令到副本生成系统上下文
        self._game.add_human_message(
            generation_entity,
            HumanMessage(content=f"# 世界导演的创作指令\n\n{directive}"),
        )
        logger.info(
            f"[GenerateDungeonDirectiveSystem] 已向副本生成系统 "
            f"{generation_entity.name!r} 注入导演指令"
        )
