from typing import Dict, List, Set, Optional
from file_system.files_def import PropFile
from gameplay_systems.action_components import (
    MindVoiceAction,
    StageNarrateAction,
    TagAction,
    PerceptionAction,
    BroadcastAction,
    BroadcastAction,
    SpeakAction,
    WhisperAction,
)
import json
from gameplay_systems.cn_constant_prompt import _CNConstantPrompt_ as ConstantPrompt


###############################################################################################################################################
def make_kick_off_actor_prompt(
    kick_off_message: str, about_game: str, game_round: int
) -> str:

    prompt = f"""# <%这是角色初始化> 游戏世界即将开始运行。这是你的初始设定，你将以此为起点进行游戏

## 游戏介绍
{about_game}

## 当前游戏运行回合
当前回合: {game_round}

## 初始设定
{kick_off_message}

## 请结合你的角色设定,更新你的状态!

## 输出要求:
- 请遵循 输出格式指南。
- 返回结果只带如下的键: {MindVoiceAction.__name__}, {TagAction.__name__}。"""

    return prompt


###############################################################################################################################################
def make_kick_off_stage_prompt(
    kick_off_message: str,
    about_game: str,
    stage_prop_files: List[PropFile],
    actors_in_stage: Set[str],
    game_round: int,
) -> str:

    props_prompt = ""
    if len(stage_prop_files) > 0:
        for prop_file in stage_prop_files:
            props_prompt += make_prop_prompt(prop_file, False, True)
    else:
        props_prompt = "- 无任何道具。"

    ## 场景角色
    actors_prompt = ""
    if len(actors_in_stage) > 0:
        for actor_name in actors_in_stage:
            actors_prompt += f"- {actor_name}\n"
    else:
        actors_prompt = "- 无任何角色。"

    prompt = f"""# <%这是场景初始化> 游戏世界即将开始运行。这是你的初始设定，你将以此为起点进行游戏

## 游戏介绍
{about_game}

## 当前游戏运行回合
当前回合: {game_round}

## 场景内的可交互的道具(包括 可拾取，可与之交互)
{props_prompt}

## 场景内角色
{actors_prompt}

## 初始设定
{kick_off_message}

## 输出要求:
- 请遵循 输出格式指南。
- 返回结果，仅带如下的键: {StageNarrateAction.__name__} 和 {TagAction.__name__}。"""
    return prompt


###############################################################################################################################################
def make_kick_off_world_system_prompt(about_game: str, game_round: int) -> str:
    prompt = f"""# <%这是世界系统初始化> 游戏世界即将开始运行，请简要回答你的职能与描述

## 游戏介绍
{about_game}

## 当前游戏运行回合
当前回合: {game_round}"""
    return prompt


###############################################################################################################################################
def make_actor_plan_prompt(
    game_round: int,
    current_stage: str,
    stage_enviro_narrate: str,
    stage_graph: Set[str],
    stage_props: List[PropFile],
    health: float,
    categorized_prop_files: Dict[str, List[PropFile]],
    current_weapon: Optional[PropFile],
    current_clothes: Optional[PropFile],
) -> str:

    health *= 100

    prop_files_prompt_list = make_categorized_prop_files_prompt_list(
        categorized_prop_files
    )

    stage_prop_prompts = [make_prop_prompt(prop, False, True) for prop in stage_props]

    prompt = f"""# {ConstantPrompt.ACTOR_PLAN_PROMPT_TAG} 请做出你的计划，决定你将要做什么

## 当前游戏运行回合
当前回合: {game_round}

## 你当前所在的场景
{current_stage != "" and current_stage or "未知"}
### 场景描述
{stage_enviro_narrate != "" and stage_enviro_narrate or "无"}
### 从本场景可以去往的场景
{len(stage_graph) > 0 and "\n".join([f"- {stage}" for stage in stage_graph]) or "无"}

## 场景内的可交互的道具(包括 可拾取，可与之交互)
{len(stage_prop_prompts) > 0 and "\n".join(stage_prop_prompts) or "- 无任何道具。"}

## 你的健康状态:
{f"生命值: {health:.2f}%"}

## 你自身持有道具:
{len(prop_files_prompt_list) > 0 and "\n".join(prop_files_prompt_list) or "- 无任何道具。"}

## 你当前装备的道具
- 武器: {current_weapon is not None and current_weapon.name or "无"}
- 衣服: {current_clothes is not None and current_clothes.name or "无"}

## 输出要求:
- 请遵循 输出格式指南。
- 结果中要附带 {TagAction.__name__}。"""

    return prompt


