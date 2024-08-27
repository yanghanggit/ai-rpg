from typing import Optional, List
from loguru import logger


#################################################################################################################################
# 我方定义的规则字符串
def parse_target_and_message(
    content: str, symbol1: str = "@", symbol2: str = ">"
) -> tuple[Optional[str], Optional[str]]:
    # 检查是否包含'@'和'>'符号
    if symbol1 not in content or symbol2 not in content:
        return None, content

    # 检查'@'是否出现在'>'之前
    at_index = content.find(symbol1)
    gt_index = content.find(symbol2)
    if at_index > gt_index:
        return None, content

    # 提取目标和消息
    try:
        target = content[at_index + 1 : gt_index].strip()
        message = content[gt_index + 1 :].strip()

        # 确保目标和消息不为空
        if not target or not message:
            return None, content

        return target, message
    except Exception as e:
        # 如果有任何异常，返回原始内容和异常提示
        return None, content


#################################################################################################################################
# 是否是有效的目标和消息格式
def is_target_and_message(content: str, symbol1: str = "@", symbol2: str = ">") -> bool:
    if symbol1 not in content or symbol2 not in content:
        return False
    return True


#################################################################################################################################
def make_target_and_message(
    target: str, message: str, symbol1: str = "@", symbol2: str = ">"
) -> str:
    return f"{symbol1}{target}{symbol2}{message}"


#################################################################################################################################


def target_and_message_values(values: List[str]) -> List[tuple[str, str]]:

    result: List[tuple[str, str]] = []

    for value in values:
        if not is_target_and_message(value):
            continue

        tp = parse_target_and_message(value)
        target: Optional[str] = tp[0]
        message: Optional[str] = tp[1]
        if target is None or message is None:
            logger.error(f"target is None: {value}")
            continue

        result.append((target, message))

    return result
