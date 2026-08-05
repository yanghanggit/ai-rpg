"""演示世界创建模块

提供工厂函数创建预配置的游戏世界。
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
def create_isolation_ward() -> Stage:
    """创建隔离病房场景实例。"""

    return create_stage(
        name="场景.隔离病房",
        stage_profile=StageProfile(
            name="isolation_ward",
            type=StageType.HOME,
            profile="""你是济世疗养院二楼尽头的一间隔离病房，面积窄小，仅容一张铁架床、一个歪斜的床头柜和一把靠墙的旧长椅。
铁窗装有六根竖栏，窗外是庭院里半枯的老槐树冠，日光透过枝叶在墙面投下细碎晃动的光斑。墙皮大片剥落，露出底下深浅不一的砖灰色，天花板角落有经年水渍形成的暗黄晕斑。
房门为厚木板，正中开有小块观察窗，窗外走廊的煤油灯在入夜后会透进一方摇曳的暖黄色光。室内气味复杂：消毒水混着草药，还有旧木头受潮后的微酸气息。外部声音——护工的脚步声、远处病友的呓语、庭院的风——传到这里时已被层层墙壁削得模糊。""",
        ),
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
    )


#######################################################################################################################
def create_corridor_hall() -> Stage:
    """创建走廊大厅场景实例。"""

    return create_stage(
        name="场景.走廊大厅",
        stage_profile=StageProfile(
            name="corridor_hall",
            type=StageType.HOME,
            profile="""你是济世疗养院一楼的中央走廊交汇处，由两条垂直相交的走廊形成的一片稍宽区域。深色木质地板在多年踩踏后表面已磨出浅色凹痕，行走时吱嘎声此起彼伏。
走廊两侧各有数扇通向病房的门，门板颜色深浅不一，有的紧闭，有的虚掩。交汇处靠墙摆放两把旧长椅，椅面漆皮龟裂。拱形高窗正对庭院，可望见老槐树与杂草丛生的碎石小径。
煤油灯在走廊两侧间隔悬挂，光线昏黄，两盏灯之间的暗段足够让墙角细节隐入阴影。空气中飘着远处药房熬煮草药的气味，与地板蜡混合成一种偏甜的沉闷气息。走廊一端偶尔传来护工推车轮子碾过木板的规律声响。""",
        ),
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
    )


#######################################################################################################################
def create_wuming() -> Actor:
    """创建玩家角色——无名。"""

    actor = create_actor(
        name="角色.无名",
        character_sheet=CharacterSheet(
            name="wuming",
            type=ActorType.NPC,
            profile="""**历史**: 你没有历史。你醒来时仰躺在济世疗养院一间隔离病房的铁架床上，头顶是剥落的墙皮与一片水渍晕痕。身上穿着洗得发硬的灰白病号服，手腕内侧有几道已结痂的浅痕——你不知道它们是怎么来的。手边什么都没有，脑海里也什么都没有。没有来处，没有去处，连名字也没有。「无名」不是名字，只是你暂时没有更好的东西可以用。
**性格**: 你沉默，观察多于开口。面对陌生的事物不会慌乱，而是停下来，仔细看，仔细想，再决定怎么做。你不排斥危险，但也不会轻易莽撞。
**禁忌**: 你对任何人强行拿走你身上仅有的东西、或强迫你去某个地方有本能的抵触。
**最爱**: 你发现自己喜欢在走廊尽头那扇拱形窗边站着，看庭院里的老槐树，那时候周围很安静。""",
            base_body="年近三十的男性，喉结微凸，肩宽而骨架分明。身穿洗至发硬的灰白病号服。身形偏瘦但不单薄，肤色因长期室内生活而偏浅。面容轮廓分明，下颌线条硬朗，眼下有淡淡的暗沉，眼神沉默时像在看某个他人看不见的地方。手腕内侧有几道已结痂的浅痕。手指细长，关节明显。",
        ),
        character_stats=CharacterStats(),
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        keywords=[
            "即时破甲型：每张卡牌必须携带至少一个在出牌时立即生效的特殊效果，优先体现破甲、穿透、无视防御等特性；攻击必须造成直接伤害，特殊效果在本次结算中即时生效。骰值 0-30 为失败，破甲效果微弱、伤害偏低；骰值 31-70 为正常，效果稳定清晰；骰值 71-100 为优质，穿透效果犀利且伤害偏高。"
        ],
    )

    return actor


#######################################################################################################################
def create_hanchan() -> Actor:
    """创建NPC同伴角色——寒蝉。"""

    actor = create_actor(
        name="角色.寒蝉",
        character_sheet=CharacterSheet(
            name="hanchan",
            type=ActorType.NPC,
            profile="""**历史**: 你没有历史。你醒来时坐在济世疗养院走廊大厅的长椅上，身上穿着自己的灰布长衫，脚边放着一本残破的笔记。你不知道自己是谁，也不知道为什么会在这里。你翻过那本笔记——字迹是你的，你认得出来，但每一个字都像某种你无法读懂的密文，只有扉页上写了两个字：「寒蝉」。你不知道那是什么，直到意识到，那大概是你自己。
