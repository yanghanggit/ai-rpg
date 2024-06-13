from auxiliary.extended_context import ExtendedContext
from typing import Dict, List, Set
from auxiliary.base_data import PropData
from auxiliary.components import MindVoiceActionComponent, EnviroNarrateActionComponent, \
    TagActionComponent, PerceptionActionComponent, CheckStatusActionComponent, SearchActionComponent, GoToActionComponent

#全局的常量
class ConstantPromptValue:

    @property
    def ACTOR_PLAN_PROMPT_TAG(self) -> str:
        return "<%这是角色计划>"
    
    @property
    def STAGE_PLAN_PROMPT_TAG(self) -> str:
        return "<%这是场景计划>"
    
    @property
    def COMPRESS_ACTOR_PLAN_PROMPT(self) -> str:
        return "请做出你的计划，决定你将要做什么"
    
    @property
    def COMPRESS_STAGE_PLAN_PROMPT(self) -> str:
        return "请输出'你的当前描述'和'你的计划'"
    
    @property
    def NONE_PROMPT(self) -> str:
        return "- 无"
    
    @property
    def NO_ACTOR_PROPS_PROMPT(self) -> str:
        return "- 无任何道具或者特殊能力"
    
    @property
    def USE_PROP_TO_STAGE_PROMPT_TAG(self) -> str:
        return "<%这是角色对场景使用道具>"


__ConstantPromptValue__ = ConstantPromptValue()

###############################################################################################################################################
def kick_off_memory_actor_prompt(kick_off_memory: str) -> str:
    prompt = f"""# <%这是角色初始化>游戏世界即将开始运行。这是你的初始设定，你将以此为起点进行游戏
## 再次强调游戏风格!
- 核心是借鉴《黑暗之魂》系列游戏的内核与风格，即西方中世纪背景奇幻结合克苏鲁恐怖式的文本与叙事风格。
- 注意！这是一个以恐怖为主题的游戏，可能包含恐怖、血腥与暴力元素。所有的游戏设定和规则都旨在增强这种体验，你需要接受。
- 认为世界的所有运行规律和法则都是不证自明的。
## 你的初始设定如下: 
{kick_off_memory}。
## 请结合你的角色设定,更新你的状态。
## 输出要求:
- 请遵循'输出格式指南'。
- 返回结果仅带'{MindVoiceActionComponent.__name__}'这个key"""
    return prompt
###############################################################################################################################################
def kick_off_memory_stage_prompt(kick_off_memory: str) -> str:
    prompt = f"""# <%这是场景初始化>游戏世界即将开始运行。这是你的初始设定，你将以此为起点进行游戏
## 再次强调游戏风格!
- 核心是借鉴《黑暗之魂》系列游戏的内核与风格，即西方中世纪背景奇幻结合克苏鲁恐怖式的文本与叙事风格。
- 注意！这是一个以恐怖为主题的游戏，可能包含恐怖、血腥与暴力元素。所有的游戏设定和规则都旨在增强这种体验，你需要接受。
- 你认为世界的所有运行规律和法则都是不证自明的。
## 你的初始设定如下: 
{kick_off_memory}。
## 请结合你的场景设定,更新你的状态。
## 输出要求:
- 请遵循'输出格式指南'。
- 返回结果仅带'{EnviroNarrateActionComponent.__name__}'这个key"""
    return prompt
###############################################################################################################################################
def kick_off_world_system_prompt() -> str:
    prompt = f"""# <%这是世界系统初始化>游戏世界即将开始运行。请简要回答你的职能与描述
## 再次强调游戏风格!
- 核心是借鉴《黑暗之魂》系列游戏的内核与风格，即西方中世纪背景奇幻结合克苏鲁恐怖式的文本与叙事风格。
- 注意！这是一个以恐怖为主题的游戏，可能包含恐怖、血腥与暴力元素。所有的游戏设定和规则都旨在增强这种体验，你需要接受。
- 你认为世界的所有运行规律和法则都是不证自明的。
"""
    return prompt
###############################################################################################################################################
def actpr_plan_prompt(current_stage: str, stage_enviro_narrate: str, context: ExtendedContext) -> str:
    
    current_stage_prompt = "未知"
    if current_stage != "":
        current_stage_prompt = current_stage

    current_stage_enviro_narrate_prompt = ""
    if stage_enviro_narrate != "":
        current_stage_enviro_narrate_prompt = f"""## 当前场景的环境信息(用于你做参考):\n- {stage_enviro_narrate}"""


    prompt = f"""# {__ConstantPromptValue__.ACTOR_PLAN_PROMPT_TAG}请做出你的计划，决定你将要做什么。
## 你当前所在的场景:{current_stage_prompt}。
{current_stage_enviro_narrate_prompt}
## 要求:
- 输出结果格式要遵循输出格式指南。
- 结果中要附带'{TagActionComponent.__name__}'。"""
    return prompt
