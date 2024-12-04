############################################################################################################
def is_complex_prop_name(data: str) -> bool:
    return data.startswith("/") and "=" in data


############################################################################################################
def _parse_prop_name_and_count(format_string: str) -> tuple[str, int]:

    assert is_complex_prop_name(
        format_string
    ), f"Invalid format string: {format_string}"

    parts = format_string.split("=")
    prop_name = parts[0][1:]  # Remove the leading "/"
    count = int(parts[1])
    if count < 1:
        count = 1

    return prop_name, count


############################################################################################################
def parse_complex_prop_name(prop_info_string: str) -> tuple[str, int]:

    # 如果data字符串在[0]第一个位置没有 "/", 就插入一个"/" 形成一个新字符串
    processed_prop_string = str(prop_info_string)
    if not prop_info_string.startswith("/"):
        # 开头没有"/"就插入一个
        processed_prop_string = "/" + prop_info_string
    else:
        assert (
            processed_prop_string.count("/") == 1
            and processed_prop_string.index("/") == 0
        ), f"Invalid format string: {processed_prop_string}"

    if "=" not in processed_prop_string:
        # 必须有一个数量
        processed_prop_string = processed_prop_string + "=1"
    else:
        # 只能有且只有一个"="
        assert (
            processed_prop_string.count("=") == 1
        ), f"Invalid format string: {processed_prop_string}"

    return _parse_prop_name_and_count(processed_prop_string)


############################################################################################################
def format_prop_name_with_count(prop_name: str, count: int) -> str:
    assert count > 0, f"Invalid count: {count}"
    return f"/{prop_name}={count}"


############################################################################################################
def match_prop_name(prop_name: str, complex_prop_name: str) -> bool:
    parsed_prop_name, _ = parse_complex_prop_name(complex_prop_name)
    return prop_name == parsed_prop_name


############################################################################################################
