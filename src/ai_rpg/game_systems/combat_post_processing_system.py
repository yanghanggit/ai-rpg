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
class CombatPostProcessingSystem(ExecuteProcessor):

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
            logger.warning(
                "战斗结束，准备总结战斗结果！！，可以做一些压缩提示词的行为!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            )
            await self._process_combat_summary()

            # TODO, 进入战斗后准备的状态，离开当前状态。
            self._game.current_engagement.combat_post_wait()

        else:
            assert False, "不可能出现的情况！"

    #######################################################################################################################################
    # 总结！！！
    async def _process_combat_summary(self) -> None:
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
            message = f"""# 指令！{stage_entity1.name} 的战斗已经结束，你需要记录下这次战斗的经历。
            
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
                    name=entity1.name,
                    prompt=message,
                    chat_history=self._game.get_agent_chat_history(
                        entity1
                    ).chat_history,
                )
            )

        # 语言服务
        await ChatClient.gather_request_post(clients=request_handlers)

        # 结束的处理。
        for request_handler in request_handlers:

            entity2 = self._game.get_entity_by_name(request_handler.name)
            assert entity2 is not None

            stage_entity2 = self._game.safe_get_stage_entity(entity2)
            assert stage_entity2 is not None

            # 在这里做压缩！！先测试，可以不做。TODO。
            self._remove_combat_chat_messages(entity2)

            # 压缩后的战斗经历，就是战斗过程做成摘要。
            summary = f"""# 提示！ 你经历了一场战斗！
战斗所在场景：{stage_entity2.name}

## 你记录下了这次战斗的经历

{request_handler.response_content}"""

            # 添加记忆，并给客户端。
            self._game.notify_event(
                set({entity2}),
                CombatCompleteEvent(
                    message=summary,
                    actor=entity2.name,
                    summary=summary,
                ),
            )

    #######################################################################################################################################
    # 压缩战斗历史。
    def _remove_combat_chat_messages(self, entity: Entity) -> None:

        assert entity.has(ActorComponent), f"实体: {entity.name} 不是角色！"

        # 获取当前的战斗实体。
        stage_entity = self._game.safe_get_stage_entity(entity)
        assert stage_entity is not None

        # 获取最近的战斗消息。
        begin_message = self._game.find_recent_human_message_by_attribute(
            actor_entity=entity,
            attribute_key="combat_kickoff_tag",
            attribute_value=stage_entity.name,
        )
        assert begin_message is not None

        # 获取最近的战斗消息。
        end_message = self._game.find_recent_human_message_by_attribute(
            actor_entity=entity,
            attribute_key="combat_result_tag",
            attribute_value=stage_entity.name,
        )
        assert end_message is not None

        if begin_message is None or end_message is None:
            logger.error(
                f"战斗消息不完整！{entity.name} begin_message: {begin_message} end_message: {end_message}"
            )
            return

        agent_chat_history = self._game.get_agent_chat_history(entity)
        begin_message_index = agent_chat_history.chat_history.index(begin_message)
        end_message_index = agent_chat_history.chat_history.index(end_message) + 1
        # 开始移除！！！！。
        del agent_chat_history.chat_history[begin_message_index:end_message_index]
        logger.info(f"战斗消息压缩成功！{entity.name}")
        logger.debug(f"begin_message: \n{begin_message.model_dump_json(indent=2)}")
        logger.debug(f"end_message: \n{end_message.model_dump_json(indent=2)}")

    #######################################################################################################################################
