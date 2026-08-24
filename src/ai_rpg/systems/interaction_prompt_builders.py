"""角色交互（说话/耳语）共享提示词构造函数。"""

from ..utils import prompt_builder


#######################################################################################################################################
@prompt_builder
def build_invalid_target_error_message(speaker_name: str, target_name: str) -> str:
    """构建交互目标不存在的错误提示（说话/耳语共用）。"""
    return f"""# 提示！{speaker_name} 试图对话，但 {target_name} 不在此处。

**提示：** 检查目标名称是否正确，或确认目标是否在当前场景中。"""