###############################################################################################################################################
def make_stage_plan_prompt(
    stage_prop_files: List[PropFile], game_round: int, actors_info: Dict[str, str]
) -> str:

    ## 场景内的可交互的道具(包括 可拾取，可与之交互)
    props_prompt = ""
    if len(stage_prop_files) > 0:
        for prop in stage_prop_files:
            props_prompt += make_prop_prompt(prop, False, True)
    else:
        props_prompt = "- 无任何道具。"

    ## 场景角色
    actors_prompt = ""
    if len(actors_info) > 0:
        for actor_name, actor_appearance in actors_info.items():
            actors_prompt += f"### {actor_name}\n- 角色外观:{actor_appearance}\n"
    else:
        actors_prompt = "- 无任何角色。"

    prompt = f"""# {ConstantPrompt.STAGE_PLAN_PROMPT_TAG} 请输出'场景描述'和'你的计划'

## 当前游戏运行回合
当前回合: {game_round}

## 场景内的可交互的道具(包括 可拾取，可与之交互)
{props_prompt}

## 场景内角色:
{actors_prompt}

## 关于’你的计划‘内容生成规则
- 根据你作为场景受到了什么事件的影响，你可以制定计划，并决定下一步将要做什么。可根据 输出格式指南 选择相应的行动。

## 输出要求:
- 请遵循 输出格式指南。
- 必须包含 {StageNarrateAction.__name__} 和 {TagAction.__name__}。"""

    return prompt


###############################################################################################################################################
def make_perception_action_prompt(
    who: str,
    current_stage: str,
    result_actor_names: Dict[str, str],
    result_props_names: List[str],
) -> str:

    prompt_of_actor = ""
    if len(result_actor_names) > 0:
        for other_name, other_appearance in result_actor_names.items():
            prompt_of_actor += f"""### {other_name}\n- 角色外观:{other_appearance}\n"""
    else:
        prompt_of_actor = "- 无其他角色。"

    prompt_of_props = ""
    if len(result_props_names) > 0:
        for propname in result_props_names:
            prompt_of_props += f"- {propname}\n"
    else:
        prompt_of_props = "- 无任何道具。"

    final_prompt = f"""# {ConstantPrompt.PERCEPTION_ACTION_TAG} {who} 在 {current_stage} 中执行感知行动({PerceptionAction.__name__})，结果如下:
## 场景内角色:
{prompt_of_actor}
## 场景内的可交互的道具(包括 可拾取，可与之交互)
{prompt_of_props}"""
    return final_prompt


###############################################################################################################################################
def make_prop_type_prompt(prop_file: PropFile) -> str:

    ret = "未知"

    if prop_file.is_weapon:
        ret = "武器"
    elif prop_file.is_clothes:
        ret = "衣服"
    elif prop_file.is_non_consumable_item:
        ret = "非消耗品"
    elif prop_file.is_special:
        ret = "特殊能力"
    elif prop_file.is_skill:
        ret = "技能"

    return ret


###############################################################################################################################################
def make_prop_prompt(
    prop_file: PropFile, need_description_prompt: bool, need_appearance_prompt: bool
) -> str:

    prompt = f"""### {prop_file.name}
- 类型:{make_prop_type_prompt(prop_file)}"""
    if need_description_prompt:
        prompt += f"\n- 道具描述:{prop_file.description}"

    if need_appearance_prompt:
        prompt += f"\n- 道具外观:{prop_file.appearance}"

    return prompt


###############################################################################################################################################
def make_categorized_prop_files_prompt_list(
    categorized_prop_files: Dict[str, List[PropFile]],
    sorted_keys: List[str] = [
        PropFile.TYPE_SPECIAL,
        PropFile.TYPE_WEAPON,
        PropFile.TYPE_CLOTHES,
        PropFile.TYPE_NON_CONSUMABLE_ITEM,
        PropFile.TYPE_SKILL,
    ],
) -> List[str]:

    ret: List[str] = []

    for key in sorted_keys:
        if key not in categorized_prop_files:
            continue

        prop_files = categorized_prop_files[key]
        if len(prop_files) == 0:
            continue

        for prop_file in prop_files:
            ret.append(make_prop_prompt(prop_file, True, True))

    return ret


