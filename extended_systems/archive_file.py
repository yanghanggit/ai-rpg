from typing import final, List
from overrides import override
from models.file_models import (
    StageArchiveFileModel,
    ActorArchiveFileModel,
)
from extended_systems.base_file import BaseFile


@final
class ActorArchiveFile(BaseFile):
    def __init__(
        self,
        model: ActorArchiveFileModel,
    ) -> None:
        super().__init__(model.name, model.owner)
        self._model = model

    @override
    def serialization(self) -> str:
        return self._model.model_dump_json()

    @override
    def deserialization(self, content: str) -> None:
        self._model = ActorArchiveFileModel.model_validate_json(content)
        self._name = self._model.name
        self._owner_name = self._model.owner

    @property
    def appearance(self) -> str:
        return self._model.appearance

    def set_appearance(self, appearance: str) -> None:
        self._model.appearance = appearance

    def update(self, model: ActorArchiveFileModel) -> None:
        self._model = model
        self._name = model.name
        self._owner_name = model.owner


############################################################################################################
############################################################################################################
############################################################################################################
class StageArchiveFile(BaseFile):
    def __init__(self, model: StageArchiveFileModel) -> None:
        super().__init__(model.name, model.owner)
        self._model: StageArchiveFileModel = model

    @override
    def serialization(self) -> str:
        return self._model.model_dump_json()

    @override
    def deserialization(self, content: str) -> None:
        self._model = StageArchiveFileModel.model_validate_json(content)
        self._name = self._model.name
        self._owner_name = self._model.owner

    @property
    def stage_narrate(self) -> str:
        return self._model.stage_narrate

    def set_stage_narrate(self, narrate: str) -> None:
        self._model.stage_narrate = narrate

    def set_stage_tags(self, tags: List[str]) -> None:
        self._model.stage_tags = tags

    def update(self, model: StageArchiveFileModel) -> None:
        self._model = model
        self._name = model.name
        self._owner_name = model.owner


############################################################################################################
############################################################################################################
############################################################################################################
