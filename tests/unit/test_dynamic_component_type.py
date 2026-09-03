"""测试动态组件类型创建与 Stage 唯一组件挂载功能。

覆盖范围：
- registry.create_component_type 动态创建组件类（含幂等与字段定义）
- registry.resolve_component_type 惰性重建动态组件（含按 data 推断字段）
- Stage.code_name 必填字段与序列化
- demo.world 唯一组件挂载辅助函数
- DBGGame.create_stage_entities 挂载 Stage.components
- RPGEntityManager.deserialize_entities 跨进程重建动态组件
"""

import importlib
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

# demo.world 内部使用 `ai_rpg.models`（而非 `src.ai_rpg.models`）导入，静态导入会
# 让 mypy 把同一源文件识别为两个模块（"Source file found twice"）。这里改用
# importlib 动态导入，运行时仍加载真实的 demo 代码。
_demo_world: Any = importlib.import_module("demo.world")


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
def _make_stage_model(name: str, code_name: str) -> Stage:
    """构造一个挂载了指定英文代号对应动态组件的 Stage 模型。"""
    return Stage(
        name=name,
        code_name=code_name,
        type=StageType.HOME,
        profile="测试场景",
        system_message=f"{name} 的系统消息",
        actors=[],
        components=[ComponentSerialization(name=code_name, data={"name": name})],
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
# Stage.code_name
############################################################################################################
class TestStageCodeName:
    def test_code_name_is_required(self) -> None:
        # 缺少 code_name 时，反序列化/构造必须失败
        with pytest.raises(ValidationError):
            Stage.model_validate(
                {
                    "name": "s",
                    "type": StageType.HOME,
                    "profile": "p",
                    "system_message": "s",
                    "actors": [],
                }
            )

    def test_serialization_round_trip(self) -> None:
        stage = _make_stage_model("场景.测试房", "test_room")

        restored = Stage.model_validate(stage.model_dump())

        assert restored.code_name == "test_room"
        assert restored.components[0].name == "test_room"
        assert restored.components[0].data == {"name": "场景.测试房"}


############################################################################################################
# demo.world 唯一组件辅助函数
############################################################################################################
class TestDemoStageComponentHelpers:
    def test_attach_stage_component(self) -> None:
        stage = Stage(
            name="场景.测试",
            code_name="test_room",
            type=StageType.HOME,
            profile="p",
            system_message="场景.测试",
            actors=[],
        )

        result = _demo_world._attach_stage_component(stage)

        assert result is stage
        assert len(stage.components) == 1
        assert stage.components[0].name == "test_room"
        assert stage.components[0].data == {"name": "场景.测试"}

    def test_attach_stage_component_rejects_invalid_code_name(self) -> None:
        stage = Stage(
            name="场景.测试",
            code_name="not valid!",
            type=StageType.HOME,
            profile="p",
            system_message="场景.测试",
            actors=[],
        )

        with pytest.raises(AssertionError, match="code_name"):
            _demo_world._attach_stage_component(stage)

    def test_attach_stage_component_rejects_duplicate_code_name(self) -> None:
        first = Stage(
            name="场景.A",
            code_name="dup_room",
            type=StageType.HOME,
            profile="p",
            system_message="场景.A",
            actors=[],
        )
        _demo_world._attach_stage_component(first)

        second = Stage(
            name="场景.B",
            code_name="dup_room",
            type=StageType.HOME,
            profile="p",
            system_message="场景.B",
            actors=[],
        )

        with pytest.raises(AssertionError, match="重名"):
            _demo_world._attach_stage_component(second)


############################################################################################################
# demo 蓝图/副本的 Stage 唯一标记
############################################################################################################
class TestDemoBlueprintUniqueTags:
    def test_all_blueprint_stages_have_unique_tags(self) -> None:
        blueprint = _demo_world.create_ruins_blueprint("Game1")

        code_names = [stage.code_name for stage in blueprint.stages]
        assert all(code_names)
        assert len(set(code_names)) == len(code_names)
        for stage in blueprint.stages:
            assert len(stage.components) == 1
            assert stage.components[0].name == stage.code_name
            assert stage.components[0].data == {"name": stage.name}

    def test_all_dungeon_stages_have_unique_tags(self) -> None:
        dungeon = _demo_world.create_shrine_ruins_dungeon()

        stages = [room.stage for room in dungeon.rooms]
        code_names = [stage.code_name for stage in stages]
        assert all(code_names)
        assert len(set(code_names)) == len(code_names)


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
