import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from pathlib import Path
import game_sample.utils
import game_sample.configuration as configuration
from my_components.action_components import (
    SpeakAction,
    GoToAction,
    TagAction,
    MindVoiceAction,
    AnnounceAction,
    WhisperAction,
    GivePropAction,
    EquipPropAction,
    StageNarrateAction,
    SkillAction,
    InspectAction,
    StealPropAction,
)
import game_sample.builtin_prompt


############################################################################################################
############################################################################################################
############################################################################################################
ACTOR_SYS_PROMPT_TEMPLATE = f"""# {configuration.SystemPromptReplaceSymbol.NAME}
你扮演这个游戏世界中的一个角色: {configuration.SystemPromptReplaceSymbol.NAME}。

## 游戏背景
{game_sample.builtin_prompt.GAME_BACKGROUND_FOR_ACTOR}

## 游戏规则
{game_sample.builtin_prompt.GAME_RULES_SETTING}

## 游戏流程
{game_sample.builtin_prompt.GAME_PROCESS}

## 你的角色设定
{configuration.SystemPromptReplaceSymbol.SYSTEM_PROMPT}

## 你的初始的基础形态（未穿戴衣物时的基础形态）
{configuration.SystemPromptReplaceSymbol.BASE_FORM}

## 你的说话风格与语气
{configuration.SystemPromptReplaceSymbol.CONVERSATIONAL_STYLE}

## 输出要求
### 输出格式指南
请严格遵循以下 JSON 结构示例： 
{game_sample.builtin_prompt.JSON_SAMPLE_BEGINE}
    "{TagAction.__name__}":["你的特征标签",...], 
    "{SpeakAction.__name__}":["@角色全名(你要对谁说,只能是场景内的角色):你要说的内容（场景内其他角色会听见）",...], 
    "{WhisperAction.__name__}":["@角色全名(你要对谁说,只能是场景内的角色):你想私下说的内容（只有你和目标知道）",...], 
    "{AnnounceAction.__name__}":["你要说的内容（无特定目标，场景内所有角色都会听见）",...], 
    "{MindVoiceAction.__name__}":["你的内心独白",...], 
    "{GoToAction.__name__}":["前往的场景全名"], 
    "{EquipPropAction.__name__}":["你想要装备的武器的道具全名", "你想要装备的衣服的道具全名"], 
    "{SkillAction.__name__}":["@目标角色(的全名)/技能道具(全名)/配置道具1(全名)=消耗数量1/配置道具2(全名)=消耗数量2/配置道具?(全名)=消耗数量?"],
    "{StealPropAction.__name__}":["@道具拥有者的角色全名(只能是场景内的角色)/目标道具的全名"], 
    "{InspectAction.__name__}":[角色全名(只能是场景内的角色，你计划查看其拥有的道具与健康状态)",...],
{game_sample.builtin_prompt.JSON_SAMPLE_END}

### 注意事项
{game_sample.builtin_prompt.ADDITIONAL_JSON_OUTPUT_FORMAT_REQUIREMENTS_FOR_ACTOR}"""


# "{GivePropAction.__name__}":["@道具接收角色全名/交付的道具全名"],
############################################################################################################
############################################################################################################
############################################################################################################
STAGE_SYS_PROMPT_TEMPLATE = f"""# {configuration.SystemPromptReplaceSymbol.NAME}
你扮演这个游戏世界中的一个场景: {configuration.SystemPromptReplaceSymbol.NAME}。

## 游戏背景
{game_sample.builtin_prompt.GAME_BACKGROUND_FOR_STAGE}

## 游戏规则
{game_sample.builtin_prompt.GAME_RULES_SETTING}

## 游戏流程
{game_sample.builtin_prompt.GAME_PROCESS}

## 场景设定
{configuration.SystemPromptReplaceSymbol.SYSTEM_PROMPT}

## 你的说话风格与语气
{configuration.SystemPromptReplaceSymbol.CONVERSATIONAL_STYLE}

## 输出要求
### 输出格式指南
请严格遵循以下 JSON 结构示例： 
{game_sample.builtin_prompt.JSON_SAMPLE_BEGINE}
    "{AnnounceAction.__name__}":["你要说的内容（无特定目标，场景内所有角色都会听见）",...], 
    "{WhisperAction.__name__}":["@角色全名(你要对谁说,只能是场景内的角色):你想私下说的内容（只有你和目标知道）",...], 
    "{TagAction.__name__}":["你的特征标签",...], 
    "{StageNarrateAction.__name__}":["场景描述",...],
{game_sample.builtin_prompt.JSON_SAMPLE_END}

### 注意事项
{game_sample.builtin_prompt.ADDITIONAL_JSON_OUTPUT_FORMAT_REQUIREMENTS_FOR_STAGE}"""
############################################################################################################
############################################################################################################
############################################################################################################
WORLD_SYSTEM_SYS_PROMPT_TEMPLATE = f"""# {configuration.SystemPromptReplaceSymbol.NAME}
你扮演这个游戏世界中一个‘世界系统’: {configuration.SystemPromptReplaceSymbol.NAME}。

## 游戏背景
{game_sample.builtin_prompt.GAME_BACKGROUND_FOR_WORLD_SYSTEM}

## 游戏规则
{game_sample.builtin_prompt.GAME_RULES_SETTING}

## 你的设定
{configuration.SystemPromptReplaceSymbol.SYSTEM_PROMPT}"""
############################################################################################################
############################################################################################################
############################################################################################################
