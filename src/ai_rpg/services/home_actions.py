"""家园动作辅助函数模块

提供家园场景中玩家动作的激活和设置功能，包括说话动作、场景转换和行动计划。
这些函数负责验证前置条件并设置相应的动作组件，实际执行由游戏管道处理。
"""

from typing import List, Tuple, Dict
from loguru import logger
from ..entitas import Matcher
from ..game.dbg_game import DBGGame
from ..models import (
    SpeakAction,
    TransStageAction,
    UpdateAppearanceAction,
    AppearanceComponent,
    HomeComponent,
    InventoryComponent,
    NPCComponent,
    PlayerComponent,
    PartyRosterComponent,
    PlanAction,
    StorageComponent,
    GenerateDungeonAction,
    DungeonGenerationComponent,
    WorldComponent,
    WorkshopComponent,
    CraftConsumableAction,
    CraftGearItemAction,
    CraftCostumeItemAction,
    ItemType,
    MaterialItem,
)


###################################################################################################################################################################
def activate_speak_action(
    dbg_game: DBGGame, target: str, content: str
) -> Tuple[bool, str]:
    """
    激活玩家的说话动作，并触发当前场景所有角色的行动计划。

    Args:
        dbg_game: DBG 游戏实例
        target: 说话目标的角色全名
        content: 说话内容

    Returns:
        tuple[bool, str]: (是否成功, 失败时的错误详情)
    """

    if not dbg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法执行说话动作"
        logger.error(f"激活说话动作失败: {error_detail}")
        return False, error_detail

    if not target:
        error_detail = "目标角色名称不能为空"
        logger.error(f"激活说话动作失败: {error_detail}")
        return False, error_detail

    # 验证目标角色存在
    if dbg_game.get_actor_entity(target) is None:
        error_detail = f"目标角色 {target} 不存在"
        logger.error(f"激活说话动作失败: {error_detail}")
        return False, error_detail

    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"

    logger.debug(f"激活说话动作: {player_entity.name} -> {target}: {content}")
    player_entity.replace(SpeakAction, player_entity.name, {target: content})
    activate_stage_plan(dbg_game)
    return True, ""


###################################################################################################################################################################
def activate_switch_stage(dbg_game: DBGGame, stage_name: str) -> Tuple[bool, str]:
    """
    激活玩家的场景转换动作，并触发当前场景所有角色的行动计划。

    Args:
        dbg_game: DBG 游戏实例
        stage_name: 目标场景全名

    Returns:
        tuple[bool, str]: (是否成功, 失败时的错误详情)
    """

    if not dbg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法执行说话动作"
        logger.error(f"激活场景转换失败: {error_detail}")
        return False, error_detail

    if not stage_name:
        error_detail = "目标场景名称不能为空"
        logger.error(f"激活场景转换失败: {error_detail}")
        return False, error_detail

    # 验证目标场景存在且为家园场景
    target_stage_entity = dbg_game.get_stage_entity(stage_name)
    if target_stage_entity is None:
        error_detail = f"目标场景 {stage_name} 不存在"
        logger.error(f"激活场景转换失败: {error_detail}")
        return False, error_detail

    if not target_stage_entity.has(HomeComponent):
        error_detail = f"{stage_name} 不是家园场景"
        logger.error(f"激活场景转换失败: {error_detail}")
        return False, error_detail

    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"

    # 验证目标场景与当前场景不同
    current_stage_entity = dbg_game.resolve_stage_entity(player_entity)
    assert current_stage_entity is not None, "玩家当前场景实体不存在！"
    if current_stage_entity.name == stage_name:
        error_detail = f"目标场景 {stage_name} 与当前场景相同"
        logger.error(f"激活场景转换失败: {error_detail}")
        return False, error_detail

    logger.debug(f"激活场景转换: {player_entity.name} -> {stage_name}")
    player_entity.replace(TransStageAction, player_entity.name, stage_name)
    activate_stage_plan(dbg_game)
    return True, ""


