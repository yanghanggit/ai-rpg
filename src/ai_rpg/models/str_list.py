"""LLM 文本字段（``List[str]``）的统一清洗与渲染。

全局约定：这类字段一律是「多值」列表，每个元素必须是一条完整、独立的字符串。

- 生成/填充端：用 ``normalize_str_list`` 去首尾空白、丢弃空项、按首次出现顺序去重；
  Pydantic 模型字段可直接引用 ``NormalizedStrList`` 注解获得同样效果。
- 系统消费端：用 ``render_str_list`` / ``render_labeled_str_list`` 逐条分行渲染，
  禁止再用 ``"、".join`` 之类把多条独立条目合并成一个整段字符串。
"""

from typing import Annotated, Iterable, List

from pydantic import AfterValidator


#######################################################################################################################################
def normalize_str_list(items: Iterable[str]) -> List[str]:
    """清洗多值字段：去首尾空白、丢弃空项、按首次出现顺序去重。"""
    normalized: List[str] = []
    for item in items:
        text = item.strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


# 供 Pydantic 字段直接引用的注解：解析 LLM 输出时自动清洗多值字段。
NormalizedStrList = Annotated[List[str], AfterValidator(normalize_str_list)]


#######################################################################################################################################
def render_str_list(items: Iterable[str], indent: str = "") -> str:
    """逐条分行渲染多值字段（每项 ``{indent}- 元素``）；空列表返回「无」。"""
    normalized = normalize_str_list(items)
    if not normalized:
        return "无"
    return "\n".join(f"{indent}- {item}" for item in normalized)


#######################################################################################################################################
def render_labeled_str_list(
    label: str, items: Iterable[str], indent: str = "  "
) -> str:
    """渲染「标签 + 多值条目」块：空列表为 ``{label}：无``，否则标签后逐条分行。"""
    normalized = normalize_str_list(items)
    if not normalized:
        return f"{label}：无"
    body = "\n".join(f"{indent}- {item}" for item in normalized)
    return f"{label}：\n{body}"
