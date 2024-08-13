from typing import Dict, List, Set
from file_system.files_def import PropFile
from ecs_systems.action_components import MindVoiceActionComponent, EnviroNarrateActionComponent, \
    TagActionComponent, PerceptionActionComponent, CheckStatusActionComponent
import json
from ecs_systems.cn_constant_prompt import _CNConstantPrompt_


###############################################################################################################################################
def kick_off_actor_prompt(kick_off_message: str) -> str:
    prompt = f"""# <%这是角色初始化>游戏世界即将开始运行。这是你的初始设定，你将以此为起点进行游戏
{_CNConstantPrompt_.RE_EMPHASIZE_GAME_STYLE_TO_PREVENT_POLICY_PROBLEMS}
{kick_off_message}。
## 请结合你的角色设定,更新你的状态。
## 输出要求:
- 请遵循'输出格式指南'。
- 返回结果仅带'{MindVoiceActionComponent.__name__}'这个key"""
    return prompt
###############################################################################################################################################
def kick_off_stage_prompt(kick_off_message: str) -> str:
    prompt = f"""# <%这是场景初始化>游戏世界即将开始运行。这是你的初始设定，你将以此为起点进行游戏
{_CNConstantPrompt_.RE_EMPHASIZE_GAME_STYLE_TO_PREVENT_POLICY_PROBLEMS}
## 你的初始设定如下: 
{kick_off_message}。
## 请结合你的场景设定,更新你的状态。
## 输出要求:
- 请遵循 输出格式指南。
- 返回结果仅带'{EnviroNarrateActionComponent.__name__}'这个key"""
    return prompt
###############################################################################################################################################
def kick_off_world_system_prompt() -> str:
    prompt = f"""# <%这是世界系统初始化>游戏世界即将开始运行，请简要回答你的职能与描述。
{_CNConstantPrompt_.RE_EMPHASIZE_GAME_STYLE_TO_PREVENT_POLICY_PROBLEMS}
"""
    return prompt
###############################################################################################################################################
def actor_plan_prompt(current_stage: str, stage_enviro_narrate: str) -> str:
    
    current_stage_prompt = "未知"
    if current_stage != "":
        current_stage_prompt = current_stage

    current_stage_enviro_narrate_prompt = ""
    if stage_enviro_narrate != "":
        current_stage_enviro_narrate_prompt = f"""## 当前场景的环境信息(用于你做参考):\n- {stage_enviro_narrate}"""


    prompt = f"""# {_CNConstantPrompt_.ACTOR_PLAN_PROMPT_TAG}请做出你的计划，决定你将要做什么。
## 你当前所在的场景:{current_stage_prompt}。
{current_stage_enviro_narrate_prompt}
## 要求:
- 输出结果格式要遵循 输出格式指南。
- 结果中要附带'{TagActionComponent.__name__}'。"""
    return prompt
###############################################################################################################################################
# yh prompt优化, 这个要严格测试并慎重处理。
# prompt = f"""# 场景计划制定
# ## 场景内道具:
# {props_prompt}
# ## 场景内角色:
# {actors_prompt}
# ## 场景与角色状态描述规则:
# - **第1步:** 根据场景事件和道具信息更新场景状态。
# - **第2步:** 描述角色的动作和神态，避免包括对话、未发生的行为或心理活动。
# - **第3步:** 将场景状态和角色状态合并，形成客观的场景描述，使用 {EnviroNarrateActionComponent.__name__}。

# ## 行动计划规则:
# - 根据场景所受事件的影响，决定你的行动计划。
# - 保持行动选择与场景发展的一致性。