###############################################################################################################################################
def make_check_status_action_prompt(
    actor_name: str,
    health: float,
    categorized_prop_files: Dict[str, List[PropFile]],
) -> str:

    health *= 100

    prop_files_prompt_list = make_categorized_prop_files_prompt_list(
        categorized_prop_files
    )

    # 组合最终的提示
    prompt = f"""# {ConstantPrompt.CHECK_STATUS_ACTION_TAG} {actor_name} 正在查看自身状态与拥有的道具
## 健康状态:
{f"生命值: {health:.2f}%"}
## 持有道具:
{len(prop_files_prompt_list) > 0 and "\n".join(prop_files_prompt_list) or "- 无任何道具。"}"""

    return prompt


###############################################################################################################################################
def make_search_prop_action_failed_prompt(actor_name: str, prop_name: str) -> str:
    return f"""# {actor_name} 无法找到道具 "{prop_name}"。
## 可能原因:
1. {prop_name} 不是一个可搜索的道具。
2. 道具可能已被移出场景或被其他角色获取。
## 建议:
1. 请{actor_name}重新考虑搜索目标。
2. 使用 {PerceptionAction.__name__} 感知场景内的道具，确保目标的可搜索性。"""


###############################################################################################################################################
def make_search_prop_action_success_prompt(
    actor_name: str, prop_name: str, stagename: str
) -> str:
    return f"""# {actor_name}从{stagename}场景内成功找到并获取了道具:{prop_name}。
## 导致结果:
- {stagename} 此场景内不再有这个道具。"""


################################################################################################################################################
def make_enter_stage_prompt1(actor_name: str, target_stage_name: str) -> str:
    return f"# {actor_name}进入了场景 {target_stage_name}。"


################################################################################################################################################
def make_enter_stage_prompt2(
    actor_name: str, target_stage_name: str, last_stage_name: str
) -> str:
    return f"# {actor_name} 离开了 {last_stage_name}, 进入了{target_stage_name}。"


################################################################################################################################################
def make_leave_stage_prompt(
    actor_name: str, current_stage_name: str, go_to_stage_name: str
) -> str:
    return f"# {actor_name}离开了{current_stage_name} 场景。"


################################################################################################################################################
# def make_stage_director_event_wrap_prompt(event: str, event_index: int) -> str:
#     event_number = event_index + 1
#     return f"""# 事件{event_number}\n{event}"""


################################################################################################################################################
# def make_stage_director_begin_prompt(stage_name: str, events_count: int) -> str:
#     return f"""# 如下是{stage_name}场景内发生的事件，事件数量为{events_count}。"""


################################################################################################################################################
# def make_stage_director_end_prompt(stage_name: str, events_count: int) -> str:
#     return f"""# 以上是{stage_name}场景内近期发生的{events_count}个事件。"""


################################################################################################################################################
def make_whisper_action_prompt(src_name: str, dest_name: str, content: str) -> str:
    return (
        f"# {ConstantPrompt.WHISPER_ACTION_TAG} {src_name}对{dest_name}私语道:{content}"
    )


################################################################################################################################################
def make_broadcast_action_prompt(src_name: str, dest_name: str, content: str) -> str:
    return f"# {ConstantPrompt.BROADCASE_ACTION_TAG} {src_name}对{dest_name}里的所有人说:{content}"


################################################################################################################################################
def make_speak_action_prompt(src_name: str, dest_name: str, content: str) -> str:
    return f"# {ConstantPrompt.SPEAK_ACTION_TAG} {src_name}对{dest_name}说:{content}"


################################################################################################################################################
def make_steal_prop_action_prompt(
    actor_name: str, target_name: str, prop_name: str, action_result: bool
) -> str:
    if not action_result:
        return f"{actor_name}从{target_name}盗取{prop_name}, 失败了"
    return f"{actor_name}从{target_name}成功盗取了{prop_name}"


################################################################################################################################################
def make_give_prop_action_prompt(
    from_who: str, to_who: str, prop_name: str, action_result: bool
) -> str:
    if not action_result:
        return f"{from_who}向{to_who}交换{prop_name}, 失败了"
    return f"{from_who}向{to_who}成功交换了{prop_name}"