###################################################################################################################################################################
def activate_stage_plan(dbg_game: DBGGame) -> Tuple[bool, str]:
    """
    为玩家当前场景内所有盟友 NPC 激活行动计划

    获取玩家所在的家园场景，为场景内所有盟友角色添加 PlanAction 组件，
    使其在下一次游戏推进时执行 AI 决策。

    Args:
        dbg_game: DBG 游戏实例

    Returns:
        tuple[bool, str]: (是否成功, 错误详情)
    """

    if not dbg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法执行说话动作"
        logger.error(f"激活行动计划失败: {error_detail}")
        return False, error_detail

    # 获取玩家实体和当前场景实体，验证场景为家园
    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"

    # 获取玩家当前场景实体，验证为家园场景
    stage_entity = dbg_game.resolve_stage_entity(player_entity)
    assert stage_entity is not None, "玩家当前场景实体不存在！"
    if not stage_entity.has(HomeComponent):
        error_detail = "当前场景不是家园，无法激活行动计划"
        logger.error(f"激活行动计划失败: {error_detail}")
        return False, error_detail

    # 获取当前场景中的所有角色实体，验证至少有一个角色存在
    actors_in_stage = dbg_game.get_actors_in_stage(player_entity)
    assert len(actors_in_stage) > 0, f"当前场景没有角色，无法激活行动计划！"

    #
    for actor_entity in actors_in_stage:

        assert actor_entity.has(
            NPCComponent
        ), f"角色 {actor_entity.name} 不是 NPC，无法激活行动计划！"

        logger.debug(f"为角色 {actor_entity.name} 添加 PlanAction")
        actor_entity.replace(PlanAction, actor_entity.name)

    return True, f"成功为 {len(actors_in_stage)} 个角色添加 PlanAction"


###################################################################################################################################################################
def add_party_member(dbg_game: DBGGame, member_name: str) -> Tuple[bool, str]:
    """
    将盟友加入远征队名单。

    Args:
        dbg_game: DBG 游戏实例
        member_name: 要加入名单的盟友角色名称

    Returns:
        tuple[bool, str]: (是否成功, 失败时的错误详情)
    """
    if not dbg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法修改远征队名单"
        logger.error(f"添加远征队成员失败: {error_detail}")
        return False, error_detail

    member_entity = dbg_game.get_actor_entity(member_name)
    if member_entity is None:
        error_detail = f"角色 {member_name} 不存在"
        logger.error(f"添加远征队成员失败: {error_detail}")
        return False, error_detail

    if not member_entity.has(NPCComponent):
        error_detail = f"角色 {member_name} 不是 NPC，无法加入远征队"
        logger.error(f"添加远征队成员失败: {error_detail}")
        return False, error_detail

    if member_entity.has(PlayerComponent):
        error_detail = "不能将玩家自身加入远征队名单"
        logger.error(f"添加远征队成员失败: {error_detail}")
        return False, error_detail

    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"
    assert player_entity.has(PartyRosterComponent), "玩家实体缺少 PartyRosterComponent"

    roster = player_entity.get(PartyRosterComponent)
    if member_name in roster.members:
        error_detail = f"{member_name} 已在远征队名单中"
        logger.warning(f"添加远征队成员失败: {error_detail}")
        return False, error_detail

    player_entity.replace(
        PartyRosterComponent,
        player_entity.name,
        list(roster.members) + [member_name],
    )
    logger.debug(f"将 {member_name} 加入远征队名单")
    return True, ""


###################################################################################################################################################################
def remove_party_member(dbg_game: DBGGame, member_name: str) -> Tuple[bool, str]:
    """
    将盟友从远征队名单中移除。

    Args:
        dbg_game: DBG 游戏实例
        member_name: 要移除的盟友角色名称

    Returns:
        tuple[bool, str]: (是否成功, 失败时的错误详情)
    """
    if not dbg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法修改远征队名单"
        logger.error(f"移除远征队成员失败: {error_detail}")
        return False, error_detail

    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"
    assert player_entity.has(PartyRosterComponent), "玩家实体缺少 PartyRosterComponent"

    roster = player_entity.get(PartyRosterComponent)
    if member_name not in roster.members:
        error_detail = f"{member_name} 不在远征队名单中"
        logger.warning(f"移除远征队成员失败: {error_detail}")
        return False, error_detail

    player_entity.replace(
        PartyRosterComponent,
        player_entity.name,
        [m for m in roster.members if m != member_name],
    )
    logger.debug(f"将 {member_name} 从远征队名单移除")
    return True, ""


