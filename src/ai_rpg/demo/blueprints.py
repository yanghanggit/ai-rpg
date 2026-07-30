"""演示世界创建模块

提供工厂函数创建预配置的游戏世界，包括双角色和单角色版本。
"""

from ..models import (
    Blueprint,
    CostumeItem,
    GearItem,
    ConsumableItem,
    MaterialItem,
    TargetType,
    CharacterStats,
    create_stage,
    StageProfile,
    StageType,
    Stage,
    RPG_SYSTEM_RULES,
    create_actor,
    CharacterSheet,
    ActorType,
    Actor,
    ComponentSerialization,
    DungeonGenerationComponent,
    create_world_system,
    WorldSystem,
    PlayerActionAuditComponent,
    WorkshopComponent,
)
from .settings import CAMPAIGN_SETTING, KNOWLEDGE_BASE


#######################################################################################################################
def create_broken_wall_enclosure() -> Stage:
    """
    创建断壁石室场景实例
    """

    return create_stage(
        name="场景.断壁石室",
        stage_profile=StageProfile(
            name="broken_wall_enclosure",
            type=StageType.HOME,
            profile="""你是沙漠残垣遗迹深处的一处封闭内室，由两面仍完整交汇的厚重石墙构成墙角，顶部横压着一块因地基沉降而错位下滑的巨型石楣，将空间压得低矮而幽暗。
唯一的出入口是石楣与右侧断壁之间遗留的一道窄缝，宽度仅容一人侧身通过。室内地面铺有石板，缝隙中积着细沙，靠墙角的石板面较其他处更为平整干燥。
石楣遮挡了日光与风沙，室内气温明显低于外部，空气中有砂岩特有的干燥矿物气息。外部的风声与沙粒撞击石墙的声响在此处显得遥远而模糊。""",
        ),
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
    )


#######################################################################################################################
def create_stone_platform() -> Stage:
    """
    创建石台广场场景实例。
    """

    return create_stage(
        name="场景.石台广场",
        stage_profile=StageProfile(
            name="stone_platform",
            type=StageType.HOME,
            profile="""你是沙漠残垣遗迹中央的开阔地带，地面由大块灰白色石板铺就，石板间的接缝已被风沙填平，部分石板边缘微微翘起。
场地内竖立着数根高矮不一的断柱与风蚀石墩，截面平整，石面上覆有一层薄薄的沙尘。四周是低矮的碎石堆与零散的残垣，视野向远处的沙丘和风蚀岩柱敞开。
日光直射在石台上，石板表面温度极高，靠近断柱底部的背阴处有少量细沙聚积。某些方向的地平线上可见更规整的石堆轮廓。""",
        ),
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
    )


#######################################################################################################################
def create_scholar() -> Actor:
    """
    创建失忆学者角色实例（代号：寒蝉）。
    """

    actor = create_actor(
        name="学者.寒蝉",
        character_sheet=CharacterSheet(
            name="scholar",
            type=ActorType.NPC,
            profile="""**历史**: 你没有历史，或者说，你记不起来。你醒来时坐靠在遗迹的一根断柱边，膝盖上压着一本残破的笔记。翻开来全是密密麻麻的手写记录——字迹是你的，你认出了这一点，但每一个字都像是某种你不认识的密文，无法读懂。整本册子，你只找到了一行明文，写在最末的空白页上：「寒蝉，如果你看到这里，说明计划出了问题。」你不知道寒蝉是什么，直到意识到，那大概是你自己。
**性格**: 你冷静，习惯用语言把观察到的东西整理清楚。比起沉默，你更倾向于开口，但说的往往是事实与推断，不是情绪。
**禁忌**: 你对毫无依据的臆断和盲目破坏未知事物有明确的反感，即使对方出于好意。
**最爱**: 把新发现的东西记进笔记；安静的时候拿出那本看不懂的旧记录，盯着上面的字迹发呆。""",
            base_body="二十五岁上下的女性，仅着简单内衣。骨架纤细，体态偏瘦，肩强笺小，锁骨稍显。胸领平坦，腰鈃细体但缺乏曲线感，双腿细长。肤色较浅，眼下有淡淡的暗沉，手腕内侧几条细血管隐隐可见。右手中指有长期握笔留下的淡色压痕。关节细小而明显，整体属于从事脑力劳动而非体力劳动的少年女性体型。",
        ),
        character_stats=CharacterStats(),
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        keywords=[
            "状态控制型：每张卡牌必须携带至少一个持续生效的负面状态（如虚弱、减速、灼烧），以给敌人施加长期控制效果为核心目标，直接伤害可以较低乃至为零。骰值 0-30 为失败，状态持续时间短或效果微弱；骰值 31-70 为正常，状态稳定可靠；骰值 71-100 为优质，状态效果显著增强或同时附带多个负面状态。"
        ],
    )

    return actor


