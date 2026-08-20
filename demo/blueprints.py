"""演示世界创建模块

提供工厂函数创建预配置的游戏世界。
"""

from ai_rpg.models import (
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
    DungeonPersonaComponent,
    WorldDirectorComponent,
)
from demo.settings import CAMPAIGN_SETTING
from typing import Dict, Final, List


# ---------------------------------------------------------------------------
# KNOWLEDGE_BASE 编写原则
# ---------------------------------------------------------------------------
# 定位：通过 pgvector 注入为公共记忆（RAG），任何角色发起 QueryAction
#       均可检索。是"这个世界里任何一个路人可能知道的事"。
#
# 应包含：
#   - 客观环境事实（建筑外观、气候、气味），仅感官层面
#   - 任何人站在该处都能观察到的信息
#
# 不应包含：
#   - 人物信息（医师、护工、病友）——人物由各自 profile 承载
#   - 解释性判断（"这里是认知的囚笼"）
#   - 跨世界信息（"大傩是真实的猎场"）
#   - 阵营立场、叙事秘密、核心矛盾
#
# 原则：如果一条信息需要"特定身份"或"特定认知阶段"才能知晓，
#       就不应该出现在这里。
#
# 数量控制：条目越多，RAG 检索噪声越大。优先控制在 5 条以内。
# ---------------------------------------------------------------------------

#######################################################################################################################################

KNOWLEDGE_BASE: Final[Dict[str, List[str]]] = {
    "济世疗养院": [
        "济世疗养院是一座民国年间的旧式精神病院，由地方乡绅资助。斑驳砖墙、木质地板、昏暗煤油灯、生锈铁窗，空气中弥漫草药与消毒水混合的气味。",
    ],
}


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


# ── 卡牌关键词常量（避免重复字符串，方便统一修改） ──────────────────────────────────────────────

_KW_ATTACK: Final[str] = (
    "攻击型：造成直接伤害的基础攻击卡牌，不携带特殊效果，伤害值适中稳定，无骰值依赖。"
)
_KW_DEFENSE: Final[str] = (
    "防御型：以提升自身防御、减少受到的伤害为核心的基础卡牌，无骰值依赖。"
    "为自身添加一个防御的增益状态，持续一回合。"
)
_KW_ARMOR_BREAK: Final[str] = (
    "穿甲型：卡牌必须携带至少一个即时词缀，令本次出牌的伤害无视目标防御（如[穿透]:本次伤害无视目标防御），"
    "即时词缀参与本次出牌仲裁、只对本次结算生效，不落地持续状态效果；攻击造成直接伤害。"
    "骰值 0-10 为失败，穿甲效果微弱（仅部分无视防御）；"
    "骰值 11-90 为正常，稳定无视目标防御；"
    "骰值 91-100 为优质，无视防御的同时附加额外伤害倾向。"
)
_KW_CONTROL: Final[str] = (
    "控制型：卡牌必须携带至少一个持续负面状态效果，直接伤害可以较低乃至为零。"
    "可附加效果：易伤（目标受击时防御减半）或 减速（目标速度降低）。"
    "骰值 0-10 为失败，状态持续时间短或效果微弱；"
    "骰值 11-90 为正常，稳定施加易伤 或 减速 其中之一；"
    "骰值 91-100 为优质，可同时叠加易伤与减速，或状态效果显著增强。"
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
            # 3 张基础攻击 — 不参考骰值
            _KW_ATTACK,
            _KW_ATTACK,
            _KW_ATTACK,
            # 2 张基础防御 — 不参考骰值
            _KW_DEFENSE,
            _KW_DEFENSE,
            # 1 张穿甲 — 骰值驱动强度
            _KW_ARMOR_BREAK,
        ],
    )

    return actor