################################################################################################################################################
def go_to_stage_failed_because_stage_is_invalid_prompt(
    actor_name: str, stagename: str
) -> str:
    return f"""#{actor_name}无法前往{stagename}，可能的原因包括:
- {stagename}目前不可访问，可能未开放或已关闭。
- 场景名称"{stagename}"格式不正确，如“xxx的深处/北部/边缘/附近/其他区域”，这样的表达可能导致无法正确识别。
- 请 {actor_name} 重新考虑目的地。"""


################################################################################################################################################
def go_to_stage_failed_because_already_in_stage_prompt(
    actor_name: str, stage_name: str
) -> str:
    return f"你已经在 {stage_name} 场景中。需要重新考虑去往的目的地"


################################################################################################################################################
def replace_mentions_of_your_name_with_you_prompt(content: str, your_name: str) -> str:
    if len(content) == 0 or your_name not in content:
        return content
    return content.replace(your_name, "你")


################################################################################################################################################
def update_actor_archive_prompt(actor_name: str, actor_archives: Set[str]) -> str:
    if len(actor_archives) == 0:
        return f"# {actor_name} 目前没有认识的角色。"

    actors_names = ",".join(actor_archives)
    return f"# {actor_name} 认识的角色有：{actors_names}。"


################################################################################################################################################
def update_stage_archive_prompt(actor_name: str, stage_archives: Set[str]) -> str:
    if len(stage_archives) == 0:
        return f"# {actor_name} 目前没有已知的场景。"

    stages_names = ",".join(stage_archives)
    return f"# {actor_name} 已知的场景包括：{stages_names}。"


################################################################################################################################################
def make_kill_event_prompt(actor_name: str, target_name: str) -> str:
    return f"# {actor_name}对{target_name}发动了一次攻击,造成了{target_name}死亡。"


################################################################################################################################################
def make_damage_event_prompt(
    actor_name: str,
    target_name: str,
    damage: int,
    target_current_hp: int,
    target_max_hp: int,
) -> str:
    health_percent = max(0, (target_current_hp - damage) / target_max_hp * 100)
    return f"# {actor_name}对{target_name}发动了攻击,造成了{damage}点伤害,当前{target_name}的生命值剩余{health_percent}%。"


################################################################################################################################################
def stage_exit_conditions_check_prompt(
    actor_name: str,
    current_stage_name: str,
    actor_status_prompt: str,
    prop_files: List[PropFile],
) -> str:

    prop_prompt_list = "无"
    if len(prop_files) > 0:
        prop_prompt_list = "\n".join(
            [make_prop_prompt(prop, True, True) for prop in prop_files]
        )

    ret_prompt = f"""# {actor_name} 想要离开场景: {current_stage_name}。
## 第1步: 请回顾你的 {ConstantPrompt.STAGE_EXIT_TAG}

## 第2步: 根据当前‘你的状态’判断是否满足允许{actor_name}离开
当前状态可能由于事件而变化，请仔细考虑。

## 第3步: 检查{actor_name}的状态是否符合离开的需求:
### 当前角色状态: 
{actor_status_prompt if actor_status_prompt != "" else "无"}

## 第4步: 检查{actor_name}的道具(与拥有的特殊能力)是否符合以下要求:
### 当前角色道具与特殊能力信息: 
{prop_prompt_list}

# 判断结果
- 完成以上步骤后，决定是否允许 {actor_name} 离开 {current_stage_name}。

# 本次输出结果格式要求。需遵循 输出格式指南:
{{
    {WhisperAction.__name__}: ["@角色名字(你要对谁说,只能是场景内的角色)>你想私下说的内容，即描述允许离开或不允许的原因，使{actor_name}明白"],
    {TagAction.__name__}: ["Yes/No"]
}}
## 附注
- {WhisperAction.__name__} 中描述的判断理由。如果不允许离开，就只说哪一条不符合要求，不要都说出来，否则会让{actor_name}迷惑，和造成不必要的提示，影响玩家解谜的乐趣。
- Yes: 允许离开
- No: 不允许离开
"""

    return ret_prompt


