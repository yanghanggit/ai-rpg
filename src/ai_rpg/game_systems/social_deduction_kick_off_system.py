import copy
from typing import final, Dict
from loguru import logger
from overrides import override
from ..entitas import ExecuteProcessor, InitializeProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import (
    ModeratorComponent,
    WerewolfComponent,
    SeerComponent,
    WitchComponent,
    VillagerComponent,
    SDCharacterSheetName,
    AppearanceComponent,
    EnvironmentComponent,
)
from ..utils.md_format import format_dict_as_markdown_list


###############################################################################################################################################
@final
class SocialDeductionKickOffSystem(ExecuteProcessor, InitializeProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###############################################################################################################################################
    @override
    async def initialize(self) -> None:
        # 分配角色
        self._assign_role_to_all_actors()

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:
        if self._game._time_marker > 0:
            return
        logger.info("第一夜，狼人请睁眼")

        # 给狼人添加上下文来识别同伴
        self._reveal_werewolf_allies()

        # 第一次观察其他的参赛选手
        self._initialize_player_awareness()

    ###############################################################################################################################################
    def _assign_role_to_all_actors(self) -> None:
        """为所有角色分配狼人杀角色"""

        all_actors = self._game._world.boot.actors
        for actor in all_actors:

            actor_entity = self._game.get_entity_by_name(actor.name)
            assert actor_entity is not None, f"Actor Entity 不存在: {actor.name}"

            match actor.character_sheet.name:
                case SDCharacterSheetName.MODERATOR:
                    actor_entity.replace(ModeratorComponent, actor.name)
                    logger.info(f"分配角色: {actor.name} -> Moderator")

                case SDCharacterSheetName.WEREWOLF:
                    actor_entity.replace(WerewolfComponent, actor.name)
                    logger.info(f"分配角色: {actor.name} -> Werewolf")

                case SDCharacterSheetName.SEER:
                    actor_entity.replace(SeerComponent, actor.name)
                    logger.info(f"分配角色: {actor.name} -> Seer")

                case SDCharacterSheetName.WITCH:
                    actor_entity.replace(WitchComponent, actor.name)
                    logger.info(f"分配角色: {actor.name} -> Witch")

                case SDCharacterSheetName.VILLAGER:
                    actor_entity.replace(VillagerComponent, actor.name)
                    logger.info(f"分配角色: {actor.name} -> Villager")

                case _:
                    assert False, f"未知的狼人杀角色: {actor.character_sheet.name}"

    ###############################################################################################################################################
    # 写一个函数，给狼人添加上下文来识别同伴
    def _reveal_werewolf_allies(self) -> None:
        """给狼人添加上下文来识别同伴"""
        werewolf_entities = self._game.get_group(
            Matcher(
                all_of=[WerewolfComponent],
            )
        ).entities.copy()

        for entity in werewolf_entities:

            # 每次循环都创建一个新的集合，避免修改原集合
            copy_entities = copy.copy(werewolf_entities)
            copy_entities.discard(entity)

            allied_werewolf_names = [
                e.get(WerewolfComponent).name for e in copy_entities
            ]
            logger.info(f"Werewolf {entity.name} 的同伴: {allied_werewolf_names}")
            self._game.append_human_message(
                entity,
                f"# 提示！你的同伴狼人有: {', '.join(allied_werewolf_names)}",
            )

    ###############################################################################################################################################
    # 第一次观察其他的参赛选手
    def _initialize_player_awareness(self) -> None:

        all_actor_entities = self._game.get_group(
            Matcher(
                any_of=[
                    WerewolfComponent,
                    SeerComponent,
                    WitchComponent,
                    VillagerComponent,
                ],
                none_of=[ModeratorComponent],
            )
        ).entities.copy()

        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "玩家实体不存在"

        stage_entity = self._game.safe_get_stage_entity(player_entity)
        assert stage_entity is not None, "场景实体不存在"

        environment_comp = stage_entity.get(EnvironmentComponent)
        assert environment_comp is not None, "场景组件不存在"

        # 创建一个数据结构。
        stage_actor_appearances_mapping: Dict[str, str] = {}
        for actor_entity in all_actor_entities:
            appearance_comp = actor_entity.get(AppearanceComponent)
            stage_actor_appearances_mapping[actor_entity.name] = (
                appearance_comp.appearance
            )

        logger.info(
            f"stage_actor_appearances_mapping = {stage_actor_appearances_mapping}"
        )

        for actor_entity in all_actor_entities:

            copy_stage_actor_appearances_mapping = copy.copy(
                stage_actor_appearances_mapping
            )
            copy_stage_actor_appearances_mapping.pop(actor_entity.name, None)

            prompt = f"""# 提示！准备开始比赛！你观察了场景与参赛的人员。
            
## 场景描述: 
 
{environment_comp.description}

## 参赛选手及外貌:

{format_dict_as_markdown_list(copy_stage_actor_appearances_mapping)}"""

            # 添加上下文！
            self._game.append_human_message(actor_entity, prompt)

    ###############################################################################################################################################
