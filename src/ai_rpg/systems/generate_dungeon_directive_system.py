"""副本生成指令系统（世界导演在副本生成时执行）"""

from typing import Dict, Final, List, final, override
from loguru import logger
from ..deepseek import DeepSeekClient, MODEL_FLASH
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    AIMessage,
    GenerateDungeonAction,
    GenerateDungeonDirectiveAction,
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
        generation_entity = entities[0]
        await self._run(generation_entity)

    ####################################################################################################################################
    async def _run(self, generation_entity: Entity) -> None:
        logger.info("[GenerateDungeonDirectiveSystem] 开始：世界导演推理副本创作指令")

        # 1. 查找世界导演实体（允许缺失时降级为空指令）
        director_entities = self._game.get_group(
            Matcher(all_of=[WorldDirectorComponent])
        ).entities.copy()

        assert len(director_entities) == 1, "存在多个世界导演实体，数据异常"
        director_entity = next(iter(director_entities))

        # 2. 让世界导演推理一次
        prompt = _build_directive_prompt()
        client = DeepSeekClient(
            name=director_entity.name,
            prompt=prompt,
            context=self._game.get_agent_context(director_entity).context,
            model=MODEL_FLASH,
            thinking=False,
        )
        await client.chat()

        # 默认指令为空，防止世界导演未返回时流程中断
        directive = ""

        # 3. 检查世界导演是否返回指令
        if client.response_ai_message is None:
            logger.warning(
                "[GenerateDungeonDirectiveSystem] 世界导演未返回指令，跳过注入"
            )
        else:
            directive = client.response_ai_message.content
            logger.info(
                f"[GenerateDungeonDirectiveSystem] 世界导演创作指令:\n{directive}"
            )

            # 4. 持久化导演 Q&A 到导演上下文
            self._game.add_human_message(
                director_entity,
                HumanMessage(content=prompt),
            )
            self._game.add_ai_message(
                director_entity,
                AIMessage(content=directive),
            )

        # 5. 挂接 GenerateDungeonDirectiveAction，将指令传递给 GenerateDungeonPremiseSystem
        #    （无论是否获得指令都挂接，保证流程持续推进；不写入副本生成系统上下文）
        generation_entity.replace(
            GenerateDungeonDirectiveAction,
            generation_entity.name,
            directive,
        )
        logger.info(
            f"[GenerateDungeonDirectiveSystem] 已挂接 GenerateDungeonDirectiveAction: "
            f"{generation_entity.name!r}, directive 长度={len(directive)}"
        )