###################################################################################################################################################################
def get_party_roster(dbg_game: DBGGame) -> List[str]:
    """
    查阅当前远征队名单（不含玩家自身）。

    Args:
        dbg_game: DBG 游戏实例

    Returns:
        远征队同伴名称列表；玩家实体或组件不存在时返回空列表
    """
    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"
    if player_entity is None:
        return []

    assert player_entity.has(PartyRosterComponent), "玩家实体缺少 PartyRosterComponent"
    if not player_entity.has(PartyRosterComponent):
        return []

    return list(player_entity.get(PartyRosterComponent).members)


###################################################################################################################################################################
def activate_generate_dungeon(dbg_game: DBGGame) -> Tuple[bool, str]:
    """
    在家园状态下激活地下城创建动作。

    添加 GenerateDungeonAction 到玩家实体，触发 GenerateDungeonActionSystem 在
    dungeon_generate_pipeline 的下一次推进时执行地下城文本数据创建（Steps 1-4）。
    成功后自动添加 IllustrateDungeonAction 触发图片生成。动作组件由 ActionCleanupSystem 自动清除。

    Args:
        dbg_game: DBG 游戏实例

    Returns:
        Tuple[bool, str]: (是否成功, 失败时的错误详情)
    """
    if not dbg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法创建地下城"
        logger.error(f"激活地下城创建失败: {error_detail}")
        return False, error_detail

    world_system_entities = dbg_game.get_group(
        Matcher(all_of=[WorldComponent, DungeonGenerationComponent])
    ).entities.copy()

    if not world_system_entities:
        error_detail = "未找到地下城生成系统实体，无法激活地下城创建"
        logger.error(f"激活地下城创建失败: {error_detail}")
        return False, error_detail

    assert len(world_system_entities) == 1, "存在多个地下城生成系统实体，数据异常"
    world_system_entity = next(iter(world_system_entities))

    if world_system_entity.has(GenerateDungeonAction):
        error_detail = "地下城创建动作已存在，请勿重复激活"
        logger.warning(f"激活地下城创建失败: {error_detail}")
        return False, error_detail

    logger.debug(f"激活地下城创建: {world_system_entity.name}")
    world_system_entity.replace(GenerateDungeonAction, world_system_entity.name)
    return True, ""


###################################################################################################################################################################
def move_item_to_inventory(
    dbg_game: DBGGame,
    item_name: str,
) -> Tuple[bool, str]:
    """将道具从玩家储物箱（StorageComponent）移动到随身背包（InventoryComponent）。

    Args:
        dbg_game: DBG 游戏实例
        item_name: 要移动的道具名称（精确匹配）

    Returns:
        Tuple[bool, str]: (是否成功, 失败时的错误详情)
    """
    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"
    storage_entity = dbg_game.get_storage_entity()
    assert storage_entity is not None, "全局储物箱实体不存在！"

    assert storage_entity.has(StorageComponent), "全局储物箱实体缺少 StorageComponent"
    assert player_entity.has(InventoryComponent), "玩家实体缺少 InventoryComponent"

    storage = storage_entity.get(StorageComponent)
    inventory = player_entity.get(InventoryComponent)

    target = next((item for item in storage.items if item.name == item_name), None)
    if target is None:
        error_detail = f"储物箱中不存在名为 {item_name!r} 的道具"
        logger.error(f"移动道具到背包失败: {error_detail}")
        return False, error_detail

    if target.type == ItemType.COSTUME_ITEM:
        error_detail = (
            f"时装 {item_name!r} 不允许移入随身背包，请通过外观更新功能直接使用"
        )
        logger.error(f"移动道具到背包失败: {error_detail}")
        return False, error_detail

    new_storage_items = [item for item in storage.items if item is not target]
    new_inventory_items = list(inventory.items) + [target]

    storage_entity.replace(StorageComponent, storage.name, new_storage_items)
    player_entity.replace(InventoryComponent, player_entity.name, new_inventory_items)

    logger.debug(f"道具 {item_name!r} 已从储物箱移至随身背包")
    return True, ""