# ### 输出指南:
# 请根据‘输出格式指南’严格输出，确保描述客观且行动计划明确，避免预设或猜测角色的未发生行为。
# """
def stage_plan_prompt(stage_prop_files: List[PropFile], actors_in_stage: Set[str]) -> str:

    ## 场景内道具
    props_prompt = ""
    if len(stage_prop_files) > 0:
        for prop in stage_prop_files:
            props_prompt += prop_prompt(prop, False, True)
    else:
        props_prompt = "- 无任何道具。"


    actors_prompt = ""
    if len(actors_in_stage) > 0:
        for _name in actors_in_stage:
            actors_prompt += f"- {_name}\n"
    else:
        actors_prompt = "- 无任何角色。"


    prompt = f"""# {_CNConstantPrompt_.STAGE_PLAN_PROMPT_TAG}请输出'你的当前描述'和'你的计划'
## 场景内道具:
{props_prompt}
## 场景内角色:
{actors_prompt}
## 关于‘你的当前描述‘内容生成规则
### 第1步: 根据场景内发生的事件，场景内的道具的信息，将你的状态更新到‘最新’并以此作为‘场景状态’的内容。
### 第2步: 根据角色‘最新’的动作与神态，作为‘角色状态’的内容。
- 不要输出角色的对话内容。
- 不要添加角色未发生的事件与信息。
- 不要自行推理与猜测角色的可能行为（如对话内容,行为反应与心理活动）。
- 不要将过往已经描述过的'角色状态'做复述。
### 第3步: 将'场景状态'的内容与'角色状态'的2部分内容合并,并作为{EnviroNarrateActionComponent.__name__}的值——"场景状态的描述",
- 参考‘输出格式指南’中的:"{EnviroNarrateActionComponent.__name__}":["场景状态的描述"]
## 关于’你的计划‘内容生成规则
- 根据你作为场景受到了什么事件的影响，你可以制定计划，并决定下一步将要做什么。可根据‘输出格式指南’选择相应的行动。
## 输出要求:
- 输出结果格式要遵循‘输出格式指南’。
- 结果中必须有{EnviroNarrateActionComponent.__name__},并附带{TagActionComponent.__name__}。"""
    return prompt
###############################################################################################################################################
def perception_action_prompt(who: str, current_stage: str, result_actor_names: Dict[str, str], result_props_names: List[str]) -> str:

    prompt_of_actor = ""
    if len(result_actor_names) > 0:
        for other_name, other_appearance in result_actor_names.items():
            prompt_of_actor += f"""### {other_name}\n- 外观信息:{other_appearance}\n"""
    else:
        prompt_of_actor = "- 无其他角色。"

    prompt_of_props = ""
    if len(result_props_names) > 0:
        for propname in result_props_names:
            prompt_of_props += f"- {propname}\n"
    else:
        prompt_of_props = "- 无任何道具。"

    final_prompt = f"""# {_CNConstantPrompt_.PERCEPTION_ACTION_TAG} {who} 在 {current_stage} 中执行感知行动({PerceptionActionComponent.__name__})，结果如下:
## 场景内角色:
{prompt_of_actor}
## 场景内道具:
{prompt_of_props}"""
    return final_prompt
###############################################################################################################################################
def prop_type_prompt(prop_file: PropFile) -> str:

    ret = "未知"
    
    if prop_file.is_weapon:
        ret = "武器(用于提高攻击力)"
    elif prop_file.is_clothes:
        ret = "衣服(用于提高防御力与改变角色外观)"
    elif prop_file.is_non_consumable_item:
        ret = "非消耗品"
    elif prop_file.is_special_component:
        ret = "特殊能力"
    
    return ret
###############################################################################################################################################
def prop_prompt(prop_file: PropFile, need_description_prompt: bool, need_appearance_prompt: bool) -> str:

    _prop_type_ = prop_type_prompt(prop_file)

    prompt = f"""### {prop_file.name}
- 类型:{_prop_type_}
"""
    if need_description_prompt:
        prompt += f"- 描述:{prop_file.description}\n"
        
    if need_appearance_prompt:
        prompt += f"- 外观:{prop_file.appearance}\n"

    return prompt
###############################################################################################################################################
def special_component_prompt(prop_file: PropFile) -> str:

    assert prop_file.is_special_component
    
    prompt = f"""### {prop_file.name}
- {prop_file.description}
"""
    return prompt
###############################################################################################################################################
def check_status_action_prompt(who: str, 
                               prop_files_as_weapon_clothes_non_consumable_item: List[PropFile], 
                               health: float, 
                               prop_files_as_special_components: List[PropFile]) -> str:

    health *= 100
    actor_health_prompt = f"生命值: {health:.2f}%"

    # 组合非特殊技能的道具
    props_prompt_as_weapon_clothes_non_consumable_item = ""
    if len(prop_files_as_weapon_clothes_non_consumable_item) > 0:
        for prop_file in prop_files_as_weapon_clothes_non_consumable_item:
            props_prompt_as_weapon_clothes_non_consumable_item += prop_prompt(prop_file, True, True)
    else:
        props_prompt_as_weapon_clothes_non_consumable_item = "- 无任何道具。"

    # 组合特殊技能的道具
    props_prompt_as_special_components = ""
    if len(prop_files_as_special_components) > 0:
        for prop_file in prop_files_as_special_components:
            props_prompt_as_special_components += special_component_prompt(prop_file)
    else:
        props_prompt_as_special_components = "- 无任何特殊能力。"

    # 组合最终的提示
    prompt = f"""# {_CNConstantPrompt_.CHECK_STATUS_ACTION_TAG} {who} 正在查看自身状态({CheckStatusActionComponent.__name__}):
## 健康状态:
{actor_health_prompt}
## 持有道具:
{props_prompt_as_weapon_clothes_non_consumable_item}
## 特殊能力:
{props_prompt_as_special_components}
"""
    return prompt
