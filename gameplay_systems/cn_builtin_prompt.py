from typing import Dict, List, Set, Optional
from file_system.files_def import PropFile
from gameplay_systems.action_components import (
    MindVoiceAction,
    StageNarrateAction,
    TagAction,
    BroadcastAction,
    BroadcastAction,
    SpeakAction,
    WhisperAction,
    GoToAction,
    PickUpPropAction,
    RemovePropAction,
)
import json
from gameplay_systems.cn_constant_prompt import _CNConstantPrompt_ as ConstantPrompt
from my_data.model_def import PropType


###############################################################################################################################################
def make_actor_kick_off_prompt(
    kick_off_message: str, about_game: str, game_round: int
) -> str:

    ret_prompt = f"""# {ConstantPrompt.ACTOR_KICK_OFF_MESSAGE_PROMPT_TAG} 游戏世界即将开始运行。这是你的初始设定，你将以此为起点进行游戏并更新你的状态

## 游戏背景与风格设定
{about_game}

## 当前游戏运行回合: {game_round}

## 你的初始设定
{kick_off_message}

## 输出要求
- 请遵循 输出格式指南。
- 返回结果只带如下的键:{MindVoiceAction.__name__}与{TagAction.__name__}。"""

    return ret_prompt


###############################################################################################################################################
def make_stage_kick_off_prompt(
    kick_off_message: str,
    about_game: str,
    props_in_stage: List[PropFile],
    actors_in_stage: Set[str],
    game_round: int,
) -> str:

    props_prompt = "- 无任何道具。"
    if len(props_in_stage) > 0:
        props_prompt = ""
        for prop_file in props_in_stage:
            props_prompt += make_prop_prompt(
                prop_file, description_prompt=False, appearance_prompt=True
            )

    actors_prompt = "- 无任何角色。"
    if len(actors_in_stage) > 0:
        actors_prompt = ""
        for actor_name in actors_in_stage:
            actors_prompt += f"- {actor_name}\n"

    ret_prompt = f"""# {ConstantPrompt.STAGE_KICK_OFF_MESSAGE_PROMPT_TAG} 游戏世界即将开始运行。这是你的初始设定，你将以此为起点进行游戏并更新你的状态

## 游戏背景与风格设定
{about_game}

## 当前游戏运行回合: {game_round}

## 场景内的道具
{props_prompt}

## 场景内的角色
{actors_prompt}

## 你的初始设定
{kick_off_message}

## 生成内容规则
- 不要对场景内角色未发生的对话，行为或心理活动进行任何猜测。
- 注意！输出的 {StageNarrateAction.__name__} 场景描述中，需要移除所有场景内角色的描述。如果场景内存在道具，请结合道具信息进行状态更新。

## 输出要求
- 请遵循 输出格式指南。
- 返回结果只包含如下:{StageNarrateAction.__name__} 和 {TagAction.__name__}。"""
    return ret_prompt


# ### 关于键值的补充规则说明
# - StageNarrateAction
#   - 步骤1: 梳理 场景中发生的 角色相关事件 与 道具相关事件（如角色对道具的拾取、放置等）。注意！不要对角色未发生的对话，行为或心理活动进行任何猜测。
#   - 步骤2: 根据 步骤1 ，并结合场景的历史，推理对场景产生的影响，做状态更新。生成 场景描述的初稿。
#   - 步骤3: 如果已经成功移除了场景中的某道具，请在 场景描述的初稿 中移除所有相关 此道具 的文本。
#   - 步骤4: 场景中未被移除的道具，其描述仍然需要 保留在 场景描述的初稿 中
#   - 步骤5: 重要！从 场景描述的初稿 中移除所有与角色相关的描述。
#   - 最终输出: 在以上步骤执行完毕之后，场景描述的初稿 就 转变为 最终 生成的场景描述(请将这个内容作为输出)。



