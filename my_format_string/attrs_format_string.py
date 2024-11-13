from typing import List


#################################################################################################################################
def from_int_attrs_to_string(values: List[int], symbol: str = ",") -> str:
    return symbol.join(map(str, values))


#################################################################################################################################
def from_string_to_string_attrs(content: str, symbol: str = ",") -> List[str]:
    return content.split(symbol)


#################################################################################################################################
def from_string_to_int_attrs(content: str, symbol: str = ",") -> List[int]:
    return list(map(int, content.split(symbol)))


#################################################################################################################################