################################################################################################################################################
def stage_entry_conditions_check_prompt(
    actor_name: str,
    current_stage_name: str,
    actor_status_prompt: str,
    prop_files: List[PropFile],
) -> str:

    prop_prompt_list = "无"
    if len(prop_files) > 0:
        prop_prompt_list = "\n".join(
            [make_prop_prompt(prop, True, True) for prop in prop_files]
        )

    ret_prompt = f"""# {actor_name} 想要进入场景: {current_stage_name}。
## 第1步: 请回顾你的 {ConstantPrompt.STAGE_EXIT_TAG}

## 第2步: 根据当前‘你的状态’判断是否满足允许{actor_name}进入
当前状态可能由于事件而变化，请仔细考虑。

## 第3步: 检查{actor_name}的状态是否符合进入的需求:
### 当前角色状态: 
{actor_status_prompt if actor_status_prompt != "" else "无"}

## 第4步: 检查{actor_name}的道具(与拥有的特殊能力)是否符合以下要求:
### 当前角色道具与特殊能力信息: 
{prop_prompt_list}

# 判断结果
- 完成以上步骤后，决定是否允许 {actor_name} 进入 {current_stage_name}。

# 本次输出结果格式要求。需遵循 输出格式指南:
{{
    {WhisperAction.__name__}: ["@角色名字(你要对谁说,只能是场景内的角色)>你想私下说的内容，即描述允许进入或不允许的原因，使{actor_name}明白"],
    {TagAction.__name__}: ["Yes/No"]
}}
## 附注
- {WhisperAction.__name__} 中描述的判断理由。如果不允许进入，就只说哪一条不符合要求，不要都说出来，否则会让{actor_name}迷惑，和造成不必要的提示，影响玩家解谜的乐趣。
- Yes: 允许进入
- No: 不允许进入
"""
    return ret_prompt


################################################################################################################################################
def exit_stage_failed_beacuse_stage_refuse_prompt(
    actor_name: str, current_stage_name: str, show_tips: str
) -> str:
    return f"""# {actor_name} 想要离开场景: {current_stage_name}，但是失败了。
## 说明:
{show_tips}"""


################################################################################################################################################
def enter_stage_failed_beacuse_stage_refuse_prompt(
    actor_name: str, stage_name: str, show_tips: str
) -> str:
    return f"""# {actor_name} 想要进入场景: {stage_name}，但是失败了。
## 说明:
{show_tips}"""


################################################################################################################################################
def make_on_update_appearance_event_prompt(safe_name: str, appearance: str) -> str:
    return f"""# {safe_name} 的外观信息已更新
## 你的当前 角色外观
{appearance}"""


################################################################################################################################################
def make_world_system_reasoning_appearance_prompt(
    actors_body_and_clothe: Dict[str, tuple[str, str]]
) -> str:
    appearance_info_list: List[str] = []
    actor_names: List[str] = []
    for name, (body, clothe) in actors_body_and_clothe.items():
        if clothe == "":
            continue
        appearance_info = f"""### {name}
- 裸身:{body}
- 衣服:{clothe}
"""
        appearance_info_list.append(appearance_info)
        actor_names.append(name)

    #
    final_input_prompt = "\n".join(appearance_info_list)
    assert len(final_input_prompt) > 0
    #
    dumps_as_format = json.dumps(
        {name: "?" for name in actor_names}, ensure_ascii=False
    )

    # 最后的合并
    ret_prompt = f"""# 请根据 裸身 与 衣服，生成当前的角色外观的描述。
## 提供给你的信息
{final_input_prompt}

## 推理逻辑
- 第1步:如角色有衣服。则代表“角色穿着衣服”。最终推理结果为:裸身的信息结合衣服信息。并且是以第三者视角能看到的样子去描述。
    - 注意！部分身体部位会因穿着衣服被遮蔽。请根据衣服的信息进行推理。
    - 衣服的样式，袖子与裤子等信息都会影响最终外观。
    - 面具（遮住脸），帽子（遮住头部，或部分遮住脸）等头部装饰物也会影响最终外观。
    - 被遮住的部位（因为站在第三者视角就无法看见），不需要再次提及，不要出现在推理结果中，如果有，需要删除。
    - 注意！错误的句子：胸前的黑色印记被衣服遮盖住，无法看见。
- 第2步:如角色无衣服，推理结果为角色当前为裸身。
    - 注意！如果是人形角色，裸身意味着穿着内衣!
    - 如果是动物，怪物等非人角色，就是最终外观信息。
- 第3步:将推理结果进行适度润色。

## 输出格式指南

### 输出格式（请根据下面的示意, 确保你的输出严格遵守相应的结构)
{dumps_as_format}

### 注意事项
- '?'就是你推理出来的结果(结果中可以不用再提及角色名字)，你需要将其替换为你的推理结果。
- 所有文本输出必须为第3人称。
- 每个 JSON 对象必须包含上述键中的一个或多个，不得重复同一个键，也不得使用不在上述中的键。
- 输出不应包含任何超出所需 JSON 格式的额外文本、解释或总结。
- 不要使用```json```来封装内容。
"""
    return ret_prompt