###############################################################################################################################################
def make_world_system_kick_off_prompt(about_game: str, game_round: int) -> str:
    ret_prompt = f"""# {ConstantPrompt.WORLD_SYSTEM_KICK_OFF_MESSAGE_PROMPT_TAG} 游戏世界即将开始运行。这是你的初始设定，请简要回答你的职能与描述

## 游戏背景与风格设定
{about_game}

## 当前游戏运行回合: {game_round}"""
    return ret_prompt


###############################################################################################################################################
def make_actor_plan_prompt(
    game_round: int,
    current_stage: str,
    stage_enviro_narrate: str,
    stage_graph: Set[str],
    props_in_stage: List[PropFile],
    info_of_actors_in_stage: Dict[str, str],
    health: float,
    actor_props: Dict[str, List[PropFile]],
    current_weapon: Optional[PropFile],
    current_clothes: Optional[PropFile],
) -> str:

    health *= 100

    actor_props_prompt = make_props_prompt_list_for_actor_plan(actor_props)

    props_in_stage_prompt = [
        make_prop_prompt(prop, description_prompt=False, appearance_prompt=True)
        for prop in props_in_stage
    ]

    actors_in_stage_prompt = "- 无任何角色。"
    if len(info_of_actors_in_stage) > 0:
        actors_in_stage_prompt = ""
        for actor_name, actor_appearance in info_of_actors_in_stage.items():
            actors_in_stage_prompt += (
                f"### {actor_name}\n- 角色外观:{actor_appearance}\n"
            )

    ret_prompt = f"""# {ConstantPrompt.ACTOR_PLAN_PROMPT_TAG} 请做出你的计划，决定你将要做什么

## 当前游戏运行回合: {game_round}

## 你当前所在的场景
{current_stage != "" and current_stage or "未知"}
### 场景描述
{stage_enviro_narrate != "" and stage_enviro_narrate or "无"}
### 从本场景可以去往的场景
{len(stage_graph) > 0 and "\n".join([f"- {stage}" for stage in stage_graph]) or "无可去往场景"}   

## 场景内的道具(可以进行交互，如: {PickUpPropAction.__name__})
{len(props_in_stage_prompt) > 0 and "\n".join(props_in_stage_prompt) or "- 无任何道具。"}

## 场景内的角色
{actors_in_stage_prompt}

## 你的健康状态
{f"生命值: {health:.2f}%"}

## 你当前持有的道具
{len(actor_props_prompt) > 0 and "\n".join(actor_props_prompt) or "- 无任何道具。"}

## 你当前装备的道具
- 武器: {current_weapon is not None and current_weapon.name or "无"}
- 衣服: {current_clothes is not None and current_clothes.name or "无"}

## 建议与注意事项
- 结合以上信息，决定你的下一步行动。
- 随时保持装备武器与衣服的状态(前提是你有对应的道具）。
- 注意！如果 从本场景可以去往的场景 为 无可去往场景，你就不可以执行{GoToAction.__name__}，因为系统的设计规则如此。

## 输出要求
- 请遵循 输出格式指南。
- 结果中要附带 {TagAction.__name__}。"""

    return ret_prompt


###############################################################################################################################################
def make_stage_plan_prompt(
    props_in_stage: List[PropFile],
    game_round: int,
    info_of_actors_in_stage: Dict[str, str],
) -> str:

    props_in_stage_prompt = "- 无任何道具。"
    if len(props_in_stage) > 0:
        props_in_stage_prompt = ""
        for prop in props_in_stage:
            props_in_stage_prompt += make_prop_prompt(
                prop, description_prompt=False, appearance_prompt=True
            )

    ## 场景角色
    actors_in_stage_prompt = "- 无任何角色。"
    if len(info_of_actors_in_stage) > 0:
        actors_in_stage_prompt = ""
        for actor_name, actor_appearance in info_of_actors_in_stage.items():
            actors_in_stage_prompt += (
                f"### {actor_name}\n- 角色外观:{actor_appearance}\n"
            )

    ret_prompt = f"""# {ConstantPrompt.STAGE_PLAN_PROMPT_TAG} 请做出你的计划，决定你将要做什么

## 当前游戏运行回合: {game_round}

## 场景内的道具
{props_in_stage_prompt}

## 场景内的角色
{actors_in_stage_prompt}

## 生成内容规则
- 结合以上信息，决定你的下一步行动。
- 不要对场景内角色未发生的对话，行为或心理活动进行任何猜测。
- 注意！输出的 {StageNarrateAction.__name__} 场景描述中，需要移除所有场景内角色的描述。如果场景内存在道具，请结合道具信息进行状态更新。
- 如果 场景内的道具 产生损毁与破坏等事件 (请回顾你的历史消息)，则使用 {RemovePropAction.__name__} 将其移除，以此来保证你的逻辑的连贯与合理性。并在 场景描述中将其信息都移除。

## 输出要求
- 请遵循 输出格式指南。
- 返回结果必须包含 {StageNarrateAction.__name__} 和 {TagAction.__name__}。"""

    return ret_prompt