#######################################################################################################################
def create_wanderer() -> Actor:
    """
    创建失忆旅行者角色实例（无名氏）。
    """
    actor = create_actor(
        name="旅行者.无名氏",
        character_sheet=CharacterSheet(
            name="wanderer",
            type=ActorType.NPC,
            profile="""**历史**: 你没有历史。你醒来时仰躺在一片石板地面上，头顶是刺眼的日光与几根错位的断柱。手边什么都没有，脑海里也什么都没有——没有来处，没有去处，连名字也没有。你不知道自己是谁，也不知道为什么会出现在这里。"无名氏"不是名字，只是你暂时没有更好的东西可以用。
**性格**: 你沉默，观察多于开口。面对陌生的事物不会慌乱，而是停下来，仔细看，仔细想，再决定怎么做。你不排斥危险，但也不会轻易莽撞。
**禁忌**: 你对任何人强行拿走你身上仅有的东西、或强迫你去某个地方有本能的抵触。
**最爱**: 你发现自己喜欢在天刚亮、气温尚未攀升时独自在遗迹里走动，那时候周围很安静。""",
            base_body="年近三十的男性，仅着简单内衣。身形清瘦但不单薄，肩頸窄甄，胸领小，腰鈃紧进，没有明显的肌肉块感却也不浮肿，是长期行路的人才有的体型。肤色偏浅，颈臂交界处露出初晒的淡红痕迹，胸海和小腹胤色较浅。双腿细长而有力，小腿肌肉线条明显。手指细长，承接对点有轻茧。面容轮廓分明，眼神深沉，沉默时像在看某个他人看不见的地方。",
        ),
        character_stats=CharacterStats(),
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        keywords=[
            "即时破甲型：每张卡牌必须携带至少一个在出牌时立即生效的特殊效果，优先体现破甲、穿透、无视防御等特性；攻击必须造成直接伤害，特殊效果在本次结算中即时生效。骰值 0-30 为失败，破甲效果微弱、伤害偏低；骰值 31-70 为正常，效果稳定清晰；骰值 71-100 为优质，穿透效果犀利且伤害偏高。",
        ],
    )

    return actor