################################################################################################################################################
def make_unknown_guid_stage_name_prompt(guid: int) -> str:
    return f"未知场景:{guid}"


################################################################################################################################################
def is_unknown_guid_stage_name_prompt(stage_name: str) -> bool:
    return "未知场景" in stage_name


################################################################################################################################################
def extract_from_unknown_guid_stage_name_prompt(stage_name: str) -> int:
    return int(stage_name.split(":")[1])


################################################################################################################################################
def make_player_conversation_check_prompt(
    input_broadcast_content: str,
    input_speak_content_list: List[str],
    input_whisper_content_list: List[str],
) -> str:

    broadcast_prompt = input_broadcast_content != "" and input_broadcast_content or "无"
    speak_content_prompt = (
        len(input_speak_content_list) > 0
        and "\n".join(input_speak_content_list)
        or "无"
    )
    whisper_content_prompt = (
        len(input_whisper_content_list) > 0
        and "\n".join(input_whisper_content_list)
        or "无"
    )

    prompt = f"""# 玩家输入了如下对话类型事件，请你检查

## {BroadcastAction.__name__}
{broadcast_prompt}
## {SpeakAction.__name__}
{speak_content_prompt}
## {WhisperAction.__name__}
{whisper_content_prompt}
## 检查规则
- 对话内容是否违反政策。
- 对话内容是否有不当的内容。
- 对话对容是否有超出游戏范围的内容。例如，玩家说了一些关于游戏外的事情，或者说出不符合游戏世界观与历史背景的事件。
"""
    return prompt


################################################################################################################################################


def make_world_reasoning_release_skill_prompt(
    actor_name: str,
    actor_info: str,
    skill_files: List[PropFile],
    prop_files: List[PropFile],
) -> str:

    skill_prompt: List[str] = []
    if len(skill_files) > 0:
        for skill_file in skill_files:
            skill_prompt.append(make_prop_prompt(skill_file, True, False))
    else:
        skill_prompt.append("- 无任何技能。")

    prop_prompt: List[str] = []
    if len(prop_files) > 0:
        for prop_file in prop_files:
            prop_prompt.append(make_prop_prompt(prop_file, True, True))
    else:
        prop_prompt.append("- 无任何道具。")

    prompt = f"""# {actor_name} 准备使用技能，请你做出判断并推理结果。

## {actor_name} 信息
{actor_info}
        
## 施放技能
{"\n".join(skill_prompt)}

## 配置的道具
{"\n".join(prop_prompt)}

## 判断步骤
步骤1: 如果 {actor_name} 自身不满足技能释放的条件，则技能释放失败。
步骤2: 如果 施放技能 对配置的道具有 明确的需求，如果道具不满足，则技能释放失败。
步骤3: 如果 施放技能 对配置的道具无需求（或者不依赖任何道具），则技能释放成功。
步骤4: 如果有 配置的道具。则按着技能在道具辅助下释放技能。例如提高技能的效果，或者减少技能的消耗。不是必须的，所以放到最后来判断。

## 输出格式指南

### 请根据下面的示例, 确保你的输出严格遵守相应的结构。
{{
  "{BroadcastAction.__name__}":["输出逻辑合理且附带润色的句子描述"],
  "{TagAction.__name__}":["{ConstantPrompt.BIG_SUCCESS}或{ConstantPrompt.SUCCESS}或{ConstantPrompt.FAILURE}或{ConstantPrompt.BIG_FAILURE}"]
}}

### 关于键值的补充规则说明
- 关于 {TagAction.__name__} 键值:
    - 只能是如下4个值: {ConstantPrompt.BIG_SUCCESS},{ConstantPrompt.SUCCESS},{ConstantPrompt.FAILURE},{ConstantPrompt.BIG_FAILURE}。
    - {ConstantPrompt.BIG_SUCCESS} 代表技能释放 不仅{ConstantPrompt.SUCCESS}，且效果超出预期。
    - {ConstantPrompt.FAILURE} 代表技能释放 不仅{ConstantPrompt.BIG_FAILURE}，且使用者会受到惩罚。

- 关于 {BroadcastAction.__name__} 键值:
    - 例句：{actor_name} 使用了xx道具,对xx目标,释放了xx技能,结果为xxx(注意{TagAction.__name__}键值),表现效果为xxx(逻辑合理且附带润色)。
    - 按着例句，输出逻辑合理且附带润色的句子描述，来表达 {actor_name} 使用技能的释放结果。
    - 如果是失败，需要描述失败的原因。
    
### 注意事项
- 每个 JSON 对象必须包含上述键中的一个或多个，不得重复同一个键，也不得使用不在上述中的键。
- 输出不应包含任何超出所需 JSON 格式的额外文本、解释或总结。
- 不要使用```json```来封装内容。"""

    return prompt


