from ..models import (
    Boot,
    Item,
    # ItemType,
)
from .actor_warrior import create_actor_warrior
from .actor_wizard import create_actor_wizard
from .campaign_setting import FANTASY_WORLD_RPG_CAMPAIGN_SETTING
from .stage_heros_camp import (
    create_demo_heros_camp,
    create_demo_heros_restaurant,
)


#######################################################################################################################
def create_demo_game_world(game_name: str) -> Boot:
    # 创建世界
    world_boot = Boot(
        name=game_name, campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING
    )

    # 创建英雄营地场景和角色
    actor_warrior = create_actor_warrior()
    actor_warrior.inventory.items.append(
        Item(
            name="消耗品.测试的药水",
            description="这是一瓶测试用的药水，能恢复50%生命值。",
        )
    )

    actor_wizard = create_actor_wizard()
    stage_heros_camp = create_demo_heros_camp()
    stage_heros_restaurant = create_demo_heros_restaurant()

    # 设置关系和消息
    stage_heros_camp.actors = [actor_warrior, actor_wizard]

    # 设置角色的初始状态
    actor_warrior.kick_off_message += f"""\n注意:{actor_wizard.name} 是你的同伴。你战斗时喜欢先用盾牌或者钉头锤击晕敌人再发动攻击，这样可以造成更高的伤害。你也会架起剑势先观察敌人的攻击再进行反击，遇到危险时你的保命手段就是用短剑或者战驽限制敌人的行动然后与其拉开距离。你讨厌火元素的法术，因为你认为它们是邪恶的。如果你遇到使用火元素魔法的人，你会立刻将攻击目标变成这个人，就算这个人是你的同伴你也会毫不犹豫的攻击。"""
    actor_wizard.kick_off_message += f"""\n注意:{actor_warrior.name} 是你的同伴。你最擅长的是古代科技结合火焰的魔法，你战斗时喜欢先给自己和同伴施加增益效果，然后再蓄力施展火焰魔法，因为火焰魔法施法缓慢，并且容易误伤自己，所以你要确保自身和队友得到保护才会开始攻击。你对人类特别有好感，除了喜欢人类的食物外，你还喜欢他们的风土人情，并且你是个话痨，特别喜欢和别人聊天，会不停的问别人问题，如果是人类，你还会主动和他们交谈并一直问有关人类的事情。你说话的语气特别欢快，不时也会说一些笑话来逗别人开心。但是你还有一个不为别人知道的秘密：你深刻理解黑暗元素的力量，但是不会轻易使用它，如果面对你最讨厌的东西——哥布林的时候你会暂时忘记别的魔法，毫不犹豫运用这种黑暗与科技力量的结合将其清除。"""

    # 设置英雄营地场景的初始状态
    world_boot.stages = [stage_heros_camp]

    # 添加世界系统
    world_boot.world_systems = []

    # 返回
    return world_boot


#######################################################################################################################