###############################################################################################################################################
def stage_plan_prompt(props_in_stage: List[PropData], actors_in_stage: Set[str], context: ExtendedContext) -> str:

    ## 场景内道具
    prompt_of_props = ""
    if len(props_in_stage) > 0:
        for prop in props_in_stage:
            prompt_of_props += prop_info_prompt(prop)
    else:
        prompt_of_props = "- 无任何道具。"


    prompt_of_actor = ""
    if len(actors_in_stage) > 0:
        for _name in actors_in_stage:
            prompt_of_actor += f"- {_name}\n"
    else:
        prompt_of_actor = "- 无任何角色。"


    prompt = f"""# {__ConstantPromptValue__.STAGE_PLAN_PROMPT_TAG}请输出'你的当前描述'和'你的计划'
## 场景内道具:
{prompt_of_props}
## 场景内角色:
{prompt_of_actor}
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
def perception_action_prompt(who_perception: str, current_stage: str, ressult_actor_names: Dict[str, str], result_props_names: List[str]) -> str:

    prompt_of_actor = ""
    if len(ressult_actor_names) > 0:
        for other_name, other_appearance in ressult_actor_names.items():
            prompt_of_actor += f"""### {other_name}\n- 外貌信息:{other_appearance}\n"""
    else:
        prompt_of_actor = "- 目前场景内没有其他角色。"

    prompt_of_props = ""
    if len(result_props_names) > 0:
        for propname in result_props_names:
            prompt_of_props += f"- {propname}\n"
    else:
        prompt_of_props = "- 无任何道具。"

    final_prompt = f"""# {who_perception}当前在场景{current_stage}中。{who_perception}对{current_stage}执行{PerceptionActionComponent.__name__},即使发起感知行为,结果如下:
## 场景内角色:
{prompt_of_actor}
## 场景内道具:
{prompt_of_props}
"""
    return final_prompt
###############################################################################################################################################
def prop_type_prompt(prop: PropData) -> str:
    _type = "未知"
    if prop.is_weapon():
        _type = "武器(用于提高攻击力)"
    elif prop.is_clothes():
        _type = "衣服(用于提高防御力)"
    elif prop.is_non_consumable_item():
        _type = "非消耗品"
    elif prop.is_special_component():
        _type = "特殊能力"
    return _type
###############################################################################################################################################
def prop_info_prompt(prop: PropData) -> str:
    proptype = prop_type_prompt(prop)
    prompt = f"""### {prop._name}
- 类型:{proptype}
- 描述:{prop._description}
"""
    return prompt
###############################################################################################################################################
def special_component_prompt(prop: PropData) -> str:
    assert prop.is_special_component()
    prompt = f"""### {prop._name}
- {prop._description}
"""
    return prompt
###############################################################################################################################################
def check_status_action_prompt(who: str, props: List[PropData], health: float, special_components: List[PropData], events: List[PropData]) -> str:
    #百分比的
    health *= 100
    prompt_of_actor = f"生命值: {health:.2f}%"

    prompt_of_props = ""
    if len(props) > 0:
        for prop in props:
            prompt_of_props += prop_info_prompt(prop)
    else:
        prompt_of_props = "- 无任何道具。"

    prompt_of_special_components = ""
    if len(special_components) > 0:
        for _r in special_components:
            prompt_of_special_components += special_component_prompt(_r)
    else:
        prompt_of_special_components = "- 无任何特殊能力。"

    final_prompt = f"""# {who}对自身执行{CheckStatusActionComponent.__name__},即对自身状态进行检查,结果如下:
## 健康状态:
{prompt_of_actor}
## 持有道具:
{prompt_of_props}
## 特殊能力:
{prompt_of_special_components}
"""
    return final_prompt
