"""Small, serializable baseline estimators shared by training and serving."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin


class MedianRegressor(BaseEstimator, RegressorMixin):
    """Historical/no-skill median baseline, learned on the fold only."""

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "MedianRegressor":
        self.value_ = float(pd.Series(y).median())
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.full(len(X), self.value_, dtype=float)


class ZeroChangeRegressor(BaseEstimator, RegressorMixin):
    """Position gain/loss baseline: predict no net position change."""

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "ZeroChangeRegressor":
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.zeros(len(X), dtype=float)


class GridPositionRegressor(BaseEstimator, RegressorMixin):
    """Operational post-qualifying baseline using only the known starting grid."""

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "GridPositionRegressor":
        self.fallback_ = float(pd.Series(y).median())
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        values = pd.to_numeric(X["grid_position"], errors="coerce").fillna(self.fallback_)
        return values.to_numpy(dtype=float)


class QualifyingPositionRegressor(BaseEstimator, RegressorMixin):
    """Post-qualifying domain baseline using the available qualifying order.

    The active post-qualifying model deliberately contains only one position
    predictor.  Keeping this estimator separate from the legacy grid baseline
    avoids duplicating the same signal under two feature names.
    """

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "QualifyingPositionRegressor":
        self.fallback_ = float(pd.Series(y).median())
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        values = pd.to_numeric(X["qualifying_position"], errors="coerce").fillna(self.fallback_)
        return values.to_numpy(dtype=float)
