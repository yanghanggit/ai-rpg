from typing import List, final
from loguru import logger
from overrides import override
from ..chat_services.client import ChatClient
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import (
    ActorComponent,
    CombatCompleteEvent,
    CombatResult,
    HeroComponent,
    RPGCharacterProfileComponent,
)


#######################################################################################################################################
@final
class CombatCompleteSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    async def execute(self) -> None:
        if not self._game.current_engagement.is_complete_phase:
            return  # 不是本阶段就直接返回

        if (
            self._game.current_engagement.combat_result == CombatResult.HERO_WIN
            or self._game.current_engagement.combat_result == CombatResult.HERO_LOSE
        ):
            # 测试，总结战斗结果。
            logger.info("战斗结束，准备总结战斗结果！！，可以做一些压缩提示词的行为!!!!!!!!")
            #await self._summarize_combat_result()

            # TODO, 进入战斗后准备的状态，离开当前状态。
            self._game.current_engagement.combat_post_wait()

        else:
            assert False, "不可能出现的情况！"

    #######################################################################################################################################
    # 总结！！！
    async def _summarize_combat_result(self) -> None:
        # 获取所有需要进行角色规划的角色
        actor_entities = self._game.get_group(
            Matcher(
                all_of=[ActorComponent, HeroComponent, RPGCharacterProfileComponent],
            )
        ).entities

        # 处理角色规划请求
        request_handlers: List[ChatClient] = []
        for entity1 in actor_entities:

            stage_entity1 = self._game.safe_get_stage_entity(entity1)
            assert stage_entity1 is not None

            # 生成消息
            message = f"""# 提示！{stage_entity1._name} 战斗结束，你决定记录下这次战斗的经历。
## 输出内容:
1. 战斗发生的场景。
2. 你的对手是谁，他们的特点。
3. 战斗的开始，过程以及如何结束的。
4. 你的感受，你的状态。
5. 你的同伴，他们的表现。
## 输出格式规范:
- 第一人称视角。
- 要求单段紧凑自述（禁用换行/空行/数字）。
- 尽量简短。"""

            # 生成请求处理器
            request_handlers.append(
                ChatClient(
                    agent_name=entity1._name,
                    prompt=message,
                    chat_history=self._game.get_agent_short_term_memory(
                        entity1
                    ).chat_history,
                )
            )

        # 语言服务
        await self._game.chat_system.gather(request_handlers=request_handlers)

        # 结束的处理。
        for request_handler in request_handlers:

            entity2 = self._game.get_entity_by_name(request_handler._name)
            assert entity2 is not None

            stage_entity2 = self._game.safe_get_stage_entity(entity2)
            assert stage_entity2 is not None

            # 在这里做压缩！！先测试，可以不做。TODO。
            self._compress_chat_history_after_combat(entity2)

            # 压缩后的战斗经历，就是战斗过程做成摘要。
            summary = f"""# 发生事件! 你经历了一场战斗！
场景: {stage_entity2._name}
你记录下了这次战斗的经历:
{request_handler.response_content}"""

            # 添加记忆，并给客户端。
            self._game.notify_event(
                set({entity2}),
                CombatCompleteEvent(
                    message=summary,
                    actor=entity2._name,
                    summary=summary,
                ),
            )

    #######################################################################################################################################
    # 压缩战斗历史。
    def _compress_chat_history_after_combat(self, entity: Entity) -> None:

        assert entity.has(ActorComponent), f"实体: {entity._name} 不是角色！"

        # 获取当前的战斗实体。
        stage_entity = self._game.safe_get_stage_entity(entity)
        assert stage_entity is not None

        # 获取最近的战斗消息。
        begin_message = self._game.retrieve_recent_human_message_by_kargs(
            entity, "combat_kickoff_tag", stage_entity._name
        )
        assert begin_message is not None

        # 获取最近的战斗消息。
        end_message = self._game.retrieve_recent_human_message_by_kargs(
            entity, "combat_result_tag", stage_entity._name
        )
        assert end_message is not None

        if begin_message is None or end_message is None:
            logger.error(
                f"战斗消息不完整！{entity._name} begin_message: {begin_message} end_message: {end_message}"
            )
            return

        short_term_memory = self._game.get_agent_short_term_memory(entity)
        begin_message_index = short_term_memory.chat_history.index(begin_message)
        end_message_index = short_term_memory.chat_history.index(end_message) + 1
        # 移除！！！！。
        del short_term_memory.chat_history[begin_message_index:end_message_index]
        logger.debug(
            f"战斗消息压缩成功！{entity._name} begin_message: {begin_message} end_message: {end_message}"
        )

    #######################################################################################################################################
