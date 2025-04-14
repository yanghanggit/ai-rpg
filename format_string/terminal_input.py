from typing import Dict, Set, TypedDict, cast
from loguru import logger


############################################################################################################
############################################################################################################
############################################################################################################
def _parse_user_action_input(usr_input: str, keys: Set[str]) -> Dict[str, str]:

    ret: Dict[str, str] = {}
    try:
        parts = usr_input.split("--")
        args = {
            part.split("=")[0].strip(): part.split("=")[1].strip()
            for part in parts
            if "=" in part
        }

        for key in keys:
            if key in args:
                ret[key] = args[key]

    except Exception as e:
        logger.error(f" {usr_input}, 解析输入时发生错误: {e}")

    return ret


############################################################################################################
############################################################################################################
############################################################################################################
class SpeakCommand(TypedDict):
    target: str
    content: str


# sample: /speak --target=角色.法师.奥露娜 --content=我还是需要准备一下
def parse_speak_command_input(usr_input: str) -> SpeakCommand:
    ret: SpeakCommand = {"target": "", "content": ""}
    if "/speak" in usr_input or "/ss" in usr_input:
        return cast(
            SpeakCommand, _parse_user_action_input(usr_input, {"target", "content"})
        )

    return ret


############################################################################################################
############################################################################################################
############################################################################################################
