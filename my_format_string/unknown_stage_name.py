from enum import StrEnum, unique


@unique
class UnknownStageNameSymbol(StrEnum):
    GUID_FLAG = "%"
    UNKNOWN_STAGE_NAME_TAG = f"未知场景{GUID_FLAG}"


################################################################################################################################################
def generate_unknown_stage_name(guid: int) -> str:
    return f"{UnknownStageNameSymbol.UNKNOWN_STAGE_NAME_TAG}{guid}"


################################################################################################################################################
def is_unknown_stage_name(stage_name: str) -> bool:
    return UnknownStageNameSymbol.UNKNOWN_STAGE_NAME_TAG in stage_name


################################################################################################################################################
def extract_guid_from_unknown_stage_name(stage_name: str) -> int:
    if not is_unknown_stage_name(stage_name):
        return 0
    return int(stage_name.split(UnknownStageNameSymbol.GUID_FLAG)[1])


################################################################################################################################################