###############################################################################################################################################
def make_prop_type_prompt(prop_file: PropFile) -> str:

    ret_prompt = "未知"

    if prop_file.is_weapon:
        ret_prompt = "武器"
    elif prop_file.is_clothes:
        ret_prompt = "衣服"
    elif prop_file.is_non_consumable_item:
        ret_prompt = "非消耗品"
    elif prop_file.is_special:
        ret_prompt = "特殊能力"
    elif prop_file.is_skill:
        ret_prompt = "技能"

    return ret_prompt


###############################################################################################################################################
def make_prop_prompt(
    prop_file: PropFile,
    description_prompt: bool,
    appearance_prompt: bool,
    attr_prompt: bool = False,
) -> str:

    prompt = f"""### {prop_file.name}
- 类型:{make_prop_type_prompt(prop_file)}"""

    if description_prompt:
        prompt += f"\n- 道具描述:{prop_file.description}"

    if appearance_prompt:
        prompt += f"\n- 道具外观:{prop_file.appearance}"

    if attr_prompt:
        prompt += f"\n- 攻击力:{prop_file.attack}\n- 防御力:{prop_file.defense}"

    return prompt


###############################################################################################################################################
def make_props_prompt_list_for_actor_plan(
    props_dict: Dict[str, List[PropFile]],
    order_keys: List[str] = [
        PropType.TYPE_SPECIAL.value,
        PropType.TYPE_WEAPON.value,
        PropType.TYPE_CLOTHES.value,
        PropType.TYPE_NON_CONSUMABLE_ITEM.value,
        PropType.TYPE_SKILL.value,
    ],
) -> List[str]:

    ret: List[str] = []

    for key in order_keys:
        if key not in props_dict:
            continue

        for prop_file in props_dict[key]:
            ret.append(
                make_prop_prompt(
                    prop_file,
                    description_prompt=True,
                    appearance_prompt=True,
                    attr_prompt=True,
                )
            )

    return ret


###############################################################################################################################################
def make_actor_pick_up_prop_failed_prompt(actor_name: str, prop_name: str) -> str:
    return f"""# {actor_name} 无法拾取道具 {prop_name}
## 原因分析:
- {prop_name} 不是一个可拾取的道具。
- 该道具可能已被移出场景，或被其他角色拾取。
## 建议:
请{actor_name}重新考虑拾取的目标。"""


###############################################################################################################################################


def make_stage_prop_lost_prompt(stage_name: str, prop_name: str) -> str:
    return f"""# 场景 {stage_name} 内的道具 {prop_name} 已经不在了，所以无法对其进行任何操作。
## 原因分析:
- 该道具可能已被移出场景，或被其他角色拾取。
"""


###############################################################################################################################################
def make_pick_up_prop_success_prompt(
    actor_name: str, prop_name: str, stage_name: str
) -> str:
    return f"""# {actor_name} 从 {stage_name} 场景内成功找到并获取了道具 {prop_name}。
## 导致结果:
- {stage_name} 此场景内不再有这个道具。"""


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
    from_name: str, target_name: str, prop_name: str, action_result: bool
) -> str:
    if not action_result:
        return f"# {from_name} 试图从 {target_name} 盗取 {prop_name}, 但是失败了。"
    return f"""# {from_name} 从 {target_name} 成功盗取了 {prop_name}。
# 导致结果
- {target_name} 现在不再拥有 {prop_name}。
- {from_name} 现在拥有了 {prop_name}。"""


