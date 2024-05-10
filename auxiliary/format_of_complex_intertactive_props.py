#
def is_complex_interactive_props(interactiveprops: str) -> bool:
    #输入 = “(内容A|内容B|xxx)” 。如果输入符合这种格式，那么就是复杂条件。否则就不是
    return interactiveprops.startswith("(") and interactiveprops.endswith(")") and "|" in interactiveprops

def parse_complex_interactive_props(interactiveprops: str) -> list[str]:
    if is_complex_interactive_props(interactiveprops):
        # 当前认为输入都是 = “(内容A|内容B)” 。
        return interactiveprops[1:-1].split("|")
    return []