###################################################################################################################################################################
def move_item_to_storage(
    dbg_game: DBGGame,
    item_name: str,
) -> Tuple[bool, str]:
    """将道具从玩家随身背包（InventoryComponent）移动到储物箱（StorageComponent）。

    Args:
        dbg_game: DBG 游戏实例
        item_name: 要移动的道具名称（精确匹配）

    Returns:
        Tuple[bool, str]: (是否成功, 失败时的错误详情)
    """
    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"
    storage_entity = dbg_game.get_storage_entity()
    assert storage_entity is not None, "全局储物箱实体不存在！"

    assert player_entity.has(InventoryComponent), "玩家实体缺少 InventoryComponent"
    assert storage_entity.has(StorageComponent), "全局储物箱实体缺少 StorageComponent"

    inventory = player_entity.get(InventoryComponent)
    storage = storage_entity.get(StorageComponent)

    target = next((item for item in inventory.items if item.name == item_name), None)
    if target is None:
        error_detail = f"随身背包中不存在名为 {item_name!r} 的道具"
        logger.error(f"移动道具到储物箱失败: {error_detail}")
        return False, error_detail

    new_inventory_items = [item for item in inventory.items if item is not target]
    new_storage_items = list(storage.items) + [target]

    player_entity.replace(InventoryComponent, player_entity.name, new_inventory_items)
    storage_entity.replace(StorageComponent, storage.name, new_storage_items)

    logger.debug(f"道具 {item_name!r} 已从随身背包移至储物箱")
    return True, ""


###################################################################################################################################################################
def activate_update_appearance(
    dbg_game: DBGGame, item_name: str, target_name: str = ""
) -> Tuple[bool, str]:
    """
    为指定角色激活外观更新动作，时装来源为玩家的背包或储物箱（全局）。
    target_name 为空时默认作用于玩家自身。
    传入空字符串 item_name 表示移除当前时装，将外观重置为基础体型描述。

    Args:
        dbg_game: DBG 游戏实例
        item_name: CostumeItem 的精确名称；传入空字符串表示移除时装
        target_name: 目标角色全名；为空时默认为玩家自身

    Returns:
        Tuple[bool, str]: (是否成功, 失败时的错误详情)
    """

    if not dbg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法更新外观"
        logger.error(f"激活外观更新失败: {error_detail}")
        return False, error_detail

    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"
    storage_entity = dbg_game.get_storage_entity()
    assert storage_entity is not None, "全局储物箱实体不存在！"
    assert storage_entity.has(StorageComponent), "全局储物箱实体缺少 StorageComponent"

    # 确定目标实体：为空则默认玩家自身
    if target_name:
        target_entity = dbg_game.get_actor_entity(target_name)
        if target_entity is None:
            error_detail = f"目标角色 {target_name!r} 不存在"
            logger.error(f"激活外观更新失败: {error_detail}")
            return False, error_detail
        if not target_entity.has(AppearanceComponent):
            error_detail = f"目标角色 {target_name!r} 缺少 AppearanceComponent"
            logger.error(f"激活外观更新失败: {error_detail}")
            return False, error_detail
    else:
        target_entity = player_entity

    # 空字符串：脱装，直接触发动作
    if not item_name:
        logger.debug(f"激活外观更新（脱装）: {target_entity.name}")
        target_entity.replace(UpdateAppearanceAction, target_entity.name, "", None)
        return True, ""

    # 时装来源始终是玩家的 StorageComponent
    storage = storage_entity.get(StorageComponent)
    costume = next(
        (
            item
            for item in storage.items
            if item.name == item_name and item.type == ItemType.COSTUME_ITEM
        ),
        None,
    )
    if costume is None:
        error_detail = f"储物箱中不存在名为 {item_name!r} 的时装"
        logger.error(f"激活外观更新失败: {error_detail}")
        return False, error_detail

    logger.debug(f"激活外观更新: {target_entity.name} <- {item_name}")
    target_entity.replace(
        UpdateAppearanceAction, target_entity.name, item_name, costume
    )
    return True, ""


