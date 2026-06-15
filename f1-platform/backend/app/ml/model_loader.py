import json
import logging
from pathlib import Path
from typing import Any, Optional

import joblib

from app.config import settings

logger = logging.getLogger(__name__)


class ModelStore:
    _instance: Optional["ModelStore"] = None

    def __new__(cls) -> "ModelStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self.position_model: Any | None = None
        self.top10_model: Any | None = None
        self.podium_model: Any | None = None
        self.position_gain_model: Any | None = None
        self.feature_importances: dict[str, Any] = {}
        self.model_metadata: dict[str, Any] = {}
        self.is_loaded = False
        self._initialized = True

    def _load_joblib(self, models_dir: Path, filename: str) -> Any | None:
        path = models_dir / filename
        if not path.exists():
            logger.warning("Model file missing: %s", path)
            return None
        model = joblib.load(path)
        logger.info("Loaded model: %s", path)
        return model

    def _load_json(self, models_dir: Path, filename: str) -> dict[str, Any]:
        path = models_dir / filename
        if not path.exists():
            logger.warning("Model metadata file missing: %s", path)
            return {}
        with path.open("r", encoding="utf-8") as json_file:
            data = json.load(json_file)
        logger.info("Loaded model metadata: %s", path)
        return data

    def load_all(self, models_dir: str) -> None:
        path = Path(models_dir)
        self.position_model = self._load_joblib(path, "position_model.joblib")
        self.top10_model = self._load_joblib(path, "top10_model.joblib")
        self.podium_model = self._load_joblib(path, "podium_model.joblib")
        self.position_gain_model = self._load_joblib(path, "position_gain_model.joblib")
        self.feature_importances = self._load_json(path, "feature_importances.json")
        self.model_metadata = self._load_json(path, "model_metadata.json")

        self.is_loaded = any(
            model is not None
            for model in [
                self.position_model,
                self.top10_model,
                self.podium_model,
                self.position_gain_model,
            ]
        )
        if not self.is_loaded:
            logger.critical("No ML models were loaded from %s", path)

    def is_ready(self) -> bool:
        return self.position_model is not None and self.top10_model is not None and self.podium_model is not None


model_store = ModelStore()


def load_all_models() -> None:
    model_store.load_all(settings.MODELS_STORE_PATH)