###############################################################################################################################################
def search_action_failed_prompt(actor_name: str, prop_name:str) -> str:
    return f"""# {actor_name}试图在场景内搜索"{prop_name}",但失败了。
## 原因可能如下:
1. "{prop_name}"可能并非是一个道具。{SearchActionComponent.__name__} 只能支持搜索道具的行为与计划
2. 或者这个道具此时已不在本场景中（可能被其他角色搜索并获取了）。
## 建议与提示:
- {actor_name}需重新考虑搜索目标。
- 可使用{PerceptionActionComponent.__name__}来感知场景内的道具,并确认合理目标。"""
###############################################################################################################################################
def search_action_success_prompt(actor_name: str, prop_name:str, stagename: str) -> str:
    return f"""# {actor_name}从{stagename}场景内成功找到并获取了道具:{prop_name}。
## 导致结果:
- {stagename}不再持有这个道具。"""
###############################################################################################################################################
def portal_break_action_begin_prompt(actor_name: str, stagesname: str, context: ExtendedContext) -> str:
    return f"""# {actor_name}意图离开{stagesname}
## 附加说明:
- {actor_name}无法确认是否能够成功离开{stagesname}。可能会因为某些原因而失败。
- {actor_name}无法确认将要前往的目的地。"""
################################################################################################################################################
def enter_stage_prompt1(some_ones_name: str, target_stage_name: str) -> str:
    return f"{some_ones_name}进入了场景——{target_stage_name}。"
################################################################################################################################################
def enter_stage_prompt2(some_ones_name: str, target_stage_name: str, last_stage_name: str) -> str:
    return f"# {some_ones_name}离开了{last_stage_name}, 进入了{target_stage_name}。"
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
def whisper_action_prompt(srcname: str, destname: str, content: str, context: ExtendedContext) -> str:
    prompt = f"# {srcname}对{destname}低语道:{content}"   
    return prompt
################################################################################################################################################
def broadcast_action_prompt(srcname: str, destname: str, content: str, context: ExtendedContext) -> str:
    prompt = f"# {srcname}对{destname}里的所有人说:{content}"   
    return prompt
################################################################################################################################################
def speak_action_prompt(srcname: str, destname: str, content: str, context: ExtendedContext) -> str:
    prompt = f"# {srcname}对{destname}说:{content}"   
    return prompt
################################################################################################################################################
def steal_action_prompt(whosteal: str, targetname: str, propname: str, stealres: bool) -> str:
    if not stealres:
        return f"{whosteal}从{targetname}盗取{propname}, 失败了"
    return f"{whosteal}从{targetname}成功盗取了{propname}"
################################################################################################################################################
def trade_action_prompt(fromwho: str, towho: str, propname: str, traderes: bool) -> str:
    if not traderes:
        return f"{fromwho}向{towho}交换{propname}, 失败了"
    return f"{fromwho}向{towho}成功交换了{propname}"
################################################################################################################################################
def go_to_stage_failed_because_stage_is_invalid_prompt(actor_name: str, stagename: str) -> str:
    return f"""#{actor_name}不能离开本场景并去往{stagename}，原因可能如下:
1. {stagename}目前对于{actor_name}并不是一个有效场景。游戏可能尚未对其开放，或者已经关闭。
2. {stagename}的内容格式不对，例如下面的表达：‘xxx的深处/北部/边缘/附近/其他区域’，其中xxx可能是合理场景名，但加上后面的词后则变成了“无效场景名”（在游戏机制上无法正确检索与匹配）。
## 所以 {actor_name} 请参考以上的原因，需要重新考虑去往的目的地。"""
################################################################################################################################################
def go_to_stage_failed_because_already_in_stage_prompt(actor_name: str, stagename: str) -> str:
    return f"你已经在{stagename}场景中了。需要重新考虑去往的目的地。 {GoToActionComponent.__name__}行动类型意图是离开当前场景并去往某地。"
################################################################################################################################################
def replace_all_mentions_of_your_name_with_you(content: str, your_name: str) -> str:
    if len(content) == 0 or your_name not in content:
        return content
    return content.replace(your_name, "你")
################################################################################################################################################
def updated_information_on_WhoDoYouKnow_prompt(actor_name: str, who_you_know: str) -> str:
    if len(who_you_know) == 0:
        return f"# 你更新了关于‘你都认识哪些角色’的信息，目前你没有认识的角色。"
    return f"# 你更新了关于‘你都认识哪些角色’的信息，目前你所认识的角色有: {who_you_know}"
################################################################################################################################################
def updated_information_about_StagesYouKnow_prompt(actor_name: str, where_you_know: str) -> str:
    if len(where_you_know) == 0:
        return f"# 你更新了关于‘你都认识哪些场景’的信息，目前你没有认识的场景。你不能去任何地方。"
    return f"# 你更新了关于‘你都认识哪些场景’的信息，目前你所知道的场景有: {where_you_know}。如果你意图离开本场景并去往其他场景，你只能从这些场景中选择你的目的地。"