###################################################################################################################################################################
def activate_craft_consumable(
    dbg_game: DBGGame,
    material_names: List[str],
) -> Tuple[bool, str]:
    """
    在家园状态下激活工坊合成消耗品动作。

    Args:
        dbg_game: DBG 游戏实例
        material_names: 参与合成的材料名称列表（精确匹配，允许重复代表多份）

    Returns:
        Tuple[bool, str]: (是否成功, 失败时的错误详情)
    """
    if not dbg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法激活合成动作"
        logger.error(f"激活合成消耗品失败: {error_detail}")
        return False, error_detail

    if not material_names:
        error_detail = "材料列表为空，至少需要一种材料"
        logger.error(f"激活合成消耗品失败: {error_detail}")
        return False, error_detail

    storage_entity = dbg_game.get_storage_entity()
    assert storage_entity is not None, "全局储物箱实体不存在！"
    assert storage_entity.has(StorageComponent), "全局储物箱实体缺少 StorageComponent"

    storage = storage_entity.get(StorageComponent)

    # 校验每种材料在储物箱中存在且类型为 MATERIAL_ITEM（按 count 追踪可用数量）
    available: Dict[str, int] = {}
    for item in storage.items:
        if item.type == ItemType.MATERIAL_ITEM:
            available[item.name] = available.get(item.name, 0) + item.count

    demand: Dict[str, int] = {}
    for name in material_names:
        demand[name] = demand.get(name, 0) + 1

    for name, required in demand.items():
        if available.get(name, 0) < required:
            error_detail = f"储物箱中材料 {name!r} 数量不足（需要 {required}，当前 {available.get(name, 0)}）"
            logger.error(f"激活合成消耗品失败: {error_detail}")
            return False, error_detail

    # 收集材料对象（count = 本次使用量），预填入 action
    material_items: List[MaterialItem] = []
    for mat_name, used in demand.items():
        source = next(
            (
                item
                for item in storage.items
                if item.name == mat_name and item.type == ItemType.MATERIAL_ITEM
            ),
            None,
        )
        assert source is not None and isinstance(source, MaterialItem)
        copied = source.model_copy(deep=True)
        copied.count = used
        material_items.append(copied)

    workshop_entities = dbg_game.get_group(
        Matcher(all_of=[WorldComponent, WorkshopComponent])
    ).entities.copy()

    if not workshop_entities:
        error_detail = "未找到工坊世界系统实体，无法激活合成动作"
        logger.error(f"激活合成消耗品失败: {error_detail}")
        return False, error_detail

    assert len(workshop_entities) == 1, "存在多个工坊世界系统实体，数据异常"
    workshop_entity = next(iter(workshop_entities))

    if workshop_entity.has(CraftConsumableAction):
        error_detail = "合成动作已存在，请勿重复激活"
        logger.warning(f"激活合成消耗品失败: {error_detail}")
        return False, error_detail

    logger.debug(f"激活合成消耗品: {workshop_entity.name}, 材料={material_names}")
    workshop_entity.replace(
        CraftConsumableAction,
        workshop_entity.name,
        list(material_names),
        material_items,
    )
    return True, ""


###################################################################################################################################################################
def activate_craft_gear_item(
    dbg_game: DBGGame,
    material_names: List[str],
) -> Tuple[bool, str]:
    """预校验材料并激活装备合成动作（CraftGearItemAction），实际合成由 CraftGearItemActionSystem 执行。

    Args:
        dbg_game: DBG 游戏实例
        material_names: 参与合成的材料名称列表（允许重复代表多份）

    Returns:
        (True, "") 表示激活成功；(False, error_detail) 表示前置校验失败
    """
    if not dbg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法激活合成动作"
        logger.error(f"激活合成装备失败: {error_detail}")
        return False, error_detail

    if not material_names:
        error_detail = "材料列表为空，至少需要一种材料"
        logger.error(f"激活合成装备失败: {error_detail}")
        return False, error_detail

    storage_entity = dbg_game.get_storage_entity()
    assert storage_entity is not None, "全局储物箱实体不存在！"
    assert storage_entity.has(StorageComponent), "全局储物箱实体缺少 StorageComponent"

    storage = storage_entity.get(StorageComponent)

    # 校验每种材料在储物箱中存在且类型为 MATERIAL_ITEM（按 count 追踪可用数量）
    available: Dict[str, int] = {}
    for item in storage.items:
        if item.type == ItemType.MATERIAL_ITEM:
            available[item.name] = available.get(item.name, 0) + item.count

    demand: Dict[str, int] = {}
    for name in material_names:
        demand[name] = demand.get(name, 0) + 1

    for name, required in demand.items():
        if available.get(name, 0) < required:
            error_detail = f"储物箱中材料 {name!r} 数量不足（需要 {required}，当前 {available.get(name, 0)}）"
            logger.error(f"激活合成装备失败: {error_detail}")
            return False, error_detail

    # 收集材料对象（count = 本次使用量），预填入 action
    material_items: List[MaterialItem] = []
    for mat_name, used in demand.items():
        source = next(
            (
                item
                for item in storage.items
                if item.name == mat_name and item.type == ItemType.MATERIAL_ITEM
            ),
            None,
        )
        assert source is not None and isinstance(source, MaterialItem)
        copied = source.model_copy(deep=True)
        copied.count = used
        material_items.append(copied)

    workshop_entities = dbg_game.get_group(
        Matcher(all_of=[WorldComponent, WorkshopComponent])
    ).entities.copy()

    if not workshop_entities:
        error_detail = "未找到工坊世界系统实体，无法激活合成动作"
        logger.error(f"激活合成装备失败: {error_detail}")
        return False, error_detail

    assert len(workshop_entities) == 1, "存在多个工坊世界系统实体，数据异常"
    workshop_entity = next(iter(workshop_entities))

    if workshop_entity.has(CraftGearItemAction):
        error_detail = "合成动作已存在，请勿重复激活"
        logger.warning(f"激活合成装备失败: {error_detail}")
        return False, error_detail

    logger.debug(f"激活合成装备: {workshop_entity.name}, 材料={material_names}")
    workshop_entity.replace(
        CraftGearItemAction, workshop_entity.name, list(material_names), material_items
    )
    return True, ""


