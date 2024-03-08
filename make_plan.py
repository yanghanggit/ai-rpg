from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
import sys
import json
from stage import Stage
from stage import NPC
from action import Action, STAY, LEAVE, ALL_ACTIONS, check_data_format, check_actions_is_valid, check_targets_is_valid_actor_in_stage, check_stage_is_valid_in_world

##################################################################################################################
##################################################################################################################
#场景需要根据状态做出计划
def stage_plan_prompt(stage: Stage)-> str:
    return f"""
    # 你需要做出计划
    ## 步骤
    - 第1步：理解你的当前状态。
    - 第2步：理解场景内所有角色的当前状态。
    - 第3步：输出你的计划。

    ## 输出规则（最终输出为JSON）：
    - 你的输出必须是一个JSON，包括action, targets, say, tags四个字段。
    - action: 默认是[""]，只能是["/fight", "/stay", "/leave"]中的一个（即都是字符串）。
    - targets: 默认是[""]，可以是多个，即都是字符串
    - say: 默认是[""]，可以是多个，即都是字符串
    - tags: 默认是[""]，可以是多个，即都是字符串
    - 参考格式 'action': ["/stay"], 'targets': ["目标1", "目标2"], 'say': ["我什么都不做"], 'tags': ["我是一个场景"]
   
    ### action与targets说明
    - "/fight"：代表你想对某个角色发动攻击或者敌意行为，targets是场景内某个角色的名字
    - "/leave"：代表你想离开本场景，targets是你知道的这个在这个世界某个地点的名字
    - 关于"/stay"：除了"/fight"，"/leave"，之外的其他行为都是"/stay"，代表你想保持现状, targets是你所在这个场景的名字（如果你自己就是场景，那就是你的名字）

    ### say与tags说明
    - say:是你想要说的话(或者心里活动)
    - tags:是你的特点

    ## 输出限制：
    - 按着如上规则，输出JSON. 不要将JSON输出生这样的格式：```json...```
    - 不要推断，增加与润色。
    - 输出在保证语意完整基础上字符尽量少。
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
#场景需要根据状态做出计划
def npc_plan_prompt(npc: NPC)-> str:
    return f"""
    # 你需要做出计划（即你想要做的事还没做）  
      
    ## 步骤
    - 第1步：理解你自身当前状态。
    - 第2步：理解你的场景内所有角色的当前状态。
    - 第3步：输出你需要做出计划。

    ## 输出规则（最终输出为JSON）：
    - 你的输出必须是一个JSON，包括action, targets, say, tags四个字段。
    - action: 默认是[""]，只能是["/fight", "/stay", "/leave"]中的一个（即都是字符串）。
    - targets: 默认是[""]，可以是多个，即都是字符串
    - say: 默认是[""]，可以是多个，即都是字符串
    - tags: 默认是[""]，可以是多个，即都是字符串
    - 参考格式 'action': ["/stay"], 'targets': ["目标1", "目标2"], 'say': ["我什么都不做"], 'tags': ["我是一个场景"]
   
    ### action与targets说明
    - "/fight"：代表你想对某个角色发动攻击或者敌意行为，targets是场景内某个角色的名字
    - "/leave"：代表你想离开本场景，targets是你知道的这个在这个世界某个地点的名字
    - 关于"/stay"：除了"/fight"，"/leave"，之外的其他行为都是"/stay"，代表你想保持现状, targets是你所在这个场景的名字（如果你自己就是场景，那就是你的名字）

    ### say与tags说明
    - say:是你想要说的话(或者心里活动)
    - tags:是你的特点

    ## 输出限制：
    - 按着如上规则，输出JSON. 不要将JSON输出生这样的格式：```json...```
    - 输出在保证语意完整基础上字符尽量少。
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