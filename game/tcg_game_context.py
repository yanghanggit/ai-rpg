from entitas import Context, Entity  # type: ignore
from typing import final, Optional, List
from game.base_game import BaseGame
from models.entity_models import ComponentSnapshot, EntitySnapshot
from components.components import (
    FinalAppearanceComponent,
    BaseFormComponent,
    COMPONENTS_REGISTRY,
)
from loguru import logger


@final
class TCGGameContext(Context):

    ###############################################################################################################################################
    def __init__(
        self,
    ) -> None:
        #
        super().__init__()
        self._game: Optional[BaseGame] = None

    ###############################################################################################################################################
    # 创建实体
    def _test_build(self, count: int) -> List[Entity]:

        ret: List[Entity] = []

        for i in range(count):
            test_entity = self.create_entity()
            name = "test_entity" + str(i + 1)
            test_entity.add(
                BaseFormComponent, name, f"这是一个测试BaseFormComponent{name}"
            )
            test_entity.add(
                FinalAppearanceComponent,
                name,
                f"这是一个测试FinalAppearanceComponent{name}",
            )

            ret.append(test_entity)

        return ret

    ###############################################################################################################################################
    def make_snapshot(self) -> List[EntitySnapshot]:

        ret: List[EntitySnapshot] = []

        entities = self._entities
        for entity in entities:
            entity_snapshot = EntitySnapshot(name="", components=[])
            for key, value in entity._components.items():
                entity_snapshot.components.append(
                    ComponentSnapshot(name=key.__name__, data=value._asdict())
                )
            ret.append(entity_snapshot)

        return ret

    ###############################################################################################################################################
    def restore_from_snapshot(self, entity_snapshots: List[EntitySnapshot]) -> None:
        # 测试数据
        test_entities = self._test_build(5)

        # 保存快照
        entity_snapshots = self.make_snapshot()

        # 删除测试数据
        for test_entity in test_entities:
            self.destroy_entity(test_entity)

        for en_snapshot in entity_snapshots:

            entity = self.create_entity()

            for comp_snapshot in en_snapshot.components:

                comp_class = COMPONENTS_REGISTRY.get(comp_snapshot.name)
                assert comp_class is not None
                restore_comp = comp_class(**comp_snapshot.data)
                assert restore_comp is not None
                logger.info(
                    f"comp_class = {comp_class.__name__}, comp = {restore_comp}"
                )
                entity.insert(comp_class, restore_comp)

    ###############################################################################################################################################
