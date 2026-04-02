"""tui_client 无状态工具方法"""

# 这些类别前缀保留在显示名中（不剥离首段）
_KEEP_PREFIXES = {"地下城"}


def display_name(full_name: str) -> str:
    """从实体全名中提取 UI 显示名。

    规则：去掉首段类别前缀，但 ``地下城`` 类别保留全名。

    例如：
        ``角色.旅行者.无名氏``  →  ``旅行者.无名氏``
        ``场景.断壁石室``       →  ``断壁石室``
        ``地下城.残柱外沿``     →  ``地下城.残柱外沿``
    """
    first_dot = full_name.find(".")
    if first_dot == -1:
        return full_name
    prefix = full_name[:first_dot]
    if prefix in _KEEP_PREFIXES:
        return full_name
    return full_name[first_dot + 1 :]
