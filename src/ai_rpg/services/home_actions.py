"""家园动作辅助函数模块"""

from typing import List, Tuple, Dict
from loguru import logger
from ..entitas import Matcher
from ..game.dbg_game import DBGGame
from ..models import (
    SpeakAction,
    TransStageAction,
    WearCostumeAction,
    RemoveCostumeAction,
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
    """

    # 检查玩家是否在家园场景中，如果不在则无法执行说话动作。
    if not dbg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法执行说话动作"
        logger.error(f"激活说话动作失败: {error_detail}")
        return False, error_detail

    # 检查目标角色名称是否为空，如果为空则无法执行说话动作。
    if not target:
        error_detail = "目标角色名称不能为空"
        logger.error(f"激活说话动作失败: {error_detail}")
        return False, error_detail

    # 验证目标角色存在
    target_entity = dbg_game.get_actor_entity(target)
    if target_entity is None:
        error_detail = f"目标角色 {target} 不存在"
        logger.error(f"激活说话动作失败: {error_detail}")
        return False, error_detail

    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"

    # 获取玩家实体，并确保其存在，以便挂载说话动作组件。
    logger.debug(f"激活说话动作: {player_entity.name} -> {target}: {content}")
    player_entity.replace(SpeakAction, player_entity.name, {target: content})

    # 为玩家自身激活行动计划（写入影子 plan，记录本轮上下文），是否让 NPC 也在本轮真正规划由调用方另行决定。
    activate_plan_action(dbg_game, [player_entity.name])

    # 返回成功消息，表示说话动作已成功激活。
    return True, ""


###################################################################################################################################################################
def activate_switch_stage(dbg_game: DBGGame, stage_name: str) -> Tuple[bool, str]:
    """
    激活玩家的场景转换动作，并触发当前场景所有角色的行动计划。
    """

    # 检查玩家是否在家园场景中，如果不在则无法执行场景转换动作。
    if not dbg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法执行场景转换动作"
        logger.error(f"激活场景转换失败: {error_detail}")
        return False, error_detail

    # 检查目标场景名称是否为空，如果为空则无法执行场景转换动作。
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

    # 检查目标场景是否为家园场景，如果不是则无法执行场景转换动作。
    if not target_stage_entity.has(HomeComponent):
        error_detail = f"{stage_name} 不是家园场景"
        logger.error(f"激活场景转换失败: {error_detail}")
        return False, error_detail

    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"

    # 验证目标场景与当前场景不同，避免重复转换。
    current_stage_entity = dbg_game.resolve_stage_entity(player_entity)
    assert current_stage_entity is not None, "玩家当前场景实体不存在！"

    # 检查目标场景是否与当前场景相同，如果相同则无需转换。
    if current_stage_entity.name == stage_name:
        error_detail = f"目标场景 {stage_name} 与当前场景相同"
        logger.error(f"激活场景转换失败: {error_detail}")
        return False, error_detail

    # 激活场景转换动作，将玩家从当前场景切换到目标场景。
    logger.debug(f"激活场景转换: {player_entity.name} -> {stage_name}")
    player_entity.replace(TransStageAction, player_entity.name, stage_name)

    # 为玩家自身激活行动计划（写入影子 plan，记录本轮上下文），是否让 NPC 也在本轮真正规划由调用方另行决定。
    activate_plan_action(dbg_game, [player_entity.name])

    # 返回成功消息，表示场景转换动作已成功激活。
    return True, ""


###################################################################################################################################################################
def activate_plan_action(dbg_game: DBGGame, actor_names: List[str]) -> Tuple[bool, str]:
    """
    为调用方（客户端）显式指定的角色列表激活行动计划（PlanAction）。
    """

    # 检查玩家是否在家园场景中，如果不在则无法激活行动计划。
    if not dbg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法激活行动计划"
        logger.error(f"激活行动计划失败: {error_detail}")
        return False, error_detail

    # 检查角色名称列表是否为空，如果为空则无法激活行动计划。
    if not actor_names:
        error_detail = "角色名称列表不能为空"
        logger.error(f"激活行动计划失败: {error_detail}")
        return False, error_detail

    # 逐一校验角色：必须存在、必须是 NPC 阵营角色（含玩家自身）、必须在家园场景中。
    resolved_entities = []
    for actor_name in actor_names:

        actor_entity = dbg_game.get_actor_entity(actor_name)
        if actor_entity is None:
            error_detail = f"角色 {actor_name} 不存在"
            logger.error(f"激活行动计划失败: {error_detail}")
            return False, error_detail

        if not actor_entity.has(NPCComponent):
            error_detail = f"角色 {actor_name} 不是 NPC 阵营角色，无法激活行动计划"
            logger.error(f"激活行动计划失败: {error_detail}")
            return False, error_detail

        if not dbg_game.is_actor_in_home_stage(actor_entity):
            error_detail = f"角色 {actor_name} 不在家园场景中，无法激活行动计划"
            logger.error(f"激活行动计划失败: {error_detail}")
            return False, error_detail

        resolved_entities.append(actor_entity)

    # 校验全部通过后再统一挂载，避免部分角色已挂载、部分校验失败导致的状态不一致。
    for actor_entity in resolved_entities:
        logger.debug(f"为角色 {actor_entity.name} 添加 PlanAction")
        actor_entity.replace(PlanAction, actor_entity.name)

    # 返回成功消息，表示所有角色的行动计划已成功激活。
    return True, f"成功为 {len(resolved_entities)} 个角色添加 PlanAction"


###################################################################################################################################################################
def add_party_member(dbg_game: DBGGame, member_name: str) -> Tuple[bool, str]:
    """
    将盟友加入远征队名单。
    """

    # 检查玩家是否在家园场景中，如果不在则无法修改远征队名单。
    if not dbg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法修改远征队名单"
        logger.error(f"添加远征队成员失败: {error_detail}")
        return False, error_detail

    # 获取要加入远征队的角色实体，验证其存在且为 NPC。
    member_entity = dbg_game.get_actor_entity(member_name)
    if member_entity is None:
        error_detail = f"角色 {member_name} 不存在"
        logger.error(f"添加远征队成员失败: {error_detail}")
        return False, error_detail

    # 检查角色是否为 NPC，如果不是则无法加入远征队。
    if not member_entity.has(NPCComponent):
        error_detail = f"角色 {member_name} 不是 NPC，无法加入远征队"
        logger.error(f"添加远征队成员失败: {error_detail}")
        return False, error_detail

    # 检查角色是否为玩家自身，如果是则无法加入远征队。
    if member_entity.has(PlayerComponent):
        error_detail = "不能将玩家自身加入远征队名单"
        logger.error(f"添加远征队成员失败: {error_detail}")
        return False, error_detail

    # 获取玩家实体，确保玩家实体存在，以便后续操作远征队名单。
    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"

    # 检查远征队名单中是否已存在该成员
    if player_entity.has(PartyRosterComponent):

        # 获取玩家实体当前的远征队成员列表，以便检查是否已经存在要添加的成员。
        existing_members = list(player_entity.get(PartyRosterComponent).members)
        if member_name in existing_members:
            error_detail = f"{member_name} 已在远征队名单中"
            logger.warning(f"添加远征队成员失败: {error_detail}")
            return False, error_detail

        # 将新的成员列表添加到现有成员列表中，准备更新玩家实体的 PartyRosterComponent。
        new_members = existing_members + [member_name]

    else:

        # 如果玩家实体尚未拥有 PartyRosterComponent，则创建一个新的成员列表，包含当前要加入的成员。
        new_members = [member_name]

    # 更新玩家实体的 PartyRosterComponent
    player_entity.replace(
        PartyRosterComponent,
        player_entity.name,
        new_members,
    )
    logger.debug(f"将 {member_name} 加入远征队名单")
    return True, ""


###################################################################################################################################################################
def remove_party_member(dbg_game: DBGGame, member_name: str) -> Tuple[bool, str]:
    """
    将盟友从远征队名单中移除。
    """

    # 检查玩家是否在家园场景中，如果不在则无法修改远征队名单。
    if not dbg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法修改远征队名单"
        logger.error(f"移除远征队成员失败: {error_detail}")
        return False, error_detail

    # 获取玩家实体，确保玩家实体存在，以便后续操作远征队名单。
    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"

    # 检查玩家实体是否拥有 PartyRosterComponent，如果没有则无法移除成员。
    if not player_entity.has(PartyRosterComponent):
        error_detail = f"{member_name} 不在远征队名单中"
        logger.warning(f"移除远征队成员失败: {error_detail}")
        return False, error_detail

    # 获取玩家实体当前的远征队成员列表，以便检查要移除的成员是否存在。
    roster = player_entity.get(PartyRosterComponent)
    if member_name not in roster.members:
        error_detail = f"{member_name} 不在远征队名单中"
        logger.warning(f"移除远征队成员失败: {error_detail}")
        return False, error_detail

    # 更新远征队名单，若移除后名单为空则移除 PartyRosterComponent
    new_members = [m for m in roster.members if m != member_name]
    if new_members:

        # 如果移除成员后远征队名单仍有其他成员，则更新玩家实体的 PartyRosterComponent。
        player_entity.replace(
            PartyRosterComponent,
            player_entity.name,
            new_members,
        )
    else:

        # 如果移除成员后远征队名单为空，则移除玩家实体的 PartyRosterComponent。
        player_entity.remove(PartyRosterComponent)
        logger.debug(f"远征队名单为空，移除 PartyRosterComponent")

    # 记录移除远征队成员的操作日志，并返回成功状态。
    logger.debug(f"将 {member_name} 从远征队名单移除")
    return True, ""


###################################################################################################################################################################
def get_party_roster(dbg_game: DBGGame) -> List[str]:
    """
    查阅当前远征队名单（不含玩家自身）。
    """
    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"
    if not player_entity.has(PartyRosterComponent):
        return []  # 玩家实体没有 PartyRosterComponent，返回空列表

    # 返回玩家实体当前的远征队成员列表（不含玩家自身）。
    return list(player_entity.get(PartyRosterComponent).members)


###################################################################################################################################################################
def activate_generate_dungeon(dbg_game: DBGGame) -> Tuple[bool, str]:
    """
    在家园状态下激活地下城创建动作。
    """

    # 检查玩家是否在家园场景中，如果不在则无法创建地下城。
    if not dbg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法创建地下城"
        logger.error(f"激活地下城创建失败: {error_detail}")
        return False, error_detail

    # 获取地下城生成系统实体，确保存在且唯一，以便后续激活地下城创建动作。
    world_system_entities = dbg_game.get_group(
        Matcher(all_of=[WorldComponent, DungeonGenerationComponent])
    ).entities.copy()

    # 检查是否找到了地下城生成系统实体，如果没有找到则无法激活地下城创建动作。
    if not world_system_entities:
        error_detail = "未找到地下城生成系统实体，无法激活地下城创建"
        logger.error(f"激活地下城创建失败: {error_detail}")
        return False, error_detail

    assert len(world_system_entities) == 1, "存在多个地下城生成系统实体，数据异常"
    world_system_entity = next(iter(world_system_entities))

    # 检查地下城生成系统实体是否已经有 GenerateDungeonAction，如果有则说明动作已激活，避免重复激活。
    if world_system_entity.has(GenerateDungeonAction):
        error_detail = "地下城创建动作已存在，请勿重复激活"
        logger.warning(f"激活地下城创建失败: {error_detail}")
        return False, error_detail

    # 激活地下城创建动作，将 GenerateDungeonAction 添加到地下城生成系统实体中。
    logger.debug(f"激活地下城创建: {world_system_entity.name}")
    world_system_entity.replace(GenerateDungeonAction, world_system_entity.name)
    return True, ""


###################################################################################################################################################################
def move_item_to_inventory(
    dbg_game: DBGGame,
    item_name: str,
) -> Tuple[bool, str]:
    """将道具从玩家储物箱（StorageComponent）移动到随身背包（InventoryComponent）。"""

    # 获取玩家实体和全局储物箱实体，并确保它们存在且具有相应的组件。
    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"

    # 获取全局储物箱实体，并确保它存在且具有 StorageComponent。
    storage_entity = dbg_game.get_storage_entity()
    assert storage_entity is not None, "全局储物箱实体不存在！"
    assert storage_entity.has(StorageComponent), "全局储物箱实体缺少 StorageComponent"
    assert player_entity.has(InventoryComponent), "玩家实体缺少 InventoryComponent"

    storage = storage_entity.get(StorageComponent)
    inventory = player_entity.get(InventoryComponent)

    # 在储物箱中查找指定名称的道具，如果不存在则返回错误。
    target = next((item for item in storage.items if item.name == item_name), None)
    if target is None:
        error_detail = f"储物箱中不存在名为 {item_name!r} 的道具"
        logger.error(f"移动道具到背包失败: {error_detail}")
        return False, error_detail

    # 检查道具类型，如果是时装道具则不允许移入随身背包。
    if target.type == ItemType.COSTUME_ITEM:
        error_detail = (
            f"时装 {item_name!r} 不允许移入随身背包，请通过外观更新功能直接使用"
        )
        logger.error(f"移动道具到背包失败: {error_detail}")
        return False, error_detail

    # 将道具从储物箱中移除，并添加到玩家随身背包中。
    new_storage_items = [item for item in storage.items if item is not target]
    new_inventory_items = list(inventory.items) + [target]

    # 使用 ECS 的 replace 方法更新储物箱和玩家随身背包的组件数据。
    storage_entity.replace(StorageComponent, storage.name, new_storage_items)
    player_entity.replace(InventoryComponent, player_entity.name, new_inventory_items)

    logger.debug(f"道具 {item_name!r} 已从储物箱移至随身背包")
    return True, ""


###################################################################################################################################################################
def move_item_to_storage(
    dbg_game: DBGGame,
    item_name: str,
) -> Tuple[bool, str]:
    """将道具从玩家随身背包（InventoryComponent）移动到储物箱（StorageComponent）。"""

    # 获取玩家实体和全局储物箱实体，并确保它们存在且具有相应的组件。
    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"

    # 获取全局储物箱实体，并确保它存在且具有 StorageComponent。
    storage_entity = dbg_game.get_storage_entity()
    assert storage_entity is not None, "全局储物箱实体不存在！"
    assert player_entity.has(InventoryComponent), "玩家实体缺少 InventoryComponent"
    assert storage_entity.has(StorageComponent), "全局储物箱实体缺少 StorageComponent"

    inventory = player_entity.get(InventoryComponent)
    storage = storage_entity.get(StorageComponent)

    # 在玩家随身背包中查找指定名称的道具，如果不存在则返回错误。
    target = next((item for item in inventory.items if item.name == item_name), None)
    if target is None:
        error_detail = f"随身背包中不存在名为 {item_name!r} 的道具"
        logger.error(f"移动道具到储物箱失败: {error_detail}")
        return False, error_detail

    # 将道具从玩家随身背包中移除，并添加到全局储物箱中。
    new_inventory_items = [item for item in inventory.items if item is not target]
    new_storage_items = list(storage.items) + [target]

    # 使用 ECS 的 replace 方法更新玩家随身背包和全局储物箱的组件数据。
    player_entity.replace(InventoryComponent, player_entity.name, new_inventory_items)
    storage_entity.replace(StorageComponent, storage.name, new_storage_items)

    logger.debug(f"道具 {item_name!r} 已从随身背包移至储物箱")
    return True, ""


###################################################################################################################################################################
def activate_wear_costume(
    dbg_game: DBGGame, item_name: str, target_name: str
) -> Tuple[bool, str]:
    """
    为指定角色激活穿上时装动作，时装来源为全局储物箱。
    """

    # 检查玩家是否在家园场景中，如果不在则无法更新外观。
    if not dbg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法更新外观"
        logger.error(f"激活穿装失败: {error_detail}")
        return False, error_detail

    # 获取全局储物箱实体，并确保它存在且具有 StorageComponent。
    storage_entity = dbg_game.get_storage_entity()
    assert storage_entity is not None, "全局储物箱实体不存在！"
    assert storage_entity.has(StorageComponent), "全局储物箱实体缺少 StorageComponent"

    # 确定目标实体：为空则报错
    if not target_name:
        error_detail = "目标角色名称不能为空"
        logger.error(f"激活穿装失败: {error_detail}")
        return False, error_detail

    # 获取目标角色实体，并确保它存在且具有 AppearanceComponent。
    target_entity = dbg_game.get_actor_entity(target_name)
    if target_entity is None:
        error_detail = f"目标角色 {target_name!r} 不存在"
        logger.error(f"激活穿装失败: {error_detail}")
        return False, error_detail

    # 检查目标角色是否具有 AppearanceComponent，如果没有则无法更新外观。
    if not target_entity.has(AppearanceComponent):
        error_detail = f"目标角色 {target_name!r} 缺少 AppearanceComponent"
        logger.error(f"激活穿装失败: {error_detail}")
        return False, error_detail

    # 穿装要求 item_name 必须非空；脱装请使用 activate_remove_costume。
    if not item_name:
        error_detail = "时装名称不能为空，如需脱下时装请调用 activate_remove_costume"
        logger.error(f"激活穿装失败: {error_detail}")
        return False, error_detail

    # 时装来源始终是全局 StorageComponent
    storage = storage_entity.get(StorageComponent)
    costume = next(
        (
            item
            for item in storage.items
            if item.name == item_name and item.type == ItemType.COSTUME_ITEM
        ),
        None,
    )

    # 如果在储物箱中未找到指定的时装，则返回错误。
    if costume is None:
        error_detail = f"储物箱中不存在名为 {item_name!r} 的时装"
        logger.error(f"激活穿装失败: {error_detail}")
        return False, error_detail

    # 在储物箱中找到指定的时装后，触发穿装动作，将目标实体的外观更新为该时装。
    logger.debug(f"激活穿装: {target_entity.name} <- {item_name}")
    target_entity.replace(WearCostumeAction, target_entity.name, item_name, costume)

    # 穿装动作激活成功，返回 True 表示激活成功。
    return True, ""


###################################################################################################################################################################
def activate_remove_costume(dbg_game: DBGGame, target_name: str) -> Tuple[bool, str]:
    """
    为指定角色激活脱下当前时装动作，时装将归还全局储物箱。
    """

    # 检查玩家是否在家园场景中，如果不在则无法更新外观。
    if not dbg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法更新外观"
        logger.error(f"激活脱装失败: {error_detail}")
        return False, error_detail

    # 确定目标实体：为空则报错
    if not target_name:
        error_detail = "目标角色名称不能为空"
        logger.error(f"激活脱装失败: {error_detail}")
        return False, error_detail

    # 获取目标角色实体，并确保它存在且具有 AppearanceComponent。
    target_entity = dbg_game.get_actor_entity(target_name)
    if target_entity is None:
        error_detail = f"目标角色 {target_name!r} 不存在"
        logger.error(f"激活脱装失败: {error_detail}")
        return False, error_detail

    # 检查目标角色是否具有 AppearanceComponent，如果没有则无法更新外观。
    if not target_entity.has(AppearanceComponent):
        error_detail = f"目标角色 {target_name!r} 缺少 AppearanceComponent"
        logger.error(f"激活脱装失败: {error_detail}")
        return False, error_detail

    logger.debug(f"激活脱装: {target_entity.name}")
    target_entity.replace(RemoveCostumeAction, target_entity.name)

    return True, ""


###################################################################################################################################################################
def activate_craft_consumable(
    dbg_game: DBGGame,
    material_names: List[str],
) -> Tuple[bool, str]:
    """
    在家园状态下激活工坊合成消耗品动作。
    """

    # 检查玩家是否在家园场景中，如果不在则无法激活合成动作。
    if not dbg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法激活合成动作"
        logger.error(f"激活合成消耗品失败: {error_detail}")
        return False, error_detail

    # 检查材料列表是否为空，如果为空则无法激活合成动作。
    if not material_names:
        error_detail = "材料列表为空，至少需要一种材料"
        logger.error(f"激活合成消耗品失败: {error_detail}")
        return False, error_detail

    # 获取全局储物箱实体，并确保它存在且具有 StorageComponent。
    storage_entity = dbg_game.get_storage_entity()
    assert storage_entity is not None, "全局储物箱实体不存在！"
    assert storage_entity.has(StorageComponent), "全局储物箱实体缺少 StorageComponent"
    storage = storage_entity.get(StorageComponent)

    # 校验每种材料在储物箱中存在且类型为 MATERIAL_ITEM（按 count 追踪可用数量）
    available: Dict[str, int] = {}
    for item in storage.items:
        if item.type == ItemType.MATERIAL_ITEM:
            available[item.name] = available.get(item.name, 0) + item.count

    # 统计每种材料的需求数量（按 count 追踪所需数量）
    demand: Dict[str, int] = {}
    for name in material_names:
        demand[name] = demand.get(name, 0) + 1

    # 检查每种材料在储物箱中的可用数量是否满足需求，如果不足则返回错误。
    for name, required in demand.items():
        if available.get(name, 0) < required:
            error_detail = f"储物箱中材料 {name!r} 数量不足（需要 {required}，当前 {available.get(name, 0)}）"
            logger.error(f"激活合成消耗品失败: {error_detail}")
            return False, error_detail

    # 收集材料对象（count = 本次使用量），预填入 action，确保每种材料在储物箱中存在且类型正确
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

    # 获取工坊世界系统实体，并确保只存在一个实体，否则返回错误。
    workshop_entities = dbg_game.get_group(
        Matcher(all_of=[WorldComponent, WorkshopComponent])
    ).entities.copy()

    # 检查是否存在工坊世界系统实体，如果不存在则返回错误。
    if not workshop_entities:
        error_detail = "未找到工坊世界系统实体，无法激活合成动作"
        logger.error(f"激活合成消耗品失败: {error_detail}")
        return False, error_detail

    # 确保只存在一个工坊世界系统实体，否则返回错误。
    assert len(workshop_entities) == 1, "存在多个工坊世界系统实体，数据异常"
    workshop_entity = next(iter(workshop_entities))

    # 检查工坊世界系统实体是否已经存在合成动作，如果存在则返回错误。
    if workshop_entity.has(CraftConsumableAction):
        error_detail = "合成动作已存在，请勿重复激活"
        logger.warning(f"激活合成消耗品失败: {error_detail}")
        return False, error_detail

    # 激活合成消耗品动作，将材料信息填入工坊世界系统实体的 CraftConsumableAction 中。
    logger.debug(f"激活合成消耗品: {workshop_entity.name}, 材料={material_names}")
    workshop_entity.replace(
        CraftConsumableAction,
        workshop_entity.name,
        list(material_names),
        material_items,
    )

    # 返回激活成功的结果。
    return True, ""


###################################################################################################################################################################
def activate_craft_gear_item(
    dbg_game: DBGGame,
    material_names: List[str],
) -> Tuple[bool, str]:
    """预校验材料并激活装备合成动作（CraftGearItemAction），实际合成由 CraftGearItemActionSystem 执行。"""

    # 检查玩家是否在家园场景中，如果不在则无法激活合成动作。
    if not dbg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法激活合成动作"
        logger.error(f"激活合成装备失败: {error_detail}")
        return False, error_detail

    # 检查材料列表是否为空，如果为空则无法激活合成动作。
    if not material_names:
        error_detail = "材料列表为空，至少需要一种材料"
        logger.error(f"激活合成装备失败: {error_detail}")
        return False, error_detail

    # 获取全局储物箱实体，用于检查和收集材料。
    storage_entity = dbg_game.get_storage_entity()
    assert storage_entity is not None, "全局储物箱实体不存在！"
    assert storage_entity.has(StorageComponent), "全局储物箱实体缺少 StorageComponent"
    storage = storage_entity.get(StorageComponent)

    # 校验每种材料在储物箱中存在且类型为 MATERIAL_ITEM（按 count 追踪可用数量）
    available: Dict[str, int] = {}
    for item in storage.items:
        if item.type == ItemType.MATERIAL_ITEM:
            available[item.name] = available.get(item.name, 0) + item.count

    # 统计每种材料的需求数量（按 count 追踪需要的数量）
    demand: Dict[str, int] = {}
    for name in material_names:
        demand[name] = demand.get(name, 0) + 1

    # 检查每种材料的可用数量是否满足需求，如果不足则无法激活合成动作。
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

    # 获取工坊世界系统实体，用于激活合成动作。
    workshop_entities = dbg_game.get_group(
        Matcher(all_of=[WorldComponent, WorkshopComponent])
    ).entities.copy()

    # 如果没有找到工坊世界系统实体，则无法激活合成动作。
    if not workshop_entities:
        error_detail = "未找到工坊世界系统实体，无法激活合成动作"
        logger.error(f"激活合成装备失败: {error_detail}")
        return False, error_detail

    # 确保只存在一个工坊世界系统实体，否则数据异常。
    assert len(workshop_entities) == 1, "存在多个工坊世界系统实体，数据异常"
    workshop_entity = next(iter(workshop_entities))

    # 检查工坊世界系统实体是否已经存在合成动作，如果存在则无法重复激活。
    if workshop_entity.has(CraftGearItemAction):
        error_detail = "合成动作已存在，请勿重复激活"
        logger.warning(f"激活合成装备失败: {error_detail}")
        return False, error_detail

    # 激活合成动作，将材料信息填入工坊世界系统实体的 CraftGearItemAction 中。
    logger.debug(f"激活合成装备: {workshop_entity.name}, 材料={material_names}")
    workshop_entity.replace(
        CraftGearItemAction, workshop_entity.name, list(material_names), material_items
    )

    # 激活合成动作成功，返回 True 表示激活成功。
    return True, ""


###################################################################################################################################################################
def activate_craft_costume_item(
    dbg_game: DBGGame,
    material_names: List[str],
) -> Tuple[bool, str]:
    """预校验材料并激活时装制作动作（CraftCostumeItemAction），实际制作由 CraftCostumeItemActionSystem 执行。"""

    # 检查玩家是否在家园场景中，如果不在则无法激活制作动作。
    if not dbg_game.is_player_in_home_stage:
        error_detail = "玩家不在家园场景中，无法激活制作动作"
        logger.error(f"激活制作时装失败: {error_detail}")
        return False, error_detail

    # 检查材料列表是否为空，如果为空则无法激活制作动作。
    if not material_names:
        error_detail = "材料列表为空，至少需要一种材料"
        logger.error(f"激活制作时装失败: {error_detail}")
        return False, error_detail

    # 获取全局储物箱实体，用于检查和收集材料。
    storage_entity = dbg_game.get_storage_entity()
    assert storage_entity is not None, "全局储物箱实体不存在！"
    assert storage_entity.has(StorageComponent), "全局储物箱实体缺少 StorageComponent"
    storage = storage_entity.get(StorageComponent)

    # 校验每种材料在储物箱中存在且类型为 MATERIAL_ITEM（按 count 追踪可用数量）
    available: Dict[str, int] = {}
    for item in storage.items:
        if item.type == ItemType.MATERIAL_ITEM:
            available[item.name] = available.get(item.name, 0) + item.count

    # 统计每种材料的需求数量（按 count 追踪需要的数量）
    demand: Dict[str, int] = {}
    for name in material_names:
        demand[name] = demand.get(name, 0) + 1

    # 检查每种材料的可用数量是否满足需求，如果不足则无法激活制作动作。
    for name, required in demand.items():
        if available.get(name, 0) < required:
            error_detail = f"储物箱中材料 {name!r} 数量不足（需要 {required}，当前 {available.get(name, 0)}）"
            logger.error(f"激活制作时装失败: {error_detail}")
            return False, error_detail

    # 收集材料对象（count = 本次使用量），预填入 CraftCostumeItemAction 中。
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

    # 获取工坊世界系统实体，用于激活制作动作。
    workshop_entities = dbg_game.get_group(
        Matcher(all_of=[WorldComponent, WorkshopComponent])
    ).entities.copy()

    # 如果没有找到工坊世界系统实体，则无法激活制作动作。
    if not workshop_entities:
        error_detail = "未找到工坊世界系统实体，无法激活制作动作"
        logger.error(f"激活制作时装失败: {error_detail}")
        return False, error_detail

    # 确保只存在一个工坊世界系统实体，否则数据异常。
    assert len(workshop_entities) == 1, "存在多个工坊世界系统实体，数据异常"
    workshop_entity = next(iter(workshop_entities))

    # 检查工坊世界系统实体是否已经存在制作动作，如果存在则无法重复激活。
    if workshop_entity.has(CraftCostumeItemAction):
        error_detail = "制作动作已存在，请勿重复激活"
        logger.warning(f"激活制作时装失败: {error_detail}")
        return False, error_detail

    # 激活制作动作，将材料信息填入工坊世界系统实体的 CraftCostumeItemAction 中。
    logger.debug(f"激活制作时装: {workshop_entity.name}, 材料={material_names}")
    workshop_entity.replace(
        CraftCostumeItemAction,
        workshop_entity.name,
        list(material_names),
        material_items,
    )

    # 制作动作激活成功，返回 True 表示激活成功。
    return True, ""
