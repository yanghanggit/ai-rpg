############################################################################################################
def _parse_prop_name_and_count(format_string: str) -> tuple[str, int]:
    assert "/" in format_string, f"Invalid format string: {format_string}"
    assert "=" in format_string, f"Invalid format string: {format_string}"
    parts = format_string.split("=")
    prop_name = parts[0][1:]  # Remove the leading "/"
    count = int(parts[1])

    return prop_name, count


############################################################################################################
def parse_prop_name_and_count(data: str) -> tuple[str, int]:

    # 如果data字符串在[0]第一个位置没有 "/", 就插入一个"/" 形成一个新字符串
    handle_data = data
    if not data.startswith("/"):
        # 开头没有"/"就插入一个
        handle_data = "/" + data
    else:
        assert (
            handle_data.count("/") == 1 and handle_data.index("/") == 0
        ), f"Invalid format string: {handle_data}"

    if "=" not in handle_data:
        # 必须有一个数量
        handle_data = handle_data + "=1"
    else:
        # 只能有且只有一个"="
        assert handle_data.count("=") == 1, f"Invalid format string: {handle_data}"

    return _parse_prop_name_and_count(handle_data)


############################################################################################################