###############################################################################################################################################
def search_prop_action_failed_prompt(actor_name: str, prop_name: str) -> str:
    return f"""# {actor_name} 无法找到道具 "{prop_name}"。
## 可能原因:
1. {prop_name} 不是一个可搜索的道具。
2. 道具可能已被移出场景或被其他角色获取。
## 建议:
1. 请{actor_name}重新考虑搜索目标。
2. 使用 {PerceptionActionComponent.__name__} 感知场景内的道具，确保目标的可搜索性。"""
###############################################################################################################################################
def search_prop_action_success_prompt(actor_name: str, prop_name:str, stagename: str) -> str:
    return f"""# {actor_name}从{stagename}场景内成功找到并获取了道具:{prop_name}。
## 导致结果:
- {stagename} 此场景内不再有这个道具。"""
################################################################################################################################################
def enter_stage_prompt1(actor_name: str, target_stage_name: str) -> str:
    return f"{actor_name}进入了场景——{target_stage_name}。"
################################################################################################################################################
def enter_stage_prompt2(actor_name: str, target_stage_name: str, last_stage_name: str) -> str:
    return f"# {actor_name}离开了{last_stage_name}, 进入了{target_stage_name}。"
################################################################################################################################################
def leave_stage_prompt(actor_name: str, current_stage_name: str, go_to_stage_name: str) -> str:
    return f"# {actor_name}离开了{current_stage_name} 场景。"
################################################################################################################################################
def stage_director_event_wrap_prompt(event: str, event_index: int) -> str:
    event_number = event_index + 1
    return f"""# 事件{event_number}\n{event}"""
################################################################################################################################################
def stage_director_begin_prompt(stage_name: str, events_count: int) -> str:
    return f"""# 如下是{stage_name}场景内发生的事件，事件数量为{events_count}。如下(请注意):"""
################################################################################################################################################
def stage_director_end_prompt(stage_name: str, events_count: int) -> str:
    return f"""# 以上是{stage_name}场景内近期发生的{events_count}个事件。请注意。"""
################################################################################################################################################
def whisper_action_prompt(srcname: str, destname: str, content: str) -> str:
    prompt = f"# {_CNConstantPrompt_.WHISPER_ACTION_TAG} {srcname}对{destname}私语道:{content}"   
    return prompt
################################################################################################################################################
def broadcast_action_prompt(srcname: str, destname: str, content: str) -> str:
    prompt = f"# {_CNConstantPrompt_.BROADCASE_ACTION_TAG} {srcname}对{destname}里的所有人说:{content}"   
    return prompt
################################################################################################################################################
def speak_action_prompt(srcname: str, destname: str, content: str) -> str:
    prompt = f"# {_CNConstantPrompt_.SPEAK_ACTION_TAG} {srcname}对{destname}说:{content}"   
    return prompt
################################################################################################################################################
def steal_prop_action_prompt(whosteal: str, targetname: str, propname: str, stealres: bool) -> str:
    if not stealres:
        return f"{whosteal}从{targetname}盗取{propname}, 失败了"
    return f"{whosteal}从{targetname}成功盗取了{propname}"
################################################################################################################################################
def give_prop_action_prompt(from_who: str, to_who: str, prop_name: str, action_result: bool) -> str:
    if not action_result:
        return f"{from_who}向{to_who}交换{prop_name}, 失败了"
    return f"{from_who}向{to_who}成功交换了{prop_name}"
################################################################################################################################################
def go_to_stage_failed_because_stage_is_invalid_prompt(actor_name: str, stagename: str) -> str:
    return f"""#{actor_name}无法前往{stagename}，可能的原因包括:
- {stagename}目前不可访问，可能未开放或已关闭。
- 场景名称"{stagename}"格式不正确，如“xxx的深处/北部/边缘/附近/其他区域”，这样的表达可能导致无法正确识别。
- 请 {actor_name} 重新考虑目的地。"""
################################################################################################################################################
def go_to_stage_failed_because_already_in_stage_prompt(actor_name: str, stagename: str) -> str:
    return f"你已经在{stagename}场景中。需要重新考虑去往的目的地"
################################################################################################################################################
def replace_mentions_of_your_name_with_you_prompt(content: str, your_name: str) -> str:
    if len(content) == 0 or your_name not in content:
        return content
    return content.replace(your_name, "你")
