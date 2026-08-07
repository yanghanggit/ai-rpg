from markdown_it import MarkdownIt

_md = MarkdownIt()


def extract_json(markdown_text: str) -> str:
    """
    从Markdown文本中提取JSON内容，移除代码块标记。

    使用 markdown-it-py（CommonMark 标准解析器）解析 token 流，
    返回第一个 ```json 或 ~~~json 围栏代码块的内容。

    Args:
        markdown_text: 可能包含JSON代码块的Markdown文本

    Returns:
        提取出的JSON字符串；若无JSON代码块则原样返回
    """
    for token in _md.parse(markdown_text):
        if token.type == "fence":
            info = token.info.strip()
            if info and info.split()[0].lower() == "json":
                return token.content.strip()
    return markdown_text
