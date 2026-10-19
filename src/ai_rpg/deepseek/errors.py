"""DeepSeek 通讯层错误模型（实现层别名，保持向后兼容）。

错误类型本身与 provider 无关，已上移到 `ai_rpg.llm.errors.ChatError`；
这里保留 `DeepSeekError` 这个名字，使既有 `from ai_rpg.deepseek import DeepSeekError`
等导入点无需改动。`DeepSeekError is ChatError` 为 True（同一对象），
因此任何按 `ChatError` 标注的协议成员都接受 `DeepSeekError` 实例。
"""

from ..llm.errors import ChatError, ErrorKind

DeepSeekError = ChatError

__all__ = ["ChatError", "DeepSeekError", "ErrorKind"]