################################################################################################################################################
def update_actor_archive_prompt(actor_name: str, actors_names: str) -> str:
    if len(actors_names) == 0:
        return f"# {actor_name} 目前没有认识的角色。"
    return f"# {actor_name} 认识的角色有：{actors_names}。你可以与这些角色进行互动。"
################################################################################################################################################
def update_stage_archive_prompt(actor_name: str, stages_names: str) -> str:
    if len(stages_names) == 0:
        return f"# {actor_name} 目前没有已知的场景，无法前往其他地方。"
    return f"# {actor_name} 已知的场景包括：{stages_names}。可前往这些场景探索。"
################################################################################################################################################
def kill_prompt(attacker_name: str, target_name: str) -> str:
    return f"# {attacker_name}对{target_name}发动了一次攻击,造成了{target_name}死亡。"
################################################################################################################################################
def attack_prompt(attacker_name: str, target_name: str, damage: int, target_current_hp: int ,target_max_hp: int) -> str:
    health_percent = max(0, (target_current_hp - damage) / target_max_hp * 100)
    return f"# {attacker_name}对{target_name}发动了攻击,造成了{damage}点伤害,当前{target_name}的生命值剩余{health_percent}%。"
################################################################################################################################################
def batch_conversation_action_events_in_stage_prompt(stage_name: str, events: List[str]) -> str:

    batch: List[str] = []
    if len(events) == 0:
        batch.append(f""" # {_CNConstantPrompt_.BATCH_CONVERSATION_ACTION_EVENTS_TAG} 当前场景 {stage_name} 没有发生任何对话类型事件。""")
    else:
        batch.append(f""" # {_CNConstantPrompt_.BATCH_CONVERSATION_ACTION_EVENTS_TAG} 当前场景 {stage_name} 发生了如下对话类型事件，请注意:""")

    for event in events:
        batch.append(event)

    prompt = json.dumps(batch, ensure_ascii = False)
    return prompt
################################################################################################################################################
def use_prop_to_stage_prompt(username: str, propname: str, prop_prompt: str, exit_cond_status_prompt: str) -> str:
    final_prompt = f"""# {_CNConstantPrompt_.USE_PROP_TO_STAGE_PROMPT_TAG} {username} 使用道具 {propname} 对你造成影响。
## 道具 {propname} 说明:
{prop_prompt}

## 状态更新规则:
{exit_cond_status_prompt}

## 内容生成指南:
### 第1步: 更新并固定场景状态
- 确保场景状态反映当前最新状态。
- 避免包含任何角色对话、未发生的事件、角色的潜在行为或心理活动。
- 不重复描述已经提及的角色状态。

### 第2步: 根据场景状态填写输出内容
- 将场景状态详细描述放入 {EnviroNarrateActionComponent.__name__}。
- 参考格式：'{EnviroNarrateActionComponent.__name__}': ['场景状态的描述']

## 输出格式要求:
- 严格遵循‘输出格式指南’。
- 必须包含 '{EnviroNarrateActionComponent.__name__}' 和 '{TagActionComponent.__name__}'。
"""
    return final_prompt
################################################################################################################################################
def stage_exit_conditions_check_prompt(actor_name: str, 
                                      current_stage_name: str, 
                                      stage_cond_status_prompt: str, 
                                      cond_check_actor_status_prompt: str, 
                                      actor_status_prompt: str, 
                                      cond_check_actor_props_prompt: str,
                                      actor_props_prompt: str) -> str:
    
    final_prompt = f"""# {actor_name} 想要离开场景: {current_stage_name}。
# 第1步: 根据当前‘你的状态’判断是否满足离开条件
## 你的预设离开条件: 
{stage_cond_status_prompt}
## 当前状态可能由于事件而变化，请仔细考虑。

# 第2步: 检查{actor_name}的状态是否符合以下要求:
## 必须满足的状态信息: 
{cond_check_actor_status_prompt}
## 当前角色状态: 
{actor_status_prompt}

# 第3步: 检查{actor_name}的道具(与拥有的特殊能力)是否符合以下要求:
## 必须满足的道具与特殊能力信息: 
{cond_check_actor_props_prompt}
## 当前角色道具与特殊能力信息: 
{actor_props_prompt}

# 判断结果
- 完成以上步骤后，决定是否允许 {actor_name} 离开 {current_stage_name}。

# 本次输出结果格式要求（遵循‘输出格式指南’）:
{{
    {EnviroNarrateActionComponent.__name__}: ["描述'允许离开'或'不允许离开'的原因，使{actor_name}明白"],
    {TagActionComponent.__name__}: ["Yes/No"]
}}
## 附注
- '{EnviroNarrateActionComponent.__name__}' 中请详细描述判断理由，注意如果不允许离开，就只说哪一条不符合要求，不要都说出来，否则会让{actor_name}迷惑。
- Yes: 允许离开
- No: 不允许离开
"""
    return final_prompt