################################################################################################################################################
def make_give_prop_action_prompt(
    from_name: str, target_name: str, prop_name: str, action_result: bool
) -> str:
    if not action_result:
        return f"# {from_name} 试图将 {prop_name} 给予 {target_name}, 但是失败了。"

    return f"""# {from_name} 将 {prop_name} 成功给予了 {target_name}。
## 导致结果
- {from_name} 现在不再拥有 {prop_name}。
- {target_name} 现在拥有了 {prop_name}。"""


################################################################################################################################################
def go_to_stage_failed_because_stage_is_invalid_prompt(
    actor_name: str, stage_name: str
) -> str:
    return f"""# {actor_name} 无法前往 {stage_name}
## 可能的原因
1. {stage_name} 目前不可访问，可能未开放或已关闭。
2. 场景名称"{stage_name}"格式不正确,如“xxx的深处/北部/边缘/附近/其他区域”，这样的表达可能导致无法正确识别。
    - 必须根据 游戏规则设定 中 对场景名字严格匹配。
3. {actor_name} 无法从当前场景去往 {stage_name}。即当前场景与目标场景{stage_name}之间没有连接。
## 建议
- 请 {actor_name} 重新考虑目的地。"""


################################################################################################################################################
def go_to_stage_failed_because_already_in_stage_prompt(
    actor_name: str, stage_name: str
) -> str:
    return f"# 注意！{actor_name} 已经在 {stage_name} 场景中。需要重新考虑去往的目的地"


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
    return f"# {actor_name} 对 {target_name} 的行动造成了{target_name}死亡。"


################################################################################################################################################
def make_damage_event_prompt(
    actor_name: str,
    target_name: str,
    damage: int,
    target_current_hp: int,
    target_max_hp: int,
) -> str:
    health_percent = max(0, (target_current_hp - damage) / target_max_hp * 100)
    return f"# {actor_name} 对 {target_name} 的行动造成了{damage}点伤害, 当前 {target_name} 的生命值剩余 {health_percent}%。"


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
            [
                make_prop_prompt(prop, description_prompt=True, appearance_prompt=True)
                for prop in prop_files
            ]
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
            [
                make_prop_prompt(prop, description_prompt=True, appearance_prompt=True)
                for prop in prop_files
            ]
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