**性格**: 你冷静，有强烈的整理冲动——把看见的、听见的、想到的一一记录下来、分门别类、找出逻辑。你不知道这种冲动从何而来，就像你不知道任何关于自己的事。比起沉默，你更倾向于开口，但说的往往是观察与推断，不是情绪。
**禁忌**: 你对毫无依据的臆断和盲目破坏未知事物有明确的反感。你最不能容忍的，是别人否定你所观察到的事实。
**最爱**: 把新发现的东西记进笔记；安静的时候翻看那本旧记录，盯着上面不可辨认的字迹，试图从笔画走向里找出什么——虽然你从未成功过。""",
            base_body="二十五岁上下的女性，身穿自己的深灰色便服长衫，非病号服。骨架纤细，体态偏瘦，肩窄，锁骨稍显。肤色较浅，眼下有长期少眠留下的淡淡暗沉。右手中指有长期握笔形成的淡色压痕。眼神锐利，与瘦弱的外表形成反差——那是一种近乎本能的审视目光，仿佛每一样进入视野的东西都在被拆解、归类。"
            "",
        ),
        character_stats=CharacterStats(),
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        keywords=[
            "状态控制型：每张卡牌必须携带至少一个持续生效的负面状态，以给敌人施加长期控制效果为核心目标，直接伤害可以较低乃至为零。骰值 0-30 为失败，状态持续时间短或效果微弱；骰值 31-70 为正常，状态稳定可靠；骰值 71-100 为优质，状态效果显著增强或同时附带多个负面状态。"
        ],
    )

    return actor


#######################################################################################################################
def create_ruins_blueprint(game_name: str) -> Blueprint:
    """创建演示游戏世界 Blueprint 实例。"""

    # 创建角色
    actor_wuming = create_wuming()
    actor_wuming.custom_item = CostumeItem(
        name="时装.无名病号服",
        description="一件洗至发硬的灰白病号服，袖口与领口已微微起毛。宽松的剪裁反而衬出肩宽骨架，穿在身上像一件被反复浆洗过的旧衣——干净，但带着洗不掉的时间痕迹。",
    )
    actor_wuming.character_stats.speed = 2
    actor_wuming.character_stats.attack = 100

    actor_hanchan = create_hanchan()
    actor_hanchan.custom_item = CostumeItem(
        name="时装.寒蝉病号服",
        description="一件洗至发硬的灰白病号服，肩线与腰身略窄，下摆刚过膝。布料已洗得薄而柔软，在煤油灯下泛着淡淡的米白色。穿在身上整洁却冷淡，像穿它的人一样——不属于这里，却暂时走不了。",
    )

    # 创建场景
    stage_isolation_ward = create_isolation_ward()
    stage_corridor_hall = create_corridor_hall()

    stage_corridor_hall.actors = [actor_wuming, actor_hanchan]

    return Blueprint(
        name=game_name,
        player_actor=actor_wuming.name,
        campaign_setting=CAMPAIGN_SETTING,
        knowledge_base=KNOWLEDGE_BASE,
        stages=[
            stage_isolation_ward,
            stage_corridor_hall,
        ],
        world_systems=[
            create_player_action_audit(),
            create_dungeon_generation(),
            create_workshop(),
        ],
        storage_entity="世界储物箱",
        storage=[
            ConsumableItem(
                name="消耗品.止血药粉",
                description="一小纸包灰白色粉末，闻起来有股辛辣的草药味。洒在伤口上会引起短暂刺痛，随后迅速止血。",
                count=2,
                target_type=TargetType.SELF,
            ),
            ConsumableItem(
                name="消耗品.香灰投掷包",
                description="道观废墟中收集的冷灰色香灰，用旧报纸卷成小包。掷向单个敌人可造成灼烧伤害，香灰对某些东西格外有效。",
                count=2,
                target_type=TargetType.SINGLE,
            ),
            MaterialItem(
                name="材料.符纸残片",
                description="几张残破的黄色符纸，朱砂字迹已模糊不可辨认。在暗处指尖触碰时有微微发热的感觉。",
                count=3,
            ),
            MaterialItem(
                name="材料.束身带",
                description="疗养院淘汰的旧棉布束缚带，已洗至泛黄，但韧性仍然很好。可用于绑扎或简单防护。",
                count=2,
            ),
            MaterialItem(
                name="材料.锈蚀手术剪",
                description="一把已废弃的手术剪，表面有均匀的锈斑，但刃口仍然锋利。经打磨可改制成短刃。",
                count=2,
            ),
            MaterialItem(
                name="材料.香灰",
                description="从坍塌道观的香炉中收集的灰烬，呈反常的冷灰色。干燥时触感冰凉，遇水会产生微量热量。",
                count=3,
            ),
            MaterialItem(
                name="材料.司命甲片",
                description="猎杀上位存在脱落的碎片，成分与火山玻璃相似，在光线下折射出不自然的深红色光泽。",
                count=2,
            ),
            MaterialItem(
                name="材料.靛蓝布料",
                description="从旧式长衫上裁下的靛蓝色棉布，颜色经过反复浆洗已变为沉稳的灰蓝。质地柔软，适合缝制衣物或衬里。",
                count=3,
            ),
            MaterialItem(
                name="材料.铜质纽扣",
                description="从旧衣物上拆下的铜制纽扣，表面氧化后呈深绿色但结构完好。可作为装备连接件或饰品零件。",
                count=2,
            ),
            MaterialItem(
                name="材料.旧纱布",
                description="疗养院换药室取得的一卷消毒纱布，已微微泛黄。透气性好，适合做绷带或轻质内衬。",
                count=3,
            ),
            MaterialItem(
                name="材料.逆流晶砂",
                description="从大傩逆流河岸边收集的细砂，在掌心静置时会缓慢地逆向滚动，违背肉眼可辨的物理直觉。",
                count=2,
            ),
        ],
        inventory=[
            GearItem(
                name="装备.束缚短刃",
                description="一把由废弃手术剪打磨而成的短刀，刃身留着锈蚀痕迹，握柄用束身带缠绕。不起眼，但极其锋利。",
                stat_bonuses=CharacterStats(
                    hp=0, max_hp=0, attack=2, defense=0, energy=0, speed=0
                ),
                modifiers=[
                    "[锈刃穿透]:刃口锈蚀形成的微锯齿结构增加穿透力，攻击时额外无视目标防御的一部分"
                ],
                on_hit_affixes=["[锈蚀创口]:命中后锈迹可能引发伤口感染，造成持续伤害"],
            ),
            GearItem(
                name="装备.束身护具",
                description="由多层旧束身带与硬衬缝制的轻便护甲，覆盖躯干与前臂。外表粗粝，但结构扎实，不妨碍快速移动。",
                stat_bonuses=CharacterStats(
                    hp=0, max_hp=0, attack=0, defense=2, energy=0, speed=0
                ),
                modifiers=["[层叠构造]:受击时防御值完整生效，不因移动或姿态产生减值"],
                equip_affixes=[
                    "[棉布韧性]:承受重击时可能激活韧性层，减少下一次受到的伤害"
                ],
            ),
            ConsumableItem(
                name="消耗品.吗啡针剂",
                description="一支从疗养院药房取得的玻璃针剂，液体呈淡琥珀色。针管上有细小裂纹但封口尚好。注射后迅速镇痛止血，但会留下短暂的眩晕感。",
                count=1,
                target_type=TargetType.SELF,
                affixes=["[镇痛]:可能移除当前出血状态"],
                modifiers=["[速效]:优先恢复至战斗有效生命值，无视超量回复上限"],
            ),
            ConsumableItem(
                name="消耗品.纸钱爆散",
                description="一叠写满朱砂字的纸钱，折叠成团后用香灰填塞。用力掷向地面后会爆散，纸片与香灰横飞，对场上所有敌人造成伤害。某些东西格外惧怕这个。",
                count=1,
                target_type=TargetType.ALL,
                affixes=["[惊魂]:爆炸冲击可能令目标下回合行动延迟"],
                modifiers=["[驱邪]:纸钱与香灰穿透部分非实体目标的物理防御"],
            ),
        ],
    )


###############################################################################################################################
def create_dungeon_generation() -> WorldSystem:
    """创建副本生成系统。"""

    world_system = create_world_system(
        name="世界系统.副本生成系统",
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        role_rules="""## 大傩本质