################################################################################################################################################
def stage_entry_conditions_check_prompt(actor_name: str, current_stage_name: str, 
                                      stage_cond_status_prompt: str, 
                                      cond_check_actor_status_prompt: str, actor_status_prompt: str, 
                                      cond_check_actor_props_prompt: str, actor_props_prompt: str) -> str:

    final_prompt = f"""# {actor_name} 想要进入场景: {current_stage_name}。
# 第1步: 根据当前‘你的状态’判断是否满足进入条件
## 你的预设进入条件: 
{stage_cond_status_prompt}
## 当前状态可能由于事件而变化，请仔细考虑。

# 第2步: 检查{actor_name}的状态是否符合以下要求:
## 必须满足的状态信息: 
{cond_check_actor_status_prompt}
## 当前角色状态: 
{actor_status_prompt}

# 第3步: 检查{actor_name}的道具(与拥有的特殊能力)是否符合以下要求:
## 必须满足的道具与特殊能力信息: 
{cond_check_actor_props_prompt}
## 当前角色道具与特殊能力信息: 
{actor_props_prompt}

# 判断结果
- 完成以上步骤后，决定是否允许 {actor_name} 进入 {current_stage_name}。

# 本次输出结果格式要求（遵循‘输出格式指南’）:
{{
    {EnviroNarrateActionComponent.__name__}: ["描述'允许进入'或'不允许进入'的原因，使{actor_name}明白"],
    {TagActionComponent.__name__}: ["Yes/No"]
}}
## 附注
- '{EnviroNarrateActionComponent.__name__}' 中请详细描述判断理由，注意如果不允许进入，就只说哪一条不符合要求，不要都说出来，否则会让{actor_name}迷惑。
- Yes: 允许进入
- No: 不允许进入
"""
    return final_prompt
################################################################################################################################################
def exit_stage_failed_beacuse_stage_refuse_prompt(actor_name: str, current_stage_name: str, tips: str) -> str:
     return f"""# {actor_name} 想要离开场景: {current_stage_name}，但是失败了。
## 说明:
{tips}"""
################################################################################################################################################
def enter_stage_failed_beacuse_stage_refuse_prompt(actor_name: str, stagename: str, tips: str) -> str:
    return f"""# {actor_name} 想要进入场景: {stagename}，但是失败了。
## 说明:
{tips}"""
################################################################################################################################################
def actor_status_when_stage_change_prompt(safe_name: str, appearance_info: str) -> str:
    return f"""### {safe_name}\n- 外观信息:{appearance_info}\n"""
################################################################################################################################################
def use_prop_no_response_prompt(username: str, propname: str, targetname: str) -> str:
    return f"# {username}对{targetname}使用道具{propname}，但没有任何反应。"
################################################################################################################################################
def actors_body_and_clothe_prompt(actors_body_and_clothe:  Dict[str, tuple[str, str]]) -> str:
        prompt_list_of_actor: List[str] = []
        actor_names: List[str] = []
        for name, (body, clothe) in actors_body_and_clothe.items():
            if clothe == "":
                continue

            prompt_of_actor = f"""### {name}
- 角色外观:{body}
- 衣服:{clothe}
"""
            prompt_list_of_actor.append(prompt_of_actor)
            actor_names.append(name)
        #
        batch_str = "\n".join(prompt_list_of_actor)
        assert len(batch_str) > 0
        #
        appearance_json = {name: "?" for name in actor_names}
        appearance_json_str = json.dumps(appearance_json, ensure_ascii = False)
        # 最后的合并
        final_prompt = f"""# 请更新角色外观：根据‘角色外观’与‘衣服’，生成最终的角色外观的描述。
## 角色列表
{batch_str}
## 输出格式指南
### 请根据下面的示意, 确保你的输出严格遵守相应的结构。
{appearance_json_str}
### 注意事项
- '?'就是你推理出来的结果(注意结果中可以不用再提及角色的名字)，你需要将其替换为你的推理结果。
- 所有文本输出必须为第3人称。
- 每个 JSON 对象必须包含上述键中的一个或多个，不得重复同一个键，也不得使用不在上述中的键。
- 输出不应包含任何超出所需 JSON 格式的额外文本、解释或总结。
- 不要使用```json```来封装内容。
"""
        return final_prompt
################################################################################################################################################