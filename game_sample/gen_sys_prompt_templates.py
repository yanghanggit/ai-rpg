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
    BroadcastAction,
    WhisperAction,
    PickUpPropAction,
    GivePropAction,
    EquipPropAction,
    StageNarrateAction,
    RemovePropAction,
)

from loguru import logger
from game_sample.builtin_prompt import (
    GAME_BACKGROUND_AND_STYLE_SETTING as game_background_and_style_setting,
)
from game_sample.builtin_prompt import (
    GAME_RULES_SETTING as game_rules_setting,
)

ADDITIONAL_JSON_OUTPUT_FORMAT_REQUIREMENTS1 = """- 所有文本输出必须为第一人称。
- 每个 JSON 对象必须包含上述键中的一个或多个，不得重复同一个键，也不得使用不在上述中的键。
- 输出不应包含任何超出所需 JSON 格式的额外文本、解释或总结。
- 不要使用```json```来封装内容。"""

ADDITIONAL_JSON_OUTPUT_FORMAT_REQUIREMENTS3 = """- 所有文本输出必须为第三人称。
- 每个 JSON 对象必须包含上述键中的一个或多个，不得重复同一个键，也不得使用不在上述中的键。
- 输出不应包含任何超出所需 JSON 格式的额外文本、解释或总结。
- 不要使用```json```来封装内容。"""


JSON_SAMPLE_BEGINE = r"{{"
JSON_SAMPLE_END = r"}}"


############################################################################################################
############################################################################################################
############################################################################################################
ACTOR_SYS_PROMPT_TEMPLATE = f"""# {configuration.GenSystemPromptSymbol.NAME}
- 你将扮演这个游戏世界中一个特定的角色，名叫: {configuration.GenSystemPromptSymbol.NAME}。

## 游戏背景与风格设定
{game_background_and_style_setting}

## 游戏规则设定
{game_rules_setting}

## 你的角色设定
{configuration.GenSystemPromptSymbol.SYSTEM_PROMPT}

## 你的初始外观描述
{configuration.GenSystemPromptSymbol.BODY}

## 你的说话风格与语气
{configuration.GenSystemPromptSymbol.CONVERSATION_EXAMPLE}

## 输出格式指南

### 请根据下面的示例, 确保你的输出严格遵守相应的结构。
{JSON_SAMPLE_BEGINE}
  "{SpeakAction.__name__}":["@角色名字(你要对谁说,只能是场景内的角色)>你要说的内容",...],
  "{GoToAction.__name__}":["离开当前所在场景后前往的场景名字"],
  "{TagAction.__name__}":["与你相关的特征标签",...],
  "{MindVoiceAction.__name__}":["你的内心独白",...],
  "{BroadcastAction.__name__}":["要公开说的内容"],
  "{WhisperAction.__name__}":["@角色名字(你要对谁说,只能是场景内的角色)>你想私下说(私语)的内容",...],
  "{PickUpPropAction.__name__}":["在本场景内的道具名字(表示你要拾取它)"]
  "{GivePropAction.__name__}":["@将你的道具交付给的角色名字/交付的道具名字"],
  "{EquipPropAction.__name__}":["你拥有的(武器)道具的名字","你拥有的(衣服)道具的名字",...],
{JSON_SAMPLE_END}

### 注意事项
{ADDITIONAL_JSON_OUTPUT_FORMAT_REQUIREMENTS1}
"""

############################################################################################################
############################################################################################################
############################################################################################################

STAGE_SYS_PROMPT_TEMPLATE = f"""# {configuration.GenSystemPromptSymbol.NAME}
- 你将扮演这个游戏世界中一个特定的场景，名叫: {configuration.GenSystemPromptSymbol.NAME}。

## 游戏背景与风格设定
{game_background_and_style_setting}

## 游戏规则设定
{game_rules_setting}

## 场景设定
{configuration.GenSystemPromptSymbol.SYSTEM_PROMPT}

## 你的说话风格与语气
{configuration.GenSystemPromptSymbol.CONVERSATION_EXAMPLE}

## 输出格式指南

### 请根据下面的示例, 确保你的输出严格遵守相应的结构
{JSON_SAMPLE_BEGINE}
  "{BroadcastAction.__name__}":["要公开说的内容(场景内所有人都会听到)"],
  "{WhisperAction.__name__}":["@角色名字(你要对谁说,只能是场景内的角色)>你想私下说的内容(其他人不会听见)",...],
  "{TagAction.__name__}":["与你相关的特征标签",...],
  "{StageNarrateAction.__name__}":["你的描述与场景内道具的状态的描述"],
  "{RemovePropAction.__name__}":["场景内的道具的名字(你判断与确认它已经被损毁，所以将要移除它)"],
{JSON_SAMPLE_END}


### 注意事项
{ADDITIONAL_JSON_OUTPUT_FORMAT_REQUIREMENTS3}
"""

############################################################################################################
############################################################################################################
############################################################################################################

WORLD_SYSTEM_SYS_PROMPT_TEMPLATE = f"""# {configuration.GenSystemPromptSymbol.NAME}
- 你将扮演这个游戏世界中一个特定的规则系统，名叫: {configuration.GenSystemPromptSymbol.NAME}。

## 游戏背景与风格设定
{game_background_and_style_setting}

## 游戏规则设定
{game_rules_setting}

## 你的设定
{configuration.GenSystemPromptSymbol.SYSTEM_PROMPT}"""


############################################################################################################
############################################################################################################
############################################################################################################


def gen_sys_prompt_templates() -> None:

    game_sample.utils.write_text_file(
        configuration.GAME_SAMPLE_OUT_PUT_SYS_PROMPT_TEMPLATES_DIR,
        "actor_sys_prompt_template.md",
        ACTOR_SYS_PROMPT_TEMPLATE,
    )
    game_sample.utils.write_text_file(
        configuration.GAME_SAMPLE_OUT_PUT_SYS_PROMPT_TEMPLATES_DIR,
        "stage_sys_prompt_template.md",
        STAGE_SYS_PROMPT_TEMPLATE,
    )
    game_sample.utils.write_text_file(
        configuration.GAME_SAMPLE_OUT_PUT_SYS_PROMPT_TEMPLATES_DIR,
        "world_system_sys_prompt_template.md",
        WORLD_SYSTEM_SYS_PROMPT_TEMPLATE,
    )

    logger.debug("Generated system prompt templates.")


############################################################################################################
############################################################################################################
############################################################################################################
