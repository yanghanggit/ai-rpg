from typing import List


def decompose_skill_command(skill_command: str) -> List[str]:
    skill_command = skill_command.strip()
    if "@" not in skill_command or "/" not in skill_command:
        return []

    parsed_targets: List[str] = []
    parsed_props: List[str] = []

    split_parts = skill_command.split("/")
    for part in split_parts:
        if "@" in part:
            split_targets = part.split("@")
            for target in split_targets:
                if target != "":
                    parsed_targets.append(target)
        else:
            if part != "":
                parsed_props.append(part)

    # 最终返回
    ret: List[str] = []
    ret.extend(parsed_targets)
    ret.extend(parsed_props)
    return ret


######################################################################################################################################################
def compose_skill_command(
    targets: List[str], skill_name: str, skill_accessory_props: List[tuple[str, int]]
) -> str:

    ret: List[str] = []
    for target in targets:
        ret.append(f"""@{target}""")

    ret.append(f"""/{skill_name}""")

    for skill_prop in skill_accessory_props:
        prop_name, consume_count = skill_prop
        ret.append(f"""/{prop_name}={consume_count}""")

    return "".join(ret)


######################################################################################################################################################


if __name__ == "__main__":

    test1 = decompose_skill_command("@角色.陈洛/技能.基础剑术/武器.黄巾军长剑")
    test2 = decompose_skill_command("@角色.陈洛/技能.基础治疗/消耗品.槁粮饼=1")
    test3 = decompose_skill_command(
        "@角色.陈洛@角色.邓茂/技能.基础治疗/消耗品.槁粮饼=1/消耗品.赤草"
    )

    print(test1)
