"""怪物上下文探测系统（纯调试）。"""

from typing import Dict, Final, List, final, override

from loguru import logger

from ..deepseek import DeepSeekClient, batch_chat
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    DeathComponent,
    MonsterComponent,
    MonsterTurnAction,
)
from ..utils import prompt_builder


#######################################################################################################################################
@prompt_builder
def _build_context_probe_prompt(monster_name: str) -> str:
    """生成调试探针问题（固定文案，不携带任何答案，避免让怪物直接照抄）。"""
    return f"""# 战场环境回忆测试

你是 {monster_name}。请仅依据你已掌握的记忆回答以下问题，不要编造记忆之外的内容：

1. 你现在所在的场景叫什么？场景环境是怎样的？
2. 当前战场上，除了你自己之外，还有哪些角色？请逐个列出：
   - 名字
   - 与你之间的阵营关系（友方/敌方）
   - 外观描述

请用分点作答。"""


#######################################################################################################################################
@final
class MonsterContextProbeSystem(ReactiveProcessor):
    """
    怪物上下文探测系统（纯调试）。
    """

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {
            Matcher(MonsterTurnAction): GroupEvent.ADDED,
        }

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        """只探测有 MonsterTurnAction 且未死亡的怪物实体。"""
        return (
            entity.has(MonsterTurnAction)
            and entity.has(MonsterComponent)
            and not entity.has(DeathComponent)
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        # 与 MonsterPrePlaySystem 保持一致的战斗状态守卫。
        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("MonsterContextProbeSystem: 战斗未进行中，跳过探测")
            return

        if not entities:
            return

        # 为每个怪物构建探测请求（context 只读复用，不会修改现有历史）。
        chat_clients: List[DeepSeekClient] = []
        for entity in entities:
            prompt = _build_context_probe_prompt(monster_name=entity.name)
            chat_clients.append(
                DeepSeekClient(
                    name=entity.name,
                    full_prompt=prompt,
                    context=self._game.get_agent_context(entity).context,
                )
            )
            logger.info(f"MonsterContextProbeSystem: [{entity.name}] 上下文探测开始")

        # 并行 LLM 推理。
        await batch_chat(clients=chat_clients)

        # 打印每个怪物的问答与参考答案，供人工比对。
        for client in chat_clients:
            assert (
                self._game.get_entity_by_name(client.name) is not None
            ), f"MonsterContextProbeSystem: 无法找到实体 {client.name}"

            # 获取实体对象，确保存在。
            if client.response_ai_message is None:
                logger.warning(
                    f"MonsterContextProbeSystem: [{client.name}] LLM 返回空响应，无法比对"
                )
                continue

            logger.info("=" * 80)
            logger.info(
                f"MonsterContextProbeSystem: [{client.name}] 调试探针问题：\n{client.full_prompt}"
            )
            logger.info(
                f"MonsterContextProbeSystem: [{client.name}] 怪物回答：\n{client.response_content}"
            )
            logger.info("=" * 80)

    ####################################################################################################################################