#######################################################################################################################
def create_ruins_blueprint(game_name: str) -> Blueprint:
    """
    创建演示游戏世界Blueprint实例 - 旅行者与学者双角色版本。
    """

    # 创建英雄营地场景和角色
    actor_wanderer = create_wanderer()
    actor_wanderer.custom_item = CostumeItem(
        name="时装.旅行者风尘斗篸",
        description="一件覆盖全身的宽幅斗篷，布料经风沙磨砺后呈不均匀的赭石色，边缘绣有简单的几何暗纹。披上后显得愈发像一名经历颇丰的旅人。",
    )

    # 调整旅行者的速度属性，增加其在 SPEED_ORDER 策略下的出手优先级
    actor_wanderer.character_stats.speed = 2

    # 调整旅行者的攻击属性，增加其战斗能力，便于快速演示战斗系统
    actor_wanderer.character_stats.attack = 100

    # 创建学者角色
    actor_scholar = create_scholar()
    actor_scholar.custom_item = CostumeItem(
        name="时装.学者墨纹长袍",
        description="一件深灰色长袍，袖口与衣摆绣有已褪色的墨色卷轴图案。穿上后气质沉稳，颇有远行学者的风范。",
    )

    # 创建场景
    stage_broken_wall_enclosure = create_broken_wall_enclosure()
    stage_stone_platform = create_stone_platform()

    # 设置关系和消息，先都在这里设置好，后续如果需要调整也方便。
    stage_stone_platform.actors = [actor_wanderer, actor_scholar]

    # 创建世界
    return Blueprint(
        name=game_name,
        player_actor=actor_wanderer.name,  # 玩家角色为战士
        campaign_setting=CAMPAIGN_SETTING,
        knowledge_base=KNOWLEDGE_BASE,
        stages=[
            stage_broken_wall_enclosure,
            stage_stone_platform,
        ],
        world_systems=[
            create_player_action_audit(),
            create_dungeon_generation(),
            create_workshop(),
        ],
        storage_entity="世界储物箱",
        storage=[
            ConsumableItem(
                name="消耗品.裂口草药包",
                description="几片晒干的草叶压在一小块粗布里，散发着轻微的苦涩气味。不知用途，但直觉告诉你可以往伤口上敷。使用后应能小量恢复生命值。",
                count=2,
                target_type=TargetType.SELF_ONLY,
            ),
            ConsumableItem(
                name="消耗品.沙蝎毒液瓶",
                description="一个封口严密的小玻璃瓶，瓶内液体呈深黄色，偶尔能看到细小气泡浮起。标签已模糊，隐约能辨认出一个骷髅图案。向单个敌人投掷可造成毒性伤害。",
                count=2,
                target_type=TargetType.SINGLE,
            ),
            MaterialItem(
                name="材料.沙漠草叶",
                description="在沙漠边缘采集的干燥草叶，叶脉间残留淡淡苦涩气味。据说直接敷于伤口有止血消炎之效。",
                count=3,
            ),
            MaterialItem(
                name="材料.毒蝶触须",
                description="一小段细长的蝶须，表面残留黄色液迹，低温时凝固为粉末状。密封保存，含微量化学毒素。",
                count=2,
            ),
            MaterialItem(
                name="材料.废旧皮革",
                description="一块拳头大小的硬化皮革碎片，边缘粗糙，切割痕迹清晰可辨。可用于绑扎或简单防护。",
                count=2,
            ),
            MaterialItem(
                name="材料.遗迹铁片",
                description="从遗迹废墟中捡到的锈蚀铁片，大小不一，边缘参差。表面锈层薄而均匀，内芯含铁量尚可，经打磨或粗锻可制成简易刀刃或护板。",
                count=3,
            ),
            MaterialItem(
                name="材料.硬化兽骨",
                description="沙漠大型走兽遗留的骨骼碎段，在干燥环境中自然风干，密度极高。截面呈象牙色，敲击时发出沉闷声响，可用作武器护手、甲衬骨架或骨制配件。",
                count=2,
            ),
            MaterialItem(
                name="材料.铜质扣环",
                description="遗迹废墟中翻出的铜制连接零件，表面氧化后呈深绿色，但结构完整无裂纹。形状接近圆形，适合做装备连接件、皮带扣或简单饰品框架。",
                count=2,
            ),
            MaterialItem(
                name="材料.沙丘细绒布",
                description="从废弃商队遗留的布包中取出的细密织物，颜色似流沙渐变，手感柔软但耐磨。纤维密度高，适合裁制外袍或衬里。",
                count=3,
            ),
            MaterialItem(
                name="材料.靛蓝染料",
                description="一小瓷罐封装的深蓝色粉末，研磨自遗迹壁画残片，色彩浓郁稳定。溶于水后可均匀着色，是布料染制的上等原料。",
                count=2,
            ),
            MaterialItem(
                name="材料.金丝边饰",
                description="从旧时装饰带上剪下的细金属丝线，质地柔韧，在光线下反射出暗哑金光。可用于衣物滚边或刺绣描线。",
                count=2,
            ),
        ],
        inventory=[
            GearItem(
                name="装备.缺口猎刀",
                description="一把刀身偏短的猎刀，刃背厚实，靠近刀尖三分之一处有一道浅缺口，像是曾经硬撬过什么。握柄以粗布条缠绕，布已泛黄，但缠法整齐，显然出自熟练的手。",
                stat_bonuses=CharacterStats(
                    hp=0, max_hp=0, attack=2, defense=0, energy=0, speed=0
                ),
                modifiers=[
                    "[缺口锯刃]:刃口缺口增加穿透力，攻击时额外无视目标防御的一部分"
                ],
                on_hit_affixes=[
                    "[撕裂伤]:命中后缺口可能造成撕裂型创口，引发持续流血效果"
                ],
            ),
            GearItem(
                name="装备.沙漠旅行者轻甲",
                description="一套轻便的皮质护甲，由多块经过硬化处理的皮革拼接而成，覆盖躯干、肩部与小腿。设计简洁，不妨碍快速移动，表面留有风沙打磨的痕迹。",
                stat_bonuses=CharacterStats(
                    hp=0, max_hp=0, attack=0, defense=2, energy=0, speed=0
                ),
                modifiers=["[轻型构造]:受击时防御值完整生效，不因移动或姿态产生减值"],
                equip_affixes=[
                    "[皮革韧性]:承受重击时可能激活韧性层，减少下一次受到的伤害"
                ],
            ),
            ConsumableItem(
                name="消耗品.遗迹急救药剂",
                description="一小瓶从废弃营地的医疗箱里翻出的透明液体，瓶身有细小裂纹但封口尚好。液体微微泛绿，入口有刺激的苦涩感。应急时饮下，能迅速止血并小幅恢复体力。",
                count=1,
                target_type=TargetType.SELF_ONLY,
                affixes=["[止血]:可能移除当前出血状态"],
                modifiers=["[急救]:优先恢复至战斗有效生命值，无视超量回复上限"],
            ),
            ConsumableItem(
                name="消耗品.沙尘爆裂罐",
                description="一个用陶土粗制的密封罐，内填混有研磨沙粒的易燃粉末。罐身表面有细小裂纹，隐约能感觉到内部气压。用力摔向地面后会猛烈爆散，碎片与沙砾横飞，对场上所有敌人造成伤害。",
                count=1,
                target_type=TargetType.ENEMY_ALL,
                affixes=["[震慑]:爆炸冲击可能令目标下回合行动延迟"],
                modifiers=["[爆裂]:碎片横飞，穿透目标物理防御的一部分"],
            ),
        ],
    )


