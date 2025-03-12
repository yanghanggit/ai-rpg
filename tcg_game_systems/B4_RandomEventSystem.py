import random
from loguru import logger
from overrides import override
from pydantic import BaseModel
from agent.chat_request_handler import ChatRequestHandler
from entitas import ExecuteProcessor, Matcher  # type: ignore
from entitas.entity import Entity
from game.tcg_game import TCGGame
from typing import Deque, List, Optional
from rpg_models.event_models import AnnounceEvent
from tcg_models.v_0_0_1 import (
    # ActorInstance,
    # ActiveSkill,
    TriggerType,
    HitInfo,
    HitType,
    DamageType,
)
from components.components import (
    AttributeCompoment,
    ActorComponent,
    FinalAppearanceComponent,
    StageEnvironmentComponent,
)


class ModifyRet(BaseModel):
    result_text: str
    result_stack: Deque[HitInfo]


class B4_RandomEventSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    @override
    def execute(self) -> None:
        pass

    async def a_execute1(self) -> None:
        if self._game._battle_manager._new_turn_flag:
            return
        if self._game._battle_manager._battle_end_flag:
            return
        if len(self._game._battle_manager._order_queue) == 0:
            return
        if len(self._game._battle_manager._hits_stack) == 0:
            return
        if self._game._battle_manager._event_msg.done_flag:
            return

        # 1/3概率随机决定发生or不发生
        if not random.randint(1, 3) == 1:
            return
        
        await self._event_start()
        self._get_choice()
        await self._event_end()

    async def _event_start(self) -> None:
        # 构造prompt，给他信息，请给我生成个随机事件吧
        # TODO 这里决定生成好事件还是坏事件
        msg = _gen_event_start_prompt()
        world_system_entity = self._game.get_world_entity("战斗系统")
        assert world_system_entity is not None
        request_handlers: List[ChatRequestHandler] = []
        agent_short_term_memory = self._game.get_agent_short_term_memory(
            world_system_entity
        )
        request_handlers.append(
            ChatRequestHandler(
                name=world_system_entity._name,
                prompt=msg,
                chat_history=agent_short_term_memory.chat_history,
            )
        )
        await self._game.langserve_system.gather(request_handlers=request_handlers)
        # 然后把生成的事件先临时存下
        self._game._battle_manager._event_msg.event = request_handlers[
            0
        ].response_content

    def _get_choice(self) -> None:
        choice = input("请输入你的选择：")
        while choice not in ["1", "2", "3"]:
            choice = input("请输入你的选择：")
        self._game._battle_manager._event_msg.choice = int(choice)

    async def _event_end(self) -> None:
        # 构造prompt
        msg = _gen_event_start_prompt()

        #开问
        world_system_entity = self._game.get_world_entity("战斗系统")
        assert world_system_entity is not None
        request_handlers: List[ChatRequestHandler] = []
        agent_short_term_memory = self._game.get_agent_short_term_memory(
            world_system_entity
        )
        request_handlers.append(
            ChatRequestHandler(
                name=world_system_entity._name,
                prompt=msg,
                chat_history=agent_short_term_memory.chat_history,
            )
        )
        await self._game.langserve_system.gather(request_handlers=request_handlers)

        # 得到返回
        try:
            ret = ModifyRet.model_validate_json(request_handlers[0].response_content)
        except:
            logger.error("返回格式错误")
            return
        # 如果返回结果没问题，就更新数据
        self._game._battle_manager._event_msg.result = ret.result_text
        self._game._battle_manager._hits_stack = ret.result_stack

        # 记录到history中
        event = self._game._battle_manager._event_msg.event
        choice = self._game._battle_manager._event_msg.choice
        result = self._game._battle_manager._event_msg.result
        self._game._battle_manager.add_history(event)
        self._game._battle_manager.add_history(result)
        # 广播给所有人
        stage_name = self._game.get_current_stage_entity()._name
        self._game.broadcast_event(
            world_system_entity,
            AnnounceEvent(
                message=event + result,
                announcer_name="事件系统",
                stage_name=stage_name,
                content=event + result,
            ),
        )

        # 标记本轮中已经发生过随机事件
        self._game._battle_manager._event_msg.done_flag = True


def _gen_event_start_prompt() -> str:
    return ""


def _gen_event_end_prompt() -> str:
    return ""