def make_skill_to_target_feedback_reasoning_prompt(
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

## 输出要求
- 请遵循 输出格式指南。
- 返回结果只带如下的键: {BroadcastAction.__name__} 和 {TagAction.__name__}。
- {BroadcastAction.__name__} 的内容格式要求为: "{target_name}对技能的反馈与更新后的状态描述"。
"""

    return prompt


################################################################################################################################################


def make_behavior_system_processed_result_notify_prompt(
    actor_name: str, behavior_sentence: str, result: bool
) -> str:
    if result:
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


def make_world_skill_system_off_line_prompt(
    actor_name: str, behavior_sentence: str
) -> str:

    prompt = f"""# 注意! 全局技能系统 处于离线状态或者出错，无法使用技能，请一会再试。
## 行动内容语句({actor_name} 发起)
{behavior_sentence}
## 以上的行动将无法执行（被系统强制取消），因为技能系统处于离线状态或者出错。
"""
    return prompt


################################################################################################################################################


def make_target_agent_off_line_prompt(
    actor_name: str, target_name: str, reasoning_sentence: str
) -> str:

    prompt = f"""# 注意! {actor_name} 无法对 {target_name} 使用技能，本次技能释放被系统取消。
## 行动内容语句({actor_name} 发起)
{reasoning_sentence}
"""
    return prompt


################################################################################################################################################
def make_world_skill_system_validate_skill_combo_fail_prompt(
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


def make_notify_others_of_skill_use_prompt(
    actor_name: str, target_name: str, reasoning_sentence: str
) -> str:

    prompt = f"""# 注意场景内发生了如下事件: {actor_name} 向 {target_name} 发动了技能。
## 关于事件描述
{reasoning_sentence}
"""
    return prompt


################################################################################################################################################


def make_equip_prop_weapon_prompt(actor_name: str, prop_file_weapon: PropFile) -> str:
    assert prop_file_weapon.is_weapon
    return f"""# {actor_name} 装备了武器: {prop_file_weapon.name} """


################################################################################################################################################


def make_equip_prop_clothes_prompt(actor_name: str, prop_file_clothes: PropFile) -> str:
    assert prop_file_clothes.is_clothes
    return f"""# {actor_name} 装备了衣服: {prop_file_clothes.name} """


################################################################################################################################################


def make_last_impression_of_stage_prompt(
    actor_name: str, stage_name: str, stage_narrate: str
) -> str:
    return f"""# {actor_name} 将要离开 {stage_name} 场景。
## 对于 {stage_name} 最后的印象如下:
{stage_narrate}"""


################################################################################################################################################


def make_equip_prop_not_found_prompt(actor_name: str, prop_name: str) -> str:
    return f"""# {actor_name} 没有道具: {prop_name}。所以无法装备。"""


################################################################################################################################################


################################################################################################################################################


def make_stage_remove_prop_success_prompt(stage_name: str, prop_name: str) -> str:
    return f"""# 场景 {stage_name} 内的道具 {prop_name} 已经被 {stage_name} 成功移除。
## 因果分析
{prop_name} 已经因某种原因被摧毁。 {stage_name} 作为其拥有者，根据游戏机制，主动将其移除。"""


################################################################################################################################################


def make_reasoning_actor_can_use_skill_prompt(
    actor_name: str,
    actor_body_info: str,
    skill_files: List[PropFile],
    prop_files: List[PropFile],
) -> str:

    skills_prompt: List[str] = []
    if len(skill_files) > 0:
        for skill_file in skill_files:
            skills_prompt.append(
                make_prop_prompt(
                    skill_file, description_prompt=True, appearance_prompt=False
                )
            )
    else:

        skills_prompt.append("- 无任何技能。")
        assert False, "技能不能为空"

    props_prompt: List[str] = []
    if len(prop_files) > 0:
        for prop_file in prop_files:
            props_prompt.append(
                make_prop_prompt(
                    prop_file, description_prompt=True, appearance_prompt=False
                )
            )
    else:
        props_prompt.append("- 无任何道具。")

    ret_prompt = f"""# {actor_name} 准备使用技能，请做出判断是否允许使用。

## {actor_name} 自身信息
{actor_body_info}
        
## 要使用的技能
{"\n".join(skills_prompt)}

## 使用技能时配置的道具
{"\n".join(props_prompt)}

## 判断的逻辑步骤
1. 检查 要使用的技能 的信息。结合 {actor_name} 自身信息 判断 {actor_name} 是否满足技能释放的条件。如果不能则技能释放失败。不用继续判断。
2. 检查 使用技能时配置的道具 的信息。结合 {actor_name} 自身信息 判断 {actor_name} 是否满足使用这些道具的条件。如果不能则技能释放失败。不用继续判断。
3. 分支判断 是否存在 使用技能时配置的道具。
    - 如存在。则结合 要使用的技能 与 使用技能时配置的道具 的信息进行综合半段。如果 技能对 配置的道具有明确的需求，且道具不满足，则技能释放失败。不用继续判断。
    - 如不存在。则继续下面的步骤。
4. 如果以上步骤都通过，则技能释放成功。

## 输出格式指南

### 请根据下面的示例, 确保你的输出严格遵守相应的结构。
{{
  "{MindVoiceAction.__name__}":["输入你的最终判断结果，技能是否可以使用成功或失败，并附带原因"],
  "{TagAction.__name__}":["Yes/No"(即技能是否可以使用成功或失败)"]
}}

### 注意事项
- 每个 JSON 对象必须包含上述键中的一个或多个，不得重复同一个键，也不得使用不在上述中的键。
- 输出不应包含任何超出所需 JSON 格式的额外文本、解释或总结。
- 不要使用```json```来封装内容。"""

    return ret_prompt


################################################################################################################################################


def make_reasoning_world_skill_system_validate_skill_combo_prompt(
    actor_name: str,
    actor_body_info: str,
    skill_files: List[PropFile],
    prop_files: List[PropFile],
    behavior_sentence: str,
) -> str:

    skills_prompt: List[str] = []
    if len(skill_files) > 0:
        for skill_file in skill_files:
            skills_prompt.append(
                make_prop_prompt(
                    skill_file, description_prompt=True, appearance_prompt=False
                )
            )
    else:
        skills_prompt.append("- 无任何技能。")
        assert False, "技能不能为空"

    props_prompt: List[str] = []
    if len(prop_files) > 0:
        for prop_file in prop_files:
            props_prompt.append(
                make_prop_prompt(
                    prop_file, description_prompt=True, appearance_prompt=False
                )
            )
    else:
        props_prompt.append("- 无任何道具。")

    ret_prompt = f"""# {actor_name} 准备使用技能，请你判断技能使用的合理性(是否符合游戏规则和世界观设计)。在尽量能保证游戏乐趣的情况下，来润色技能的描述。

## {actor_name} 自身信息
{actor_body_info}
        
## 要使用的技能
{"\n".join(skills_prompt)}

## 使用技能时配置的道具
{"\n".join(props_prompt)}

## 行动内容语句(请在这段信息内提取 技能释放的目标 的信息，注意请完整引用)
{behavior_sentence}

## 判断的逻辑步骤
1. 如果 配置的道具 存在。则需要将道具与技能的信息联合起来推理。
    - 推理结果 违反了游戏规则或世界观设计。则技能释放失败。即{ConstantPrompt.FAILURE}。
    - 推理结果合理的。则技能释放成功。即{ConstantPrompt.SUCCESS}。如果道具对技能有增益效果，则标记为{ConstantPrompt.CRITICAL_SUCCESS}。
2. 如果 配置的道具 不存在。则继续下面的步骤。
3. 结合 {actor_name} 的自身信息。判断是否符合技能释放的条件。
    - 如果不符合。则技能释放失败。即{ConstantPrompt.FAILURE}。
    - 如果符合。则技能释放成功。即{ConstantPrompt.SUCCESS}。如果 {actor_name} 的自身信息，对技能有增益效果，则标记为{ConstantPrompt.CRITICAL_SUCCESS}。

## 输出格式指南

### 请根据下面的示例, 确保你的输出严格遵守相应的结构。
{{
  "{BroadcastAction.__name__}":["输出结果"],
  "{TagAction.__name__}":["{ConstantPrompt.CRITICAL_SUCCESS}或{ConstantPrompt.SUCCESS}或{ConstantPrompt.FAILURE}"]
}}

### 关于 {BroadcastAction.__name__} 的输出结果的规则如下
- 如果你的判断是 {ConstantPrompt.SUCCESS} 或 {ConstantPrompt.CRITICAL_SUCCESS}。
    - 必须包含如下信息：{actor_name}的名字（技能使用者），释放的技能的描述，技能释放的目标的名字，配置的道具的信息。
    - 做出逻辑合理的句子描述（可以适当润色），来表达 {actor_name} 使用技能的使用过程。但不要判断技能命中目标之后，目标的可能反应。
    - 请注意，用第三人称的描述。  
- 如果你的判断是 {ConstantPrompt.FAILURE}。
    - 则输出结果需要描述为：技能释放失败的原因。
    
### 注意事项
- 每个 JSON 对象必须包含上述键中的一个或多个，不得重复同一个键，也不得使用不在上述中的键。
- 输出不应包含任何超出所需 JSON 格式的额外文本、解释或总结。
- 不要使用```json```来封装内容。"""

    return ret_prompt


################################################################################################################################################
