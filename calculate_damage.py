import random


def calculate_damage(attacker, defender, attack_type="physical"):
    """
    计算一次攻击造成的伤害值（包含命中/闪避判定）。

    Parameters
    ----------
    attacker : dict
        进攻方的属性，例如：
        {
            "PhysicalAttack": 80,
            "MagicAttack": 50,
            "Accuracy": 40
        }

    defender : dict
        防守方的属性，例如：
        {
            "PhysicalDefense": 60,
            "MagicDefense": 30,
            "Evasion": 25,
            "HP": 100
        }

    attack_type : str, optional
        "physical" 或 "magic"。
        决定使用物理伤害公式还是魔法伤害公式，默认为 "physical"。

    Returns
    -------
    damage : int
        本次攻击对防守方造成的最终伤害值（未命中则为 0）。
    """

    # 1. 命中率计算
    attacker_acc = attacker.get("Accuracy", 0)
    defender_eva = defender.get("Evasion", 0)

    # 避免分母为 0 的情况
    if (attacker_acc + defender_eva) > 0:
        hit_rate = attacker_acc / (attacker_acc + defender_eva)
    else:
        hit_rate = 1.0  # 如果双方命中和闪避都为 0，可视为必定命中

    # 2. 命中判定
    rand_val = random.random()  # 生成 [0,1) 之间的随机数
    if rand_val > hit_rate:
        # 攻击未命中
        return 0

    # 3. 根据攻击类型，计算基础伤害
    if attack_type == "physical":
        # 物理伤害公式：
        # Damage = max(1, (PhysicalAttack * alpha) - PhysicalDefense)
        physical_attack = attacker.get("PhysicalAttack", 0)
        physical_defense = defender.get("PhysicalDefense", 0)

        # alpha 表示随机浮动，示例取 [0.9, 1.1] 之间
        alpha = random.uniform(0.9, 1.1)
        damage = (physical_attack * alpha) - physical_defense

    elif attack_type == "magic":
        # 魔法伤害公式：
        # Damage = max(1, (MagicAttack * beta) - MagicDefense)
        magic_attack = attacker.get("MagicAttack", 0)
        magic_defense = defender.get("MagicDefense", 0)

        # beta 同理，用于魔法伤害波动
        beta = random.uniform(0.9, 1.1)
        damage = (magic_attack * beta) - magic_defense

    else:
        # 未知攻击类型，视为无伤害
        return 0

    # 4. 设定伤害下限，避免出现 0 或负伤害
    final_damage = max(1, int(damage))

    return final_damage


def apply_damage(defender, damage):
    """
    将伤害应用到防守方，并返回更新后的 HP。

    defender : dict
        防守方属性，必须包含 "HP" 键。

    damage : int
        本次攻击造成的伤害值。
    """
    defender["HP"] = max(0, defender["HP"] - damage)
    return defender["HP"]


# ---------------- 示例测试 ----------------
if __name__ == "__main__":
    # 进攻方和防守方示例数据
    attacker_example = {"PhysicalAttack": 80, "MagicAttack": 50, "Accuracy": 40}
    defender_example = {
        "PhysicalDefense": 60,
        "MagicDefense": 30,
        "Evasion": 25,
        "HP": 100,
    }

    # 进行一次物理攻击
    dmg = calculate_damage(attacker_example, defender_example, attack_type="physical")
    print(f"物理攻击造成的伤害: {dmg}")

    # 更新防守者 HP
    updated_hp = apply_damage(defender_example, dmg)
    print(f"防守者剩余 HP: {updated_hp}")

    # 进行一次魔法攻击
    dmg = calculate_damage(attacker_example, defender_example, attack_type="magic")
    print(f"魔法攻击造成的伤害: {dmg}")

    updated_hp = apply_damage(defender_example, dmg)
    print(f"防守者剩余 HP: {updated_hp}")
