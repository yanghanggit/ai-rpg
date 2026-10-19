"""chat dump：把 DeepSeekClient 每轮的完整对话落盘到 `.chat_dumps/` 下的文本文件。

调试用途的旁路能力，从 `client.py` 抽出来单独存放，避免调试代码污染通信层主流程。

开关 `chat_dump_enabled` 默认关闭；`dbg_agent_game.py` 等调试入口在运行时打开。
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final, List

from loguru import logger

from ..models import AIMessage, ChatMessage, HumanMessage, get_buffer_string

if TYPE_CHECKING:
    from .client import DeepSeekClient

############################################################################################################
# chat dump 存储目录（项目根目录下）
CHAT_DUMP_DIR: Path = Path(".chat_dumps")
CHAT_DUMP_DIR.mkdir(parents=True, exist_ok=True)
assert CHAT_DUMP_DIR.exists(), f"找不到目录: {CHAT_DUMP_DIR}"

# chat dump 全局开关（默认关闭）；dbg_agent_game.py 等调试入口会在运行时打开
chat_dump_enabled: bool = False

_SEP = "-" * 86

# 文件名安全字符集：中文、字母、数字与 _ - .；其余（含 | : / \ 空格 等）替换为下划线
_SAFE_FILENAME_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"[^0-9A-Za-z_\-.\u4e00-\u9fff]"
)


############################################################################################################
def dump_chat(client: DeepSeekClient) -> None:
    """将 client 本轮的完整对话写入 .chat_dumps/ 下的文本文件。"""

    try:

        # 拷贝 messages，再把本轮 prompt / response 分别补齐，
        # 使全部消息（含本轮）统一交给 get_buffer_string.
        messages: List[ChatMessage] = list(client._messages)

        # 仅在 prompt 非空时追加本轮 prompt：continuation 模式下 prompt 为空，
        # 不应产生一条幽灵空 Human 消息。
        if client._input_message:
            messages.append(HumanMessage(content=client._input_message))

        # 追加本轮 response：优先用原始 AIMessage（保留 tool_calls 等 additional_kwargs）；
        # 仅当响应缺失（如 200 但空 choices）时才退化为纯文本。
        if client._response_ai_message is not None:
            messages.append(client._response_ai_message)
        else:
            messages.append(AIMessage(content=client.response_content))

        # 提取对话内容为字符串，带有分隔符和角色标记；
        # chat dump 用于调试，需渲染 tool_calls（否则工具调用显示为空 AI:）。
        content = get_buffer_string(
            messages,
            system_prefix="\n" + _SEP + "\nSystem",
            human_prefix="\n" + _SEP + "\nHuman",
            ai_prefix="\n" + _SEP + "\nAI",
            tool_prefix="\n" + _SEP + "\nTool",
            render_tool_calls=True,
        )

        # Reasoning（可选）
        if client.response_reasoning_content:
            content += "\n" + _SEP + "\n" + client.response_reasoning_content

        # 内容结束。
        content += "\n"

        # 写入文件，文件名格式为：YYYYMMDD_HHMMSS_microseconds_label.txt
        # label 可能带「主体|服务对象」这类分隔标记（如外观合成），且含路径分隔符/冒号等
        # 会破坏文件名的字符；统一把非 [中文 字母 数字 _ - .] 的字符换成 "_"。
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_label = _SAFE_FILENAME_PATTERN.sub("_", client._label)
        dump_file = CHAT_DUMP_DIR / f"{timestamp}_{safe_label}.txt"
        CHAT_DUMP_DIR.mkdir(parents=True, exist_ok=True)
        dump_file.write_text(content, encoding="utf-8")
        logger.debug(f"chat dump saved: {dump_file}")

    except Exception as e:

        logger.warning(
            f"dump_chat failed for '{client._label}': {type(e).__name__}: {e}"
        )
