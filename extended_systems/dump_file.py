from typing import final
from overrides import override
import json
from loguru import logger
from models.file_models import (
    EntityProfileModel,
)
from extended_systems.base_file import BaseFile


@final
class EntityProfileFile(BaseFile):
    def __init__(self, model: EntityProfileModel) -> None:
        super().__init__(model.name, model.name)
        self._model: EntityProfileModel = model

    @override
    def serialization(self) -> str:
        if self._model is None:
            return ""
        try:
            return self._model.model_dump_json()
        except Exception as e:
            logger.error(f"{e}")
        return ""

    @override
    def deserialization(self, content: str) -> None:
        self._model = EntityProfileModel.model_validate_json(content)
        self._name = self._model.name
        self._owner_name = self._model.name