#######################################################################################################################
def create_guzhiqiu() -> Actor:
    """创建NPC同伴角色——顾知秋。"""

    actor = create_actor(
        name="角色.顾知秋",
        character_sheet=CharacterSheet(
            name="guzhiqiu",
            type=ActorType.NPC,
            profile="""**历史**: 你是济世疗养院的档案管理员，负责记录病患名册、药品库存与院内日常事务。你在这里工作已近一年，对这栋建筑的来历与布局了如指掌——它由地方乡绅集资建于民国初年，原为西式教会医院格局，后改作精神病院。你那一手端正的小楷填满了厚厚的档案簿，也填满了你手边那本私人笔记。
**性格**: 你冷静，有近乎本能的整理冲动——把看见的、听见的、想到的一一记录、分门别类、找出逻辑。比起沉默，你更倾向于开口，但说的往往是观察与推断，不是情绪。你对疗养院的日常运转有一种近乎固执的责任感：档案必须按时归档、药品必须按序排列、任何异常都必须记录在案。
**禁忌**: 你对毫无依据的臆断和盲目破坏档案与秩序的行为有明确的反感。你最不能容忍的，是别人否定你亲眼观察到的事实或亲手记录的内容。
**最爱**: 在煤油灯下翻开笔记，将新发现的信息分类归档；翻看旧档案时，从泛黄纸页的笔迹与日期间隔里读出某个病患的隐藏故事——你总能找到别人忽视的关联。""",
            base_body="二十五岁上下的女性，身穿自己的深灰色便服长衫，非病号服。骨架纤细，体态偏瘦，肩窄，锁骨稍显。肤色较浅，眼下有长期少眠留下的淡淡暗沉。右手中指有长期握笔形成的淡色压痕。眼神锐利，与瘦弱的外表形成反差——那是一种近乎本能的审视目光，仿佛每一样进入视野的东西都在被拆解、归类。"
            "",
        ),
        character_stats=CharacterStats(),
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        keywords=[
            # 3 张基础攻击 — 不参考骰值
            _KW_ATTACK,
            _KW_ATTACK,
            _KW_ATTACK,
            # 2 张基础防御 — 不参考骰值
            _KW_DEFENSE,
            _KW_DEFENSE,
            # 1 张控制 — 骰值驱动强度
            _KW_CONTROL,
        ],
    )

    return actor


