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
    # PickUpPropAction,
    GivePropAction,
    EquipPropAction,
    StageNarrateAction,
    # StagePropDestructionAction,
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
{configuration.SystemPromptReplaceSymbol.CONVERSATION_EXAMPLE}

## 输出要求
### 输出格式指南
请严格遵循以下 JSON 结构示例： 
{game_sample.builtin_prompt.JSON_SAMPLE_BEGINE}
    "{TagAction.__name__}":["你的特征标签",...], 
    "{SpeakAction.__name__}":["@角色全名(你要对谁说,只能是场景内的角色)>你要说的内容（场景内其他角色会听见）",...], 
    "{WhisperAction.__name__}":["@角色全名(你要对谁说,只能是场景内的角色)>你想私下说的内容（只有你和目标知道）",...], 
    "{AnnounceAction.__name__}":["你要说的内容（无特定目标，场景内所有角色都会听见）"], 
    "{MindVoiceAction.__name__}":["你的内心独白",...], 
    "{GoToAction.__name__}":["前往的场景全名"], 
    "{GivePropAction.__name__}":["@道具接收角色全名/交付的道具全名"], 
    "{EquipPropAction.__name__}":["你拥有的(武器)道具全名", "你拥有的(衣服)道具全名",...], 
{game_sample.builtin_prompt.JSON_SAMPLE_END}

### 注意事项
{game_sample.builtin_prompt.ADDITIONAL_JSON_OUTPUT_FORMAT_REQUIREMENTS_FOR_ACTOR}"""


##"{PickUpPropAction.__name__}":["在本场景内的道具的全名（表示你要拾取它）"],
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
{configuration.SystemPromptReplaceSymbol.CONVERSATION_EXAMPLE}

## 输出要求
### 输出格式指南
请严格遵循以下 JSON 结构示例： 
{game_sample.builtin_prompt.JSON_SAMPLE_BEGINE}
    "{AnnounceAction.__name__}":["你要说的内容（无特定目标，场景内所有角色都会听见）"], 
    "{WhisperAction.__name__}":["@角色全名(你要对谁说,只能是场景内的角色)>你想私下说的内容（只有你和目标知道）",...], 
    "{TagAction.__name__}":["你的特征标签",...], 
    "{StageNarrateAction.__name__}":["场景描述（生成规则见下文）"],
{game_sample.builtin_prompt.JSON_SAMPLE_END}

### 注意事项
{game_sample.builtin_prompt.ADDITIONAL_JSON_OUTPUT_FORMAT_REQUIREMENTS_FOR_STAGE}

### 补充：{StageNarrateAction.__name__} —— 场景描述生成规则
#### 步骤
1. 事件回顾：回顾已发生的角色行为、对话和道具使用，判断其对场景的影响。不要推测未发生的活动。
3. 状态更新与描述：结合事件回顾和场景设定，生成场景的更新描述，突出环境背景、光线、气味、音效等关键细节。
4. 角色信息排除：移除所有角色相关信息，仅保留场景状态的描述。
#### 注意！
- 输出应清晰反映场景的最新状态和变化，不应包含角色的活动或心理。
- 确保描述有层次感，充分展示场景的状态更新。"""


##"{StagePropDestructionAction.__name__}":["场景内被破坏的道具全名（触发规则见下文'道具破坏的逻辑处理'）"],
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
