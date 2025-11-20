"""
Multi-Agents Game Framework 工具模块

这个包包含了游戏框架中使用的各种工具和实用函数。

主要模块：
- json_format: JSON格式化和处理工具
- excel_utils: Excel文件读取、处理和数据转换工具
"""

# JSON格式化工具
# Excel工具
from .excel import (
    convert_dict_to_model,
    display_excel_info,
    get_column_names,
    list_valid_rows,
    list_valid_rows_as_models,
    read_excel_file,
    safe_extract,
    safe_get_from_dict,
    safe_get_row_number,
    validate_dataframe,
)
from .json_format import (
    normalize_json_string,
    merge_json_fragments,
    has_multiple_json_objects,
)

from .md_format import (
    format_dict_as_markdown_list,
    format_list_as_markdown_list,
    has_json_code_block,
    extract_json_from_code_block,
)

# 公开的API
__all__ = [
    # JSON格式化工具
    "normalize_json_string",
    "merge_json_fragments",
    "has_multiple_json_objects",
    "has_json_code_block",
    "extract_json_from_code_block",
    # Excel工具
    "read_excel_file",
    "display_excel_info",
    "list_valid_rows",
    "safe_extract",
    "safe_get_from_dict",
    "get_column_names",
    "validate_dataframe",
    "safe_get_row_number",
    "convert_dict_to_model",
    "list_valid_rows_as_models",
    # Markdown格式化工具
    "format_dict_as_markdown_list",
    "format_list_as_markdown_list",
    "has_json_code_block",
    "extract_json_from_code_block",
]