################################################################################################################################################


def make_reasoning_skill_target_reasoning_prompt(
    actor_name: str,
    target_name: str,
    reasoning_sentence: str,
    result_desc: str,
) -> str:

    prompt = f"""# {actor_name} 向 {target_name} 发动技能。
## 事件描述
 {reasoning_sentence}

## 系统判断结果
{result_desc}

## 判断步骤
第1步:回顾 {target_name} 的当前状态。
第2步:结合 事件描述 与 系统判断结果，推理技能对 {target_name} 的影响。例如改变你的状态，或者对你造成伤害等。
第3步:更新 {target_name} 的状态，作为最终输出。

## 输出要求:
- 请遵循 输出格式指南。
- 返回结果仅带如下2个键: {BroadcastAction.__name__} 和 {TagAction.__name__}。
- {BroadcastAction.__name__} 的内容格式要求为: "{target_name}对技能的反馈与更新后的状态描述"。
"""

    return prompt


################################################################################################################################################


def make_behavior_check_prompt(
    actor_name: str, behavior_sentence: str, allow: bool
) -> str:
    if allow:
        prompt1 = f"""# 这是一次 {actor_name} 的计划行动
## 行动内容语句
{behavior_sentence}
## 结果
- 系统经过分析之后允许通过。也就是执行后续的处理步骤。"""
        return prompt1

    prompt2 = f""" # 这是一次 {actor_name} 的计划行动
## 行动内容语句
{behavior_sentence}
## 结果
- 系统判断后，拒绝！不通过。
- 请检查行动内容，必须至少有一个技能与一个目标。"""

    return prompt2


################################################################################################################################################


def make_world_skill_system_off_line_error_prompt(
    actor_name: str, behavior_sentence: str
) -> str:

    prompt = f"""# 注意! 全局技能系统 处于离线状态或者出错，无法使用技能，请一会再试。
## 行动内容语句({actor_name} 发起)
{behavior_sentence}
## 以上的行动将无法执行（被系统强制取消），因为技能系统处于离线状态或者出错。
"""
    return prompt


################################################################################################################################################


def make_skill_skill_target_agent_off_line_error_prompt(
    actor_name: str, target_name: str, reasoning_sentence: str
) -> str:

    prompt = f"""# 注意! {actor_name} 无法对 {target_name} 使用技能，本次技能释放被系统取消。
## 行动内容语句({actor_name} 发起)
{reasoning_sentence}
"""
    return prompt


################################################################################################################################################
def make_world_skill_system_reasoning_result_is_failure_prompt(
    actor_name: str,
    failure_desc: str,
    input_behavior_sentence: str,
    reasoning_sentence: str,
) -> str:

    prompt = f"""# 全局技能系统 推理与判断之后，判断结果为 {failure_desc}
## 行动(技能)发起者: {actor_name}
## 失败类型: {failure_desc}
## 原始的行动内容语句
{input_behavior_sentence}
## 系统推理后的结果
{reasoning_sentence}

## 错误分析与提示
- 请检查行动内容，必须至少有一个技能与一个目标。
- 如果 技能的释放目标 不合理会被系统拒绝。
- 虽然道具可用来配合技能使用，但使用必须合理(请注意道具的说明，使用限制等)
- 道具，技能和对象之间的关系如果不合理（违反游戏世界的运行规律与常识）。也会被系统拒绝。
"""
    return prompt


################################################################################################################################################


def make_notify_release_skill_event_prompt(
    actor_name: str, target_name: str, reasoning_sentence: str
) -> str:

    prompt = f"""# {actor_name} 向 {target_name} 发动技能。
## 事件描述
{reasoning_sentence}
"""
    return prompt