################################################################################################################################################
def kill_prompt(attacker_name: str, target_name: str) -> str:
    return f"# {attacker_name}对{target_name}发动了一次攻击,造成了{target_name}死亡。"
################################################################################################################################################
def attack_prompt(attacker_name: str, target_name: str, damage: int, target_current_hp: int ,target_max_hp: int) -> str:
    health_percent = max(0, (target_current_hp - damage) / target_max_hp * 100)
    return f"# {attacker_name}对{target_name}发动了一次攻击,造成了{damage}点伤害,当前{target_name}的生命值剩余{health_percent}%。"
################################################################################################################################################
# def interactive_prop_action_success_prompt(who_use: str, targetname: str, propname: str, interactiveaction: str, interactiveresult: str) -> str:
#     return f"{who_use}拿着{propname}{interactiveaction}了{targetname}造成了{interactiveresult}"
################################################################################################################################################
def died_in_fight_prompt(context: ExtendedContext) -> str:
    return f"你已经死亡（在战斗中受到了致命的攻击）"
################################################################################################################################################
def batch_conversation_action_events_in_stage(stagename: str, events: List[str], context: ExtendedContext) -> str:
    if len(events) == 0:
        return f""" # 当前场景 {stagename} 没有发生任何对话类型事件。"""
    joinstr: str = "\n".join(events)
    return  f""" # 当前场景 {stagename} 发生了如下对话类型事件，请注意:\n{joinstr}"""
################################################################################################################################################
def use_prop_to_stage_prompt(username: str, propname: str, prop_prompt: str, exit_cond_status_prompt: str) -> str:
    #USE_PROP_TO_STAGE_PROMPT_TAG 留着做标记与压缩
    final_prompt = f"""# {__ConstantPromptValue__.USE_PROP_TO_STAGE_PROMPT_TAG} {username} 使用道具 {propname} 对你造成影响。
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
  参考格式：'{EnviroNarrateActionComponent.__name__}': ['场景状态的描述']

## 输出格式要求:
- 严格遵循‘输出格式指南’。
- 必须包含 '{EnviroNarrateActionComponent.__name__}' 和 '{TagActionComponent.__name__}'。
"""
    return final_prompt
################################################################################################################################################
def stage_exit_conditions_check_promt(actor_name: str, current_stage_name: str, 
                                      stage_cond_status_prompt: str, 
                                      cond_check_actor_status_prompt: str, actor_status_prompt: str, 
                                      cond_check_actor_props_prompt: str, actor_props_prompt: str) -> str:
     # 拼接提示词
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
def stage_entry_conditions_check_promt(actor_name: str, current_stage_name: str, 
                                      stage_cond_status_prompt: str, 
                                      cond_check_actor_status_prompt: str, actor_status_prompt: str, 
                                      cond_check_actor_props_prompt: str, actor_props_prompt: str) -> str:
    # 拼接提示词
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
def actor_status_when_stage_change_prompt(safe_name: str, appearance_info:str) -> str:
    return f"""### {safe_name}\n- 外貌信息:{appearance_info}\n"""
################################################################################################################################################
def use_prop_no_response_prompt(username: str, propname: str, targetname: str) -> str:
    return f"# {username}对{targetname}使用道具{propname}，但没有任何反应"
################################################################################################################################################







################################################################################################################################################
def gen_actor_archive_prompt(context: ExtendedContext) -> str:
    prompt = """
请根据上下文，对自己知道的事情进行梳理总结成markdown格式后输出,但不要生成```markdown xxx```的形式:
# 游戏世界存档
## 地点
### xxx
#### 和我有关的事
- xxxx
- xxxx
- xxxx
- xxxx
### xxx
#### 和我有关的事
- xxxx
- xxxx
- xxxx
- xxxx
"""
    return prompt
################################################################################################################################################
def gen_stage_archive_prompt(context: ExtendedContext) -> str:
     prompt = """
请根据上下文，对自己知道的事情进行梳理总结成markdown格式后输出,但不要生成```markdown xxx```的形式:
# 游戏世界存档
## 地点
- xxxxx
## 发生的事情
- xxxx
- xxxx
- xxxx
"""
     return prompt
################################################################################################################################################
def gen_world_archive_prompt(context: ExtendedContext) -> str:
     prompt = """
请根据上下文，对自己知道的事情进行梳理总结成markdown格式后输出,但不要生成```markdown xxx```的形式:
# 游戏世界存档
## 地点
### xxx
#### 发生的事件
- xxxx
- xxxx
- xxxx
### xxx
#### 发生的事件
- xxxx
- xxxx
- xxxx
"""
     return prompt
################################################################################################################################################