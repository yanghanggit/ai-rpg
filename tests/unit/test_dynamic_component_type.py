"""测试动态组件类型创建与挂载功能。

覆盖范围：
- registry.create_component_type 动态创建组件类（含幂等与字段定义）
- registry.resolve_component_type 惰性重建动态组件（含按 data 推断字段）
- DBGGame.create_stage_entities 挂载 Stage.components
- RPGEntityManager.deserialize_entities 跨进程重建动态组件
"""

import uuid
from typing import Any, Iterator

import pytest
from pydantic import ValidationError

from src.ai_rpg.entitas import Entity
from src.ai_rpg.entitas.components import Component
from src.ai_rpg.game.rpg_entity_manager import RPGEntityManager
from src.ai_rpg.models import (
    COMPONENT_TYPES,
    ComponentSerialization,
    HomeComponent,
    IdentityComponent,
    Stage,
    StageComponent,
    StageType,
    create_component_type,
    resolve_component_type,
)


############################################################################################################
@pytest.fixture(autouse=True)
def _clean_dynamic_component_types() -> Iterator[None]:
    """测试结束后清理动态注册的组件类型，避免污染全局注册表。"""
    before = set(COMPONENT_TYPES.keys())
    yield
    for key in list(COMPONENT_TYPES.keys()):
        if key not in before:
            del COMPONENT_TYPES[key]


############################################################################################################
def _make_stage_model(name: str, component_name: str) -> Stage:
    """构造一个挂载了指定动态组件的 Stage 模型。"""
    return Stage(
        name=name,
        type=StageType.HOME,
        profile="测试场景",
        system_message=f"{name} 的系统消息",
        actors=[],
        components=[ComponentSerialization(name=component_name, data={"name": name})],
    )


############################################################################################################
# create_component_type
############################################################################################################
class TestCreateComponentType:
    def test_creates_registered_component_subclass(self) -> None:
        cls = create_component_type("TestDynamicComponent")

        assert cls.__name__ == "TestDynamicComponent"
        assert issubclass(cls, Component)
        assert COMPONENT_TYPES["TestDynamicComponent"] is cls
        assert cls().model_dump() == {}

    def test_is_idempotent(self) -> None:
        cls1 = create_component_type("TestDynamicComponent")
        cls2 = create_component_type("TestDynamicComponent")

        assert cls1 is cls2

    def test_supports_field_definitions(self) -> None:
        cls = create_component_type("TestDynamicWithField", name=(str, ...))

        with pytest.raises(ValidationError):
            cls()
        inst = cls.model_validate({"name": "guard"})
        assert inst.model_dump() == {"name": "guard"}

    def test_rejects_empty_or_non_string_name(self) -> None:
        with pytest.raises(AssertionError):
            create_component_type("   ")
        with pytest.raises(AssertionError):
            create_component_type(123)  # type: ignore[arg-type]

    def test_usable_as_marker_on_entity(self) -> None:
        cls = create_component_type("TestDynamicOnEntity")

        entity = Entity()
        entity.activate(1)
        entity.add(cls)

        assert entity.has(cls)
        assert entity.get(cls) == cls()


############################################################################################################
# resolve_component_type
############################################################################################################
class TestResolveComponentType:
    def test_returns_registered_class(self) -> None:
        cls = create_component_type("TestResolveRegistered")

        assert resolve_component_type("TestResolveRegistered", {}) is cls

    def test_rebuilds_unknown_empty_data_component(self) -> None:
        cls = resolve_component_type("TestResolveRebuild", {})

        assert cls.__name__ == "TestResolveRebuild"
        assert COMPONENT_TYPES["TestResolveRebuild"] is cls

    def test_rebuilds_unknown_non_empty_data_with_inferred_fields(self) -> None:
        cls = resolve_component_type("TestResolveWithField", {"name": "场景.测试"})

        assert cls.__name__ == "TestResolveWithField"
        assert COMPONENT_TYPES["TestResolveWithField"] is cls
        inst = cls.model_validate({"name": "场景.测试"})
        assert inst.model_dump() == {"name": "场景.测试"}


############################################################################################################
# DBGGame.create_stage_entities 集成
############################################################################################################
class TestCreateStageEntitiesDynamicComponent:
    def test_attaches_dynamic_component(self, sample_game: Any) -> None:
        tag_name = "integration_001"
        tag_cls = create_component_type(tag_name, name=(str, ...))
        stage_model = _make_stage_model("场景.测试房", "integration_001")

        stage_entities = sample_game.create_stage_entities([stage_model])

        assert len(stage_entities) == 1
        stage_entity = stage_entities[0]
        assert stage_entity.has(StageComponent)
        assert stage_entity.has(HomeComponent)
        assert stage_entity.has(tag_cls)
        assert stage_entity.get(tag_cls).model_dump() == {"name": "场景.测试房"}

    def test_each_stage_gets_its_own_unique_component(self, sample_game: Any) -> None:
        cls_a = create_component_type("integration_a", name=(str, ...))
        cls_b = create_component_type("integration_b", name=(str, ...))

        entities = sample_game.create_stage_entities(
            [
                _make_stage_model("场景.A", "integration_a"),
                _make_stage_model("场景.B", "integration_b"),
            ]
        )
        by_name = {e.name: e for e in entities}

        assert by_name["场景.A"].has(cls_a)
        assert not by_name["场景.A"].has(cls_b)
        assert by_name["场景.B"].has(cls_b)
        assert not by_name["场景.B"].has(cls_a)
        assert by_name["场景.A"].get(cls_a).model_dump() == {"name": "场景.A"}
        assert by_name["场景.B"].get(cls_b).model_dump() == {"name": "场景.B"}


############################################################################################################
# RPGEntityManager.deserialize_entities 集成
############################################################################################################
class TestDeserializeEntitiesDynamicComponent:
    def test_rebuilds_dynamic_component_from_serialization(self) -> None:
        tag_name = "deser_001"
        tag_cls = create_component_type(tag_name, name=(str, ...))

        source = RPGEntityManager()
        entity = source._create_entity("场景.序列化测试")
        entity.add(IdentityComponent, "场景.序列化测试", 1, str(uuid.uuid4()))
        entity.set(tag_cls, tag_cls.model_validate({"name": "场景.序列化测试"}))

        serialized = source.serialize_entities({entity})

        # 模拟全新进程：动态类不在注册表中
        del COMPONENT_TYPES[tag_name]
        assert tag_name not in COMPONENT_TYPES

        target = RPGEntityManager()
        restored = target.deserialize_entities(serialized)

        restored_entity = next(iter(restored))
        assert tag_name in COMPONENT_TYPES  # 反序列化时已惰性重建
        rebuilt_cls = COMPONENT_TYPES[tag_name]
        assert restored_entity.name == "场景.序列化测试"
        assert restored_entity.has(rebuilt_cls)
        assert restored_entity.get(rebuilt_cls).model_dump() == {
            "name": "场景.序列化测试"
        }
