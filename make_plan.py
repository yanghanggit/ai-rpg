from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
import sys
import json
from stage import Stage
from stage import NPC
from action import Action, STAY, LEAVE, ALL_ACTIONS, check_data_format, check_actions_is_valid, check_targets_is_valid_actor_in_stage, check_stage_is_valid_in_world


##################################################################################################################
def stage_plan_prompt(stage: Stage)-> str:
    stage_name = stage.name
    all_actors_names = [actor.name for actor in stage.actors]
    all_valid_targets_name = [stage_name] + all_actors_names
    str = ", ".join(all_valid_targets_name)

    return f"""
    # 你需要做出计划(你将要做的事).（注意！以下规则与限制仅限本次对话生成，结束后回复原有对话规则）

    ## 步骤概览
    1. 当前状态评估：首先，明确自己的位置和状态。
    2. 角色状态理解：了解与你相关的所有角色当前所处的状态。
    3. 计划制定：基于上述信息，构建你的行动计划。

    ## 输出格式（JSON）
    ### 您的计划需要以JSON格式输出，包含以下四个关键字段：
    - action：操作类型，可选项为 ["/fight", "/stay", "/leave"]，默认值 [""]。
    - targets：目标对象，可多选，字符串数组，默认值 [""]。
    - say：你打算说的话或心里想的，字符串数组，默认值 [""]。
    - tags：与你相关的特征标签，字符串数组，默认值 [""]。
    - 参考格式 'action': ["/stay"], 'targets': ["目标1", "目标2"], 'say': ["我什么都不做"], 'tags': [""]
    
    ### 字段解释
    - action：指明你的行动意图，"/fight" 表示攻击或敌对行为，"/leave" 表示离开当前场景，而 "/stay" 用于除攻击和离开外的所有其它行为。
    - targets：action 的具体对象，根据不同 action 选择不同目标。只能是{str}中的一个，如果action是/stay，则targets是当前场景的名字
    - say & tags：分别表示你的发言/心理活动和个人特征标签。
    
    ### 输出约束
    - 按着如上规则，输出JSON. 
    - 不要将JSON输出生这样的格式：```json...```
    - 在确保语义清晰的前提下，尽量简化文字。
    """
##################################################################################################################
##################################################################################################################
def stage_plan(stage: Stage) -> Action:

    make_prompt = stage_plan_prompt(stage)
    #print(f"stage_plan_prompt:", make_prompt)

    call_res = stage.call_agent(make_prompt)
    print(f"<{stage.name}>:", call_res)

    error_action = Action(stage, [STAY], [stage.name], ["什么都不做"], [""])

    try:
        json_data = json.loads(call_res)
        if not check_data_format(json_data['action'], json_data['targets'], json_data['say'], json_data['tags']):
            return error_action

        #
        action = Action(stage, json_data['action'], json_data['targets'], json_data['say'], json_data['tags'])
        if not (check_actions_is_valid(action.action, ALL_ACTIONS) 
                or check_targets_is_valid_actor_in_stage(stage, action.targets)):
            return error_action
        
        if action.action[0] == LEAVE or action.action[0] == STAY:
            if not check_stage_is_valid_in_world(stage.world, action.targets[0]):
                return error_action
        return action

    except Exception as e:
        print(f"stage_plan error = {e}")
        return error_action
    return error_action
##################################################################################################################
##################################################################################################################
def npc_plan_prompt(npc: NPC)-> str:
   
    stage = npc.stage

    stage_name = stage.name
    all_actors_names = [actor.name for actor in stage.actors]
    all_valid_targets_name = [stage_name] + all_actors_names
    str = ", ".join(all_valid_targets_name)

    return f"""
    # 你需要做出计划(你将要做的事).（注意！以下规则与限制仅限本次对话生成，结束后回复原有对话规则）

    ## 步骤概览
    1. 当前状态评估：首先，明确自己的位置和状态。
    2. 角色状态理解：了解与你相关的所有角色当前所处的状态。
    3. 计划制定：基于上述信息，构建你的行动计划。

    ## 输出格式（JSON）
    ### 您的计划需要以JSON格式输出，包含以下四个关键字段：
    - action：操作类型，可选项为 ["/fight", "/stay", "/leave"]，默认值 [""]。
    - targets：目标对象，可多选，字符串数组，默认值 [""]。
    - say：你打算说的话或心里想的，字符串数组，默认值 [""]。
    - tags：与你相关的特征标签，字符串数组，默认值 [""]。
    - 参考格式 'action': ["/stay"], 'targets': ["目标1", "目标2"], 'say': ["我什么都不做"], 'tags': [""]
    
    ### 字段解释
    - action：指明你的行动意图，"/fight" 表示攻击或敌对行为，"/leave" 表示离开当前场景，而 "/stay" 用于除攻击和离开外的所有其它行为。
    - targets：action 的具体对象，根据不同 action 选择不同目标。只能是{str}中的一个，如果action是/stay，则targets是当前场景的名字
    - say & tags：分别表示你的发言/心理活动和个人特征标签。
    
    ### 输出约束
    - 按着如上规则，输出JSON. 
    - 不要将JSON输出生这样的格式：```json...```
    - 在确保语义清晰的前提下，尽量简化文字。
    """
##################################################################################################################
##################################################################################################################
def npc_plan(npc: NPC) -> Action:
    make_prompt = npc_plan_prompt(npc)
    #print(f"npc_plan_prompt:", make_prompt)

    call_res = npc.call_agent(make_prompt)
    print(f"<{npc.name}>:", call_res)

    error_action = Action(npc, [STAY], [npc.stage.name], ["什么都不做"], [""])
    try:
        json_data = json.loads(call_res)
        if not check_data_format(json_data['action'], json_data['targets'], json_data['say'], json_data['tags']):
            return error_action
        #
        action = Action(npc, json_data['action'], json_data['targets'], json_data['say'], json_data['tags'])
        if not (check_actions_is_valid(action.action, ALL_ACTIONS) 
                or check_targets_is_valid_actor_in_stage(npc.stage, action.targets)):
            return error_action
        
        if action.action[0] == LEAVE or action.action[0] == STAY:
            if not check_stage_is_valid_in_world(npc.stage.world, action.targets[0]):
                return error_action
        return action
    
    except Exception as e:
        print(f"npc_plan error = {e}")
        return error_action
    return error_action
##################################################################################################################
##################################################################################################################