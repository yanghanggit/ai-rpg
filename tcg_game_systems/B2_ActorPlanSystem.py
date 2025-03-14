# from overrides import override
# from pydantic import BaseModel
# from agent.chat_request_handler import ChatRequestHandler
# from entitas import ExecuteProcessor  # type: ignore

# # from entitas.entity import Entity
# # from game.tcg_game_context import TCGGameContext
# from game.tcg_game import TCGGame
# from typing import Deque, List

# # from tcg_models.v_0_0_1 import ActorInstance, ActiveSkill
# from components.components import (
#     AttributeCompoment,
#     # ActorComponent,
#     FinalAppearanceComponent,
#     StageEnvironmentComponent,
# )
# from loguru import logger

# # import json


# class ChoiceRet(BaseModel):
#     num: int
#     target: str
#     text: str


# class B2_ActorPlanSystem(ExecuteProcessor):

#     def __init__(self, game_context: TCGGame) -> None:
#         self._game: TCGGame = game_context

#     @override
#     def execute(self) -> None:
#         pass

#     @override
#     async def a_execute1(self) -> None:
#         await self._make_plan()

#     async def _make_plan(self) -> None:
#         if self._game._battle_manager._new_turn_flag:
#             return
#         if self._game._battle_manager._battle_end_flag:
#             return
#         if len(self._game._battle_manager._order_queue) == 0:
#             return

#         # 找出当前应该做决定的角色
#         thinker_name = self._game._battle_manager._order_queue[0]
#         thinker = self._game.get_entity_by_name(thinker_name)
#         if thinker is None:
#             assert False, "can't find entity by thinker name"
#         comp = thinker.get(AttributeCompoment)
#         if comp.action_times <= 0:
#             assert False, "角色行动力<=0但是没删掉"
#             return
#         if comp.hp <= 0:
#             return

#         # 检查这个时候触发的buff，写的太硬了给我自己看笑了
#         if any(buff_name == "眩晕" for buff_name, last_times in comp.buffs.items()):
#             self._game._battle_manager.add_history(
#                 f"{thinker_name} 被眩晕了，无法行动！"
#             )
#             self._game._battle_manager._order_queue.popleft()
#             return

#         # 问他做什么决定
#         # 得到所有角色和场景信息
#         current_stage = self._game.safe_get_stage_entity(thinker)
#         assert current_stage is not None
#         actors_set = self._game.retrieve_actors_on_stage(current_stage)
#         actors_info_list: List[str] = [
#             f"{actor._name}：\n外表：{actor.get(FinalAppearanceComponent).final_appearance}\n生命值：{actor.get(AttributeCompoment).hp}/{actor.get(AttributeCompoment).maxhp}\n行动力：{actor.get(AttributeCompoment).action_times}/{actor.get(AttributeCompoment).max_action_times}"
#             for actor in actors_set
#             if actor.has(FinalAppearanceComponent)
#         ]
#         # 得到自己的所有技能信息 问题：让不让角色能看其他人的技能？
#         active_skills = [
#             f"{index} {x.name}: {x.description}"
#             for index, x in enumerate(comp.active_skills)
#         ]
#         trigger_skills = [
#             f"{index} {x.name}: {x.description}"
#             for index, x in enumerate(comp.trigger_skills)
#         ]
#         # 得到除掉自己后的行动队列
#         order = self._game._battle_manager._order_queue.copy()
#         order.popleft()
#         # 生成prompt
#         message = _gen_prompt(
#             current_stage_name=current_stage._name,
#             current_stage_narration=current_stage.get(
#                 StageEnvironmentComponent
#             ).narrate,
#             actors_info_list=actors_info_list,
#             active_skill_list=active_skills,
#             trigger_skill_list=trigger_skills,
#             act_order=order,
#             battle_history=self._game._battle_manager.battle_history_dump,
#         )

#         logger.info(f"thinker_name: {thinker_name}, message:\n{message}")