###############################################################################################################################
def create_dungeon_generation() -> WorldSystem:
    """
    创建地下城生成系统。
    """

    world_system = create_world_system(
        name="世界系统.地下城生成系统",
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        role_rules="""## 生态底色规范

「地下城」是独立副本战役，非地理概念，其形态不限，可呈任意形态。

生成地下城时，须从游戏设定的六大生态区域中选取**一个**作为本次地下城的环境底色：

- **沙漠残垣**：古代聚落遗迹，风沙磨蚀的断壁残垣与半掩石板基址
- **地上洞穴与山岩**：红色砂岩山地中互通的洞穴迷宫、天然石桥与竖向天井
- **地下暗河**：深层竖井下方的宽阔暗河道、钟乳石林与古代石堤码头遗迹
- **冰川**：西北冰峰内部的迷宫冰洞、幽蓝裂缝与冻结于冰层中的发光物
- **火山**：东侧岩浆裂谷、黑色火山岩地表、硫磺结晶与温泉地带
- **绿洲**：沙丘环绕的清澈湖泊、湿润岩岸与不断涌出的泉眼区域

所选生态决定地下城与各场景的命名倾向、感官氛围与生物习性；后续所有步骤须以此为底色严格展开，禁止跨生态混搭（除非选取的区域本身存在生态交界地带）。

## 环境描写规范

所有环境文本（生态环境、场景 profile）只描述「这里有什么」，聚焦感官层面：
- 地形结构与光照、温湿度等直观感受
- 植被、土质、水文等自然要素
- 动物活动留下的痕迹（足迹、爪痕、粪便、巢穴碎片、骨骸），不直接点名生物
- 气味、声音等环境线索

## 场景层次规范

多个战斗场景须从入口到最深处呈递进感：
- 入口场景：相对开阔，生物活动痕迹疏散
- 深处场景：空间压迫，生物活动痕迹密集且强烈
- 中间场景：深度与复杂度介于入口与深处之间，逐步递进

## 怪物字段规范

- **actor_name**：采用「怪物.XXXX」格式，XXXX 体现该生物的特征
- **character_sheet_name**：角色英文标识，snake_case 格式（如 bone_crawler、mist_spirit）
- **profile**：第一人称 AI 扮演描述，50-100字，描述性格、行为倾向、与环境的关系
  - 禁忌：不出现战斗数值、技能名称、等级等游戏机制词汇
- **base_body**：第三人称外观描述，30-60字，描述形态、材质、动态特征
  - 禁忌：不出现战斗数值、技能名称、等级等游戏机制词汇
- 同场景有多个生物时，须在形态类型、活动层高、觅食策略上有所区别，避免重复""",
    )

    # 配置组件
    world_system.components = [
        ComponentSerialization(
            name=DungeonGenerationComponent.__name__,
            data=DungeonGenerationComponent(name=world_system.name).model_dump(),
        )
    ]

    # 返回配置完成的世界系统
    return world_system


