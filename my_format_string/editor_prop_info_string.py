############################################################################################################
def check_prop_name_and_count_format(data: str) -> bool:
    return data.startswith("/") and "=" in data


############################################################################################################
def _extract_prop_name_and_count(format_string: str) -> tuple[str, int]:

    assert check_prop_name_and_count_format(
        format_string
    ), f"Invalid format string: {format_string}"

    parts = format_string.split("=")
    prop_name = parts[0][1:]  # Remove the leading "/"
    count = int(parts[1])
    if count < 1:
        count = 1

    return prop_name, count


############################################################################################################
def extract_prop_name_and_count(input_string: str) -> tuple[str, int]:

    # 如果data字符串在[0]第一个位置没有 "/", 就插入一个"/" 形成一个新字符串
    handle_string = str(input_string)
    if not input_string.startswith("/"):
        # 开头没有"/"就插入一个
        handle_string = "/" + input_string
    else:
        assert (
            handle_string.count("/") == 1 and handle_string.index("/") == 0
        ), f"Invalid format string: {handle_string}"

    if "=" not in handle_string:
        # 必须有一个数量
        handle_string = handle_string + "=1"
    else:
        # 只能有且只有一个"="
        assert handle_string.count("=") == 1, f"Invalid format string: {handle_string}"

    return _extract_prop_name_and_count(handle_string)


############################################################################################################
def generate_prop_name_and_count_format_string(prop_name: str, count: int) -> str:
    assert count > 0, f"Invalid count: {count}"
    return f"/{prop_name}={count}"


############################################################################################################