#         # 开问
#         request_handlers: List[ChatRequestHandler] = []
#         agent_short_term_memory = self._game.get_agent_short_term_memory(thinker)
#         request_handlers.append(
#             ChatRequestHandler(
#                 name=thinker._name,
#                 prompt=message,
#                 chat_history=agent_short_term_memory.chat_history,
#             )
#         )
#         await self._game.langserve_system.gather(request_handlers=request_handlers)
#         self._game.append_human_message(
#             thinker, "你的回合开始，请思考并给出本回合的行动计划。"
#         )
#         self._game.append_ai_message(thinker, request_handlers[0].response_content)

#         # 得到回复后，构建hit
#         try:
#             ret: ChoiceRet = ChoiceRet.model_validate_json(
#                 request_handlers[0].response_content
#             )
#         except:
#             logger.error("返回格式错误")
#             ret = ChoiceRet(num=-1, target=thinker_name, text="返回格式错误")
#         if ret.num == -1:
#             msg = f"{thinker_name}决定跳过行动，原因是：{ret.text}"
#             self._game._battle_manager.add_history(msg)
#             self._game._battle_manager._order_queue.popleft()
#             return
#         else:
#             hits = self._game._battle_manager.generate_hits(
#                 comp.active_skills[ret.num], thinker_name, ret.target, ret.text
#             )
#         # hit插入执行栈内
#         self._game._battle_manager._hits_stack.stack.extend(hits)


# def _gen_prompt(
#     current_stage_name: str,
#     current_stage_narration: str,
#     actors_info_list: List[str],
#     active_skill_list: List[str],
#     trigger_skill_list: List[str],
#     act_order: Deque[str],
#     battle_history: str,
# ) -> str:
#     return f"""
# # 你的回合开始，请思考并给出本回合的行动计划。
# ## 战场形式
# ### 当前所在的场景
# {current_stage_name}
# ### 当前场景描述
# {current_stage_narration}
# ### 当前场景内所有角色的状态
# {"\n".join(actors_info_list)}
# ### 你的主动技能列表
# {"\n".join(active_skill_list)}
# ### 你的被动技能列表
# {"\n".join(trigger_skill_list)}
# ### 本回合尚未未行动角色行动顺序队列
# {", ".join(f"{index}: {item}" for index, item in enumerate(act_order))}
# ### 战斗历史
# {battle_history}
# ## 行动计划规则
# 你需要选择使用技能，或不使用技能。
# ### 使用技能
# 如果你选择了使用技能，你需要给出三个值：\n
# 1. 从你的主动技能中选择想要使用的技能的序号。
# 2. 选择释放技能的目标角色的名称。
# 3. 释放技能时你想说的话。
# ### 不使用技能
# 如果你选择不使用技能，代表你认为使用技能对你并不重要，或并不符合你的目标。你需要给出你不想使用技能的原因。此时：
# 1. 你想使用的技能的序号固定为-1。
# 2. 释放技能的目标角色的名称固定为你的名称。
# 3. 释放技能时你想说的话固定为你不想使用技能的原因。
# ## 输出格式指南
# 请严格遵守以下JSON结构示例：
# {{
#     "num":"此处替换为想使用的技能的序号。类型为整数。",
#     "target":"此处替换为你想释放技能的目标角色的名称。",
#     "text":"此处替换为你想说的话或你的原因。",
# }}
# ### 注意事项
# - 引用角色或场景时，请严格遵守全名机制
# - 所有输出必须为第一人称视角。
# - 输出不得包含超出所需 JSON 格式的其他文本、解释或附加信息。
# - 不要使用```json```来封装内容。
# ## 补充信息
# - 请以你的目标为中心，全面考虑你的喜好与性格倾向，战场状态等因素制定你的计划。
# - 确保你的言行符合游戏规则和设定。
# - 使用技能时会消耗行动力。行动力归0后本回合无法继续行动。
# - 被动技能只有在满足触发条件时才能使用。无法主动使用。
# - HP归零，被击败的目标无法成为技能的目标。
# """
