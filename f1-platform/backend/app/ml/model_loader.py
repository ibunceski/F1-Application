import json
import logging
from pathlib import Path
from typing import Any, Optional

import joblib

from app.config import settings
from app.models.ml_feature import POST_QUALIFYING, PREDICTION_CONTEXTS

logger = logging.getLogger(__name__)

MODEL_FILENAMES = {
    "position_model": "position_model.joblib",
    "top10_model": "top10_model.joblib",
    "podium_model": "podium_model.joblib",
    "position_gain_model": "position_gain_model.joblib",
}


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
        self.models_by_context: dict[str, dict[str, Any | None]] = {}
        self.feature_importances_by_context: dict[str, dict[str, Any]] = {}
        self.model_metadata_by_context: dict[str, dict[str, Any]] = {}
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
        self.models_by_context = {}
        self.feature_importances_by_context = {}
        self.model_metadata_by_context = {}

        for context in sorted(PREDICTION_CONTEXTS):
            self.models_by_context[context] = {
                model_name: self._load_joblib(path, f"{context}_{filename}")
                for model_name, filename in MODEL_FILENAMES.items()
            }
            self.feature_importances_by_context[context] = self._load_json(
                path,
                f"{context}_feature_importances.json",
            )
            self.model_metadata_by_context[context] = self._load_json(
                path,
                f"{context}_model_metadata.json",
            )

        post_models = self.models_by_context.get(POST_QUALIFYING, {})
        self.position_model = post_models.get("position_model")
        self.top10_model = post_models.get("top10_model")
        self.podium_model = post_models.get("podium_model")
        self.position_gain_model = post_models.get("position_gain_model")
        self.feature_importances = self.feature_importances_by_context
        self.model_metadata = self.model_metadata_by_context

        self.is_loaded = any(any(model is not None for model in models.values()) for models in self.models_by_context.values())
        if not self.is_loaded:
            logger.critical("No ML models were loaded from %s", path)

    def models_for_context(self, context: str) -> dict[str, Any | None]:
        return self.models_by_context.get(context, {})

    def metadata_for_context(self, context: str) -> dict[str, Any]:
        return self.model_metadata_by_context.get(context, {})

    def feature_importances_for_context(self, context: str) -> dict[str, Any]:
        return self.feature_importances_by_context.get(context, {})

    def feature_columns_for_context(self, context: str) -> list[str]:
        metadata = self.metadata_for_context(context)
        return list(metadata.get("feature_columns") or [])

    def is_ready(self, context: str = POST_QUALIFYING) -> bool:
        models = self.models_for_context(context)
        return (
            models.get("position_model") is not None
            and models.get("top10_model") is not None
            and models.get("podium_model") is not None
        )


model_store = ModelStore()


def load_all_models() -> None:
    model_store.load_all(settings.MODELS_STORE_PATH)
