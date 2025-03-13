import random
from loguru import logger
from overrides import override
from pydantic import BaseModel
from agent.chat_request_handler import ChatRequestHandler
from entitas import ExecuteProcessor, Matcher  # type: ignore
from entitas.entity import Entity
from game.tcg_game import TCGGame
from typing import Deque, Dict, List, Optional
from rpg_models.event_models import AnnounceEvent
from tcg_models.v_0_0_1 import (
    # ActorInstance,
    # ActiveSkill,
    Buff,
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
import json


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
        if len(self._game._battle_manager._hits_stack.stack) == 0:
            return
        if self._game._battle_manager._event_msg.done_flag:
            return

        # 1/3概率随机决定发生or不发生
        # if not random.randint(1, 3) == 1:
        #     return

        await self._event_start()
        self._get_choice()
        await self._event_end()

    async def _event_start(self) -> None:
        # 构造prompt，给他信息，请给我生成个随机事件吧
        # TODO 这里决定生成好事件还是坏事件
        current_stage = self._game.get_current_stage_entity()
        assert current_stage is not None
        actors_set = self._game.retrieve_actors_on_stage(current_stage)
        actors_info_list: List[str] = [
            f"{actor._name}：\n外表：{actor.get(FinalAppearanceComponent).final_appearance}\n生命值：{actor.get(AttributeCompoment).hp}/{actor.get(AttributeCompoment).maxhp}\n行动力：{actor.get(AttributeCompoment).action_times}/{actor.get(AttributeCompoment).max_action_times}"
            for actor in actors_set
            if actor.has(FinalAppearanceComponent)
        ]
        msg = _gen_event_start_prompt(
            current_stage_name=current_stage._name,
            current_stage_narration=current_stage.get(
                StageEnvironmentComponent
            ).narrate,
            actors_info_list=actors_info_list,
            doing_hits_log=self._game._battle_manager._hits_stack.model_dump_json(),
            battle_history=self._game._battle_manager.battle_history_dump,
        )

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
        logger.warning(self._game._battle_manager._event_msg.event)
        choice = input("请输入你的选择：")
        while choice not in ["1", "2", "3"]:
            choice = input("请输入你的选择：")
        self._game._battle_manager._event_msg.choice = int(choice)

    async def _event_end(self) -> None:
        # 构造prompt
        current_stage = self._game.get_current_stage_entity()
        assert current_stage is not None
        actors_set = self._game.retrieve_actors_on_stage(current_stage)
        actors_info_list: List[str] = [
            f"{actor._name}：\n外表：{actor.get(FinalAppearanceComponent).final_appearance}\n生命值：{actor.get(AttributeCompoment).hp}/{actor.get(AttributeCompoment).maxhp}\n行动力：{actor.get(AttributeCompoment).action_times}/{actor.get(AttributeCompoment).max_action_times}"
            for actor in actors_set
            if actor.has(FinalAppearanceComponent)
        ]
        msg = _gen_event_end_prompt(
            current_stage_name=current_stage._name,
            current_stage_narration=current_stage.get(
                StageEnvironmentComponent
            ).narrate,
            actors_info_list=actors_info_list,
            doing_hits_log=self._game._battle_manager._hits_stack.model_dump_json(),
            battle_history=self._game._battle_manager.battle_history_dump,
            event_text=self._game._battle_manager._event_msg.event,
            choice=self._game._battle_manager._event_msg.choice,
            buff_list=self._game.world.boot.data_base.buffs,
        )

        # 开问
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
            logger.info(ret.result_stack)
        except:
            logger.error("返回格式错误")
            return
        # 如果返回结果没问题，就更新数据
        self._game._battle_manager._event_msg.result = ret.result_text
        self._game._battle_manager._hits_stack.stack = ret.result_stack

        # 记录到history中
        event = self._game._battle_manager._event_msg.event
        choice = self._game._battle_manager._event_msg.choice
        result = self._game._battle_manager._event_msg.result
        self._game._battle_manager.add_history("发生了事件：" + event)
        self._game._battle_manager.add_history(result)
        # 广播给所有人
        stage_entity = self._game.get_current_stage_entity()
        assert stage_entity is not None
        player_entity = self._game.get_player_entity()
        assert player_entity is not None
        self._game.broadcast_event(
            player_entity,
            AnnounceEvent(
                message=event + result,
                announcer_name="事件系统",
                stage_name=stage_entity._name,
                content=event + result,
            ),
        )

        # 标记本轮中已经发生过随机事件
        self._game._battle_manager._event_msg.done_flag = True


def _gen_event_start_prompt(
    current_stage_name: str,
    current_stage_narration: str,
    actors_info_list: List[str],
    doing_hits_log: str,
    battle_history: str,
) -> str:
    return f"""
# 请作为事件系统，参考战斗日志，生成一个随机事件。
## 你的职责
1. 阅读战斗日志，了解当前战场形势。
2. 生成一个随机事件，要求符合随机事件要求。
3. 等待玩家返回结果。
## 战场形势
### 当前所在的场景
{current_stage_name}
### 当前场景描述
{current_stage_narration}
### 当前场景内所有角色的状态
{"\n".join(actors_info_list)}
### 即将执行的行动栈
{doing_hits_log}
### 截至目前，整场战斗的记录
{battle_history}
## 行动栈说明
1. 行动栈中的元素的类型为HitInfo。代表了角色使用的行动所产生的效果。
2. 行动栈中的元素先进后出，即最后一个是最先执行的行动。
## 随机事件要求
1. 随机事件能够影响玩家方角色的行为选择和执行结果。
2. 必须提供三个选项让玩家选择。
3. 不要总是让玩家方获胜，适时时给予挫折。
4. 必须充分考虑角色的行为对其目标之外的场景内元素，包括其他角色，场景内物品，场景本身等带来的影响。
5. 可以生成一些突兀的，机械降神的事件。
6. 不要让选项看上去差距过大，要让潜在的收益和风险并存。要让玩家感受挫折时，需要让所有选项看上去都是坏选项。
7. 必须考虑以往已经发生过的随机事件，不要雷同重复，并要使多个随机事件形成一条连续的事件链。
## 描述要求
1. 描述需要生动和有趣。
2. 描述中不要附带角色对话，不要揣测角色心理活动，仅以第三人称视角对发生的事件做客观描述。
3. 尽量将描述的长度限制在五到十句话左右。
4. 描述需要客观公正，不要在价值观上偏袒任何一方。
"""


def _gen_event_end_prompt(
    current_stage_name: str,
    current_stage_narration: str,
    actors_info_list: List[str],
    doing_hits_log: str,
    battle_history: str,
    event_text: str,
    choice: int,
    buff_list: Dict[str, Buff],
) -> str:
    return f"""
# 请作为事件系统，参考战斗日志，已生成的随机事件起因和玩家选项，生成该随机事件的结果。
## 你的职责
1. 阅读战斗日志，了解当前战场形势。
2. 阅读已生成的随机事件起因和玩家选项。充分理解玩家的选择。
3. 生成该随机事件的结果描述，要求符合随机事件要求。
4. 根据结果描述，修改行动栈中的值，或向行动栈中添加新HitInfo。以使本次随机事件的结果生效。
## 战场形势
### 当前所在的场景
{current_stage_name}
### 当前场景描述
{current_stage_narration}
### 当前场景内所有角色的状态
{"\n".join(actors_info_list)}
### 即将执行的行动栈
{doing_hits_log}
### 截至目前，整场战斗的记录
{battle_history}
### 随机事件起因
{event_text}
### 玩家选择
{choice}
## 行动栈说明
1. 行动栈中的元素的类型为HitInfo。代表了角色使用的行动所产生的效果。
2. 行动栈中的元素先进后出，即最后一个是最先执行的行动。
3. 若要在行动栈中添加新的HitInfo作为随机事件的结果，通常添加至最后一个。
4. 修改行动栈时，添加或移除的buff必须存在于给出的buff列表中。
5. HitInfo中的target必须是存在于场景中的角色全名。
## HitInfo说明
{HitInfo.get_description()}
## 构成新HitInfo时的可用Buff列表
{"\n".join([buff.model_dump_json() for name, buff in buff_list.items()])}
## 随机事件要求
1. 随机事件能够影响玩家方角色的行为选择和执行结果。
2. 必须提供三个选项让玩家选择。
3. 不要总是让玩家方获胜，适时时给予挫折。
4. 必须充分考虑角色的行为对其目标之外的场景内元素，包括其他角色，场景内物品，场景本身等带来的影响。
5. 可以生成一些突兀的，机械降神的事件。
6. 不要让选项看上去差距过大，要让潜在的收益和风险并存。要让玩家感受挫折时，需要让所有选项看上去都是坏选项。
7. 必须考虑以往已经发生过的随机事件，不要雷同重复，并要使多个随机事件形成一条连续的事件链。
## 描述要求
1. 描述需要生动和有趣。
2. 描述中不要附带角色对话，不要揣测角色心理活动，仅以第三人称视角对发生的事件做客观描述。
3. 尽量将描述的长度限制在五到十句话左右。
4. 描述需要客观公正，不要在价值观上偏袒任何一方。
## 输出格式要求
请严格遵守以下JSON结构示例：
{{
    "result_text":"此处替换为你生成的随机事件结果描述。类型为str。",
    "result_stack":[
        {{
            "修改后的HitInfo"...
        }}
    ]
}}
### 注意事项
- 引用角色或场景时，请严格遵守全名机制
- 所有输出必须为第一人称视角。
- 输出不得包含超出所需 JSON 格式的其他文本、解释或附加信息。
- 不要使用```json```来封装内容。
"""