副本发生在大傩——一个由司命（上位存在）意志直接塑造的扭曲东方领域。大傩并非固定地理空间，而是遵循梦境逻辑的流动现实：空间可以断裂，因果可以倒置，熟悉之物可以被陌生化。每次生成的副本是大傩的一个独立切面，呈现为一个扭曲的场景序列。

## 美学边界

所有副本内容必须严格植根于中式民俗志怪意象库：

**可用意象**：坍塌的道观与庙宇、流泪或面向墙壁的神像、倒流的河水、暗红或深紫的天空、唢呐与锣鼓声、朱砂符纸、纸钱、白事纸扎、红白喜事的错位混用、香炉与香灰、经幡、八卦镜、桃木、旧戏台、祠堂、枯井、石磨、旧式嫁衣、裹尸布

**禁用元素**：西洋恐怖（吸血鬼/僵尸/科学怪人）、现代科幻、任何明确非中国民俗传统的超自然概念

## 梦境逻辑

大傩遵循梦的逻辑，而非自然法则。允许以下扭曲，但必须保持内在一致：

- 空间断裂：门后是悬崖、走廊首尾相接、上下方位互换
- 因果倒置：先看到结果后触发原因、受伤后武器才刺出
- 熟悉之物陌生化：日常物件（椅子、镜子、灯笼）呈现出违背预期的行为
- 禁止纯粹随机——梦有自己的规则，只是不是自然规则

