
from typing import Optional

class Console:

    #
    def __init__(self, name: str):
        self.name = name
    
    #
    def parse_command(self, input_val: str, split_str: str)-> str:
        if split_str in input_val:
            return input_val.split(split_str)[1].strip()
        return input_val

    #
    def parse_at_symbol(self, input_val: str) -> tuple[str, str]:
        if "@" not in input_val:
            return "", input_val
        start_index = input_val.index("@") + 1
        end_index = input_val.index(" ")
        p1 = input_val[start_index:end_index]
        message = input_val[end_index+1:]
        return p1, message
    
    