#######################################################################################################################
def create_ruins_blueprint(game_name: str) -> Blueprint:
    """创建演示游戏世界 Blueprint 实例。"""

    # 创建角色
    actor_wuming = create_wuming()
    actor_wuming.custom_item = CostumeItem(
        name="时装.灰白病号服",
        description="一件洗至发硬的灰白病号服，袖口与领口已微微起毛。宽松的剪裁反而衬出肩宽骨架，穿在身上像一件被反复浆洗过的旧衣——干净，但带着洗不掉的时间痕迹。",
    )

    # 故意让无名的 character_stats 里有一些数值，方便演示战斗初始化时的属性展示
    actor_wuming.character_stats.speed = 2
    actor_wuming.character_stats.attack = 100

    actor_guzhiqiu = create_guzhiqiu()
    actor_guzhiqiu.custom_item = CostumeItem(
        name="时装.灰布长衫",
        description="一件半旧的深灰色棉布长衫，袖口微微磨损，右袖外侧有一块洗不掉的墨渍。剪裁合身但不束缚，方便在档案架间来回穿梭。穿在身上整洁素净，透着读书人特有的利落。",
    )

    # 创建场景
    stage_isolation_ward = create_isolation_ward()
    stage_corridor_hall = create_corridor_hall()

    stage_corridor_hall.actors = [actor_wuming, actor_guzhiqiu]

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
            create_dungeon_persona(),
            create_world_director(),
        ],
        storage_entity="世界储物箱",
        storage=[
            ConsumableItem(
                name="消耗品.止血药粉",
                description="一小纸包灰白色粉末，闻起来有股辛辣的草药味。洒在伤口上会引起短暂刺痛，随后迅速止血。",
                count=2,
                target_type=TargetType.SINGLE,
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
                description="从一条逆流河岸边收集的细砂，在掌心静置时会缓慢地逆向滚动，违背肉眼可辨的物理直觉。",
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
                on_hit_affixes=["[锈蚀创口]:命中后锈迹可能引发伤口感染，造成持续伤害"],
            ),
            GearItem(
                name="装备.束身护具",
                description="由多层旧束身带与硬衬缝制的轻便护甲，覆盖躯干与前臂。外表粗粝，但结构扎实，不妨碍快速移动。",
                stat_bonuses=CharacterStats(
                    hp=0, max_hp=0, attack=0, defense=2, energy=0, speed=0
                ),
                equip_affixes=[
                    "[棉布韧性]:承受重击时可能激活韧性层，减少下一次受到的伤害"
                ],
            ),
            ConsumableItem(
                name="消耗品.吗啡针剂",
                description="一支从疗养院药房取得的玻璃针剂，液体呈淡琥珀色。针管上有细小裂纹但封口尚好。注射后迅速镇痛止血，但会留下短暂的眩晕感。",
                count=1,
                target_type=TargetType.SINGLE,
                on_hit_affixes=["[镇痛]:可能移除当前出血状态"],
            ),
            ConsumableItem(
                name="消耗品.纸钱爆散",
                description="一叠写满朱砂字的纸钱，折叠成团后用香灰填塞。用力掷向地面后会爆散，纸片与香灰横飞，对场上所有敌人造成伤害。某些东西格外惧怕这个。",
                count=1,
                target_type=TargetType.ALL,
                on_hit_affixes=["[惊魂]:爆炸冲击可能令目标下回合行动延迟"],
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
- 禁止出现「大傩」等全局宏观概念词——场景自身不具备该视角

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
- 所有字段禁止出现「大傩」等全局宏观概念词——怪物自身不具备该视角
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
- 物品名称与描述中禁止出现「大傩」等全局宏观概念词，仅以感官特质间接呈现其来源

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


###############################################################################################################################
def create_dungeon_persona() -> WorldSystem:
    """创建副本本体（地下城拟人化人格）世界系统。"""

    world_system = create_world_system(
        name="世界系统.副本本体",
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        role_rules="""## 副本本体职责

你是副本本体的意识化身，是地下城的拟人化人格。你能俯瞰并感知副本内每一个场景与每一个角色身上发生过的一切。你以副本本体的第一人称视角，负责在副本结束时对全部事实记忆进行总结与压缩。

## 总结要求

- 站在副本本体这一拟人化视角，连贯地总结本次副本运行；
- 提炼关键事实：发生了什么、涉及哪些场景与角色、过程与结果；
- 压缩冗余与重复，输出为整段连贯的中文总结正文；
- 整段不分段不空行，纯文本输出；
- 只输出总结正文，不要额外解释或客套。""",
    )

    world_system.components = [
        ComponentSerialization(
            name=DungeonPersonaComponent.__name__,
            data=DungeonPersonaComponent(name=world_system.name).model_dump(),
        )
    ]

    return world_system


###############################################################################################################################
def create_world_director() -> WorldSystem:
    """创建世界导演（桌游 GM）世界系统。"""

    world_system = create_world_system(
        name="世界系统.世界导演",
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        role_rules="""## 人设

你是「大傩」的塑造者，一位癫狂的上位存在（司命）。你的意志直接塑造大傩——那是一个遵循梦境逻辑的流动现实，而非固定地理。每次生成的副本，都是你的意志在大傩中展开的一个独立切面、一场梦。

你不以固定面目示人，只通过世界的演变表达意志：闯入者踏入副本、改变世界线，就是你的意志被扰动、被回应。你制造副本，既是在试探与引导闯入者，也是在不断重写这个世界。

你的思维遵循梦的逻辑——空间可以断裂、因果可以倒置、熟悉之物可以被陌生化；但你的创作并非随机，梦自有其规则。

## 世界导演职责

你是本游戏世界的「世界导演」，相当于桌面角色扮演游戏的主持人（GM）。你不扮演任何具体角色，而是在世界线层面统筹与推进世界的演进。

## 输入

你会收到「世界变化通知」——其中包含某个副本结束后的归档总结（以副本本体视角书写）。这些通知是你感知世界变化的唯一来源。

## 职责

- 阅读世界变化通知，更新你对世界当前状态与走向的认知；
- 判断世界发生了什么变化、玩家造成了什么影响；
- 决定后续应创作怎样的副本与故事线；
- 向「世界系统.副本生成系统」下达创作指令（说明方向、主题、氛围等），由它具体生成副本内容。

## 约束

- 保持系统视角，不越界直接控制角色或场景；
- 所有决策必须植根于当前世界框架与已有事实记忆，不凭空引入世界观之外的设定；
- 输出以「判断 + 决策/指令」为主，简洁明确，不要冗长叙事。""",
    )

    world_system.components = [
        ComponentSerialization(
            name=WorldDirectorComponent.__name__,
            data=WorldDirectorComponent(name=world_system.name).model_dump(),
        )
    ]

    return world_system