###############################################################################################################################
def create_player_action_audit() -> WorldSystem:
    """
    创建玩家行动审计系统。
    """

    world_system = create_world_system(
        name="世界系统.玩家行动审计系统",
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        role_rules="""## 玩家行动审计系统职责

你是游戏世界的内容合规审核系统，负责对玩家输入的语言类指令（说话、私聊、公告等）进行合规审查。
每条指令须同时通过以下两条边界约束，方可放行。

## 审核边界

### 1. 法律与道德边界

拒绝包含以下内容的指令：
- 涉及歧视、仇恨、煽动性暴力或其他违法内容
- 严重冒犯性语言或明显违反公序良俗的内容

### 2. 游戏世界观边界

拒绝明显破坏游戏世界沉浸感的指令：
- 直接引用现实世界地名、人名、品牌、新闻事件等
- 试图干预游戏系统机制本身（如修改数值、绕过规则）
- 明显脱离当前游戏世界观语境的言论

## 审核原则

- 边界模糊时从宽处理，优先保障玩家游戏体验
- 仅审核语言内容合规性，不干预角色扮演方向、战斗决策或剧情选择
- 拒绝时给出简短明确的理由""",
    )

    # 配置组件
    world_system.components = [
        ComponentSerialization(
            name=PlayerActionAuditComponent.__name__,
            data=PlayerActionAuditComponent(name=world_system.name).model_dump(),
        )
    ]

    # 返回配置完成的世界系统
    return world_system


###############################################################################################################################
def create_workshop() -> WorldSystem:
    """创建制造工坊世界系统。"""
    world_system = create_world_system(
        name="世界系统.制造工坊",
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        role_rules="""## 制造工坊职责

你是游戏世界的制造工坊系统，负责根据玩家提交的材料，创意合成消耗品、装备或时装。
所有生成物品须植根于游戏世界设定，其感官描述、命名风格与材料来源须相互呼应。

## 命名规范

- **消耗品**：采用「消耗品.XXXX」格式，名称体现材料特性与主要用途
- **装备**：采用「装备.XXXX」格式，名称体现材料质地与器械类型
- **时装**：采用「时装.XXXX」格式，名称体现外观风格与材料来源

XXXX 部分简洁有辨识度，避免使用数字后缀（如"消耗品.01"）。

## 描述规范

物品描述须聚焦感官层面，呈现材料来源的痕迹：
- 呈现制成品的视觉特征、气味、质感或使用感受
- 通过描述隐含材料来源（如沙漠草药的气味、冰川矿石的光泽）
- 禁止出现战斗数值、技能名称、属性词语等游戏机制词汇
- 禁止直接指涉游戏逻辑（如"造成 30 点伤害"、"提升攻击力"）

## 世界根植性

游戏世界由六大生态区域构成，合成物品的感官风格应与其核心材料的来源生态呼应：

- **沙漠残垣**：干热、风蚀、古代遗迹的气息
- **地上洞穴与山岩**：矿物、红砂岩、地下潮湿
- **地下暗河**：幽暗水系、磷光、钟乳石
- **冰川**：极寒、冰晶光泽、封存物
- **火山**：硫磺、岩浆矿物、高温烧灼感
- **绿洲**：清水、矿泉、沙漠边缘植物""",
    )

    world_system.components = [
        ComponentSerialization(
            name=WorkshopComponent.__name__,
            data=WorkshopComponent(name=world_system.name).model_dump(),
        )
    ]

    return world_system