###################################################################################################################################################################
def activate_craft_costume_item(
    dbg_game: DBGGame,
    material_names: List[str],
) -> Tuple[bool, str]:
    """预校验材料并激活时装制作动作（CraftCostumeItemAction），实际制作由 CraftCostumeItemActionSystem 执行。

    Args:
        dbg_game: DBG 游戏实例
        material_names: 参与制作的材料名称列表（允许重复代表多份）

    Returns:
        (True, "") 表示激活成功；(False, error_detail) 表示前置校验失败
    """
    if not dbg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法激活制作动作"
        logger.error(f"激活制作时装失败: {error_detail}")
        return False, error_detail

    if not material_names:
        error_detail = "材料列表为空，至少需要一种材料"
        logger.error(f"激活制作时装失败: {error_detail}")
        return False, error_detail

    storage_entity = dbg_game.get_storage_entity()
    assert storage_entity is not None, "全局储物箱实体不存在！"
    assert storage_entity.has(StorageComponent), "全局储物箱实体缺少 StorageComponent"

    storage = storage_entity.get(StorageComponent)

    # 校验每种材料在储物箱中存在且类型为 MATERIAL_ITEM（按 count 追踪可用数量）
    available: Dict[str, int] = {}
    for item in storage.items:
        if item.type == ItemType.MATERIAL_ITEM:
            available[item.name] = available.get(item.name, 0) + item.count

    demand: Dict[str, int] = {}
    for name in material_names:
        demand[name] = demand.get(name, 0) + 1

    for name, required in demand.items():
        if available.get(name, 0) < required:
            error_detail = f"储物箱中材料 {name!r} 数量不足（需要 {required}，当前 {available.get(name, 0)}）"
            logger.error(f"激活制作时装失败: {error_detail}")
            return False, error_detail

    # 收集材料对象（count = 本次使用量），预填入 action
    material_items: List[MaterialItem] = []
    for mat_name, used in demand.items():
        source = next(
            (
                item
                for item in storage.items
                if item.name == mat_name and item.type == ItemType.MATERIAL_ITEM
            ),
            None,
        )
        assert source is not None and isinstance(source, MaterialItem)
        copied = source.model_copy(deep=True)
        copied.count = used
        material_items.append(copied)

    workshop_entities = dbg_game.get_group(
        Matcher(all_of=[WorldComponent, WorkshopComponent])
    ).entities.copy()

    if not workshop_entities:
        error_detail = "未找到工坊世界系统实体，无法激活制作动作"
        logger.error(f"激活制作时装失败: {error_detail}")
        return False, error_detail

    assert len(workshop_entities) == 1, "存在多个工坊世界系统实体，数据异常"
    workshop_entity = next(iter(workshop_entities))

    if workshop_entity.has(CraftCostumeItemAction):
        error_detail = "制作动作已存在，请勿重复激活"
        logger.warning(f"激活制作时装失败: {error_detail}")
        return False, error_detail

    logger.debug(f"激活制作时装: {workshop_entity.name}, 材料={material_names}")
    workshop_entity.replace(
        CraftCostumeItemAction,
        workshop_entity.name,
        list(material_names),
        material_items,
    )
    return True, ""