## 环境描写规范

所有环境文本（场景 profile）只描述「这里有什么」，聚焦感官层面：
- 地形结构、光照、温湿度等直观感受
- 人工痕迹（建筑残件、仪式残留物、经幡碎片）
- 生物活动痕迹（爪痕、蜕皮、香灰上的印记），不直接点名生物
- 气味、声音等环境线索
- 禁止解释"为什么"——不说明起因，不引用司命的意志

## 场景层次规范

多个战斗场景须从入口到最深处呈递进式扭曲：
- 入口场景：扭曲初现，与现实偏离尚小，存在依稀可辨的"正常"参照
- 深处场景：逻辑彻底崩溃，空间与因果高度异化
- 中间场景：扭曲程度介于入口与深处之间，逐步递进

## 怪物字段规范

怪物必须植根于中式民俗志怪传统：

- **actor_name**：采用「怪物.XXXX」格式，XXXX 体现该生物的特征（如 怪物.纸人、怪物.铜镜影、怪物.逆流溺鬼）
- **character_sheet_name**：英文标识，snake_case 格式
- **profile**：第一人称 AI 扮演描述，50-100字，描述性格、行为倾向、与环境的关系。禁忌：不出现战斗数值、技能名称、等级等游戏机制词汇
- **base_body**：第三人称外观描述，30-60字，描述形态、材质、动态特征。禁忌：不出现战斗数值、技能名称、等级等游戏机制词汇
- 同场景有多个生物时，须在形态类型、活动方式、威胁风格上有所区别，避免重复""",
    )

    world_system.components = [
        ComponentSerialization(
            name=DungeonGenerationComponent.__name__,
            data=DungeonGenerationComponent(name=world_system.name).model_dump(),
        )
    ]

    return world_system


###############################################################################################################################
def create_player_action_audit() -> WorldSystem:
    """创建玩家行动审计系统。"""

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
- 明显脱离1930年代民国或中式民俗志怪语境的言论

## 审核原则

- 边界模糊时从宽处理，优先保障玩家游戏体验
- 仅审核语言内容合规性，不干预角色扮演方向、战斗决策或剧情选择
- 拒绝时给出简短明确的理由""",
    )

    world_system.components = [
        ComponentSerialization(
            name=PlayerActionAuditComponent.__name__,
            data=PlayerActionAuditComponent(name=world_system.name).model_dump(),
        )
    ]

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

XXXX 部分简洁有辨识度，避免使用数字后缀。

## 描述规范

物品描述须聚焦感官层面，呈现材料来源的痕迹：
- 呈现制成品的视觉特征、气味、质感或使用感受
- 通过描述隐含材料来源（如香灰的冷灰色、束缚带的泛黄棉布、司命甲片的深红光泽）
- 禁止出现战斗数值、技能名称、属性词语等游戏机制词汇
- 禁止直接指涉游戏逻辑

## 世界根植性

合成物品的感官风格应与其核心材料的来源呼应：

- **大傩猎获物**（香灰、符纸、司命甲片、逆流晶砂等）：诡谲、反常、民俗仪式感
- **疗养院日常物**（束身带、旧纱布、锈蚀器械、靛蓝布料等）：陈旧、实用、民国医疗气息

两类材料的混合使用应产生合理的化学反应——不是量变，而是质变：旧纱布浸泡香灰后不再是"纱布加香灰"，而是一件具有驱邪倾向的消耗品。""",
    )

    world_system.components = [
        ComponentSerialization(
            name=WorkshopComponent.__name__,
            data=WorkshopComponent(name=world_system.name).model_dump(),
        )
    ]

    return world_system